"""Keeps the HeX knowledge base in step with its sources: u:Cloud papers, the members CSV, the news feed.

Runs in the scheduled ``hex-gig-knowledge-sync`` job only, never in the API (#42). Each run lists
every source, compares it with what is stored, and touches only the difference: it inserts what is
new, replaces what changed, and removes what the source no longer has. A run where nothing changed
writes nothing.

Why this replaced ``Knowledge.ainsert(..., skip_if_exists=True)`` on every app start:

* agno's skip path still calls ``_update_content``, which UPDATEs the metadata of every chunk of
  every skipped document. Each restart rewrote all ~26k rows (674k updates in a month), which
  scattered the table on disk and made a cold search ~9x slower.
* Nothing ever removed a document whose source was gone: a publication deleted from u:Cloud stayed
  searchable.
* News was keyed by title, so an article whose title changed was stored again under the new title
  and the old copy was never removed. News is keyed by its feed ``guid`` here.

**Identity.** Each stored item needs a key that names its source item. Papers can't use the content
name: all of a member's PDFs share ``HeX Research - <member>``. The key and a fingerprint of the
source version are kept in the content row's ``description`` (see ``encode_sync_marker``). Not in
``metadata``: agno advertises every metadata key to the model as a filter it may use, and free-text
keys are exactly how invented filter values emptied searches in #47.

**Deletion guard.** A listing that comes back short — an expired share token, a u:Cloud outage, an
empty feed — must not wipe the knowledge base. Deletions of items that vanished from a source are
held back, and the run is reported as failed, when they exceed ``MAX_DELETE_FRACTION`` of the
stored items (with a floor of ``MIN_DELETE_ALLOWANCE`` so small collections can still lose one or
two). A listing that fails outright raises before anything is compared, so it deletes nothing.
"""

import hashlib
import json
import logging
import math
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from agno.knowledge import Knowledge
from agno.knowledge.content import Content, ContentStatus
from agno.knowledge.reader.pdf_reader import PDFReader

from knowledge_base.hex_gig_knowledge_base import (
    build_research_paper_metadata,
    get_member_profiles_data,
    match_member_papers,
    research_paper_name,
)
from knowledge_base.hex_gig_rss_knowledge import RSS_SOURCE_TYPE, get_rss_news_data
from services.nextcloud_pdf_provider import NextcloudPDFProvider

logger = logging.getLogger(__name__)

SYNC_MARKER_VERSION = "hex-sync/1"

MAX_DELETE_FRACTION = 0.2
MIN_DELETE_ALLOWANCE = 2

RESEARCH_PAPER_SOURCE_TYPE = "research_paper"
MEMBER_PROFILE_SOURCE_TYPE = "member_profile"


class SyncAborted(RuntimeError):
    """The stored state can't be reconciled safely, so the source was left untouched."""


@dataclass(frozen=True)
class SourceItem:
    """One item a source currently has. ``payload`` is whatever its inserter needs."""

    key: str
    fingerprint: str
    payload: Any = None


@dataclass(frozen=True)
class StoredItem:
    """One stored content row, as the sync sees it. ``key`` is None when it can't be identified."""

    content_id: str
    key: str | None
    fingerprint: str | None
    complete: bool


@dataclass
class SyncPlan:
    insert: list[SourceItem] = field(default_factory=list)
    # Every stored copy of the key is removed before the new version is inserted.
    replace: list[tuple[list[StoredItem], SourceItem]] = field(default_factory=list)
    delete: list[StoredItem] = field(default_factory=list)
    # Items gone from the source whose removal the guard held back.
    held_back: list[StoredItem] = field(default_factory=list)
    unchanged: int = 0


@dataclass
class SyncReport:
    source: str
    seen: int = 0
    unchanged: int = 0
    inserted: int = 0
    replaced: int = 0
    deleted: int = 0
    held_back: int = 0
    failed: int = 0
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.failed == 0 and self.held_back == 0

    def summary(self) -> str:
        return (
            f"{self.source}: {self.seen} in source, {self.unchanged} unchanged, {self.inserted} inserted, "
            f"{self.replaced} replaced, {self.deleted} deleted, {self.held_back} deletions held back, "
            f"{self.failed} failed" + (f" — {self.error}" if self.error else "")
        )


def fingerprint_of(*parts: Any) -> str:
    """A stable digest of the parts, for detecting that a source item changed."""
    encoded = json.dumps(parts, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:32]


def encode_sync_marker(key: str, fingerprint: str) -> str:
    return json.dumps(
        {"sync": SYNC_MARKER_VERSION, "key": key, "fingerprint": fingerprint}, ensure_ascii=False, sort_keys=True
    )


def decode_sync_marker(description: str | None) -> tuple[str | None, str | None]:
    """``(key, fingerprint)`` from a content description, or ``(None, None)`` if it carries none."""
    if not description:
        return None, None
    try:
        marker = json.loads(description)
    except (TypeError, ValueError):
        return None, None
    if not isinstance(marker, dict) or marker.get("sync") != SYNC_MARKER_VERSION:
        return None, None
    key, fingerprint = marker.get("key"), marker.get("fingerprint")
    return (key if isinstance(key, str) else None), (fingerprint if isinstance(fingerprint, str) else None)


def plan_sync(
    source: Sequence[SourceItem],
    stored: Sequence[StoredItem],
    *,
    max_delete_fraction: float = MAX_DELETE_FRACTION,
    min_delete_allowance: int = MIN_DELETE_ALLOWANCE,
) -> SyncPlan:
    """Decide what to insert, replace and delete so that ``stored`` matches ``source``.

    A stored copy is current only if its fingerprint matches and its ingestion completed; anything
    else is replaced, which is also how a run interrupted mid-load resumes. Surplus copies of a
    key that is still current are removed without counting against the guard — they are
    duplicates, not data the source dropped. Stored items with no key are the caller's concern
    and are ignored here.
    """
    plan = SyncPlan()

    copies_by_key: dict[str, list[StoredItem]] = {}
    for stored_item in stored:
        if stored_item.key is not None:
            copies_by_key.setdefault(stored_item.key, []).append(stored_item)
    stored_keys = len(copies_by_key)

    seen_keys: set[str] = set()
    for source_item in source:
        if source_item.key in seen_keys:
            logger.warning("Source lists %r twice; keeping the first", source_item.key)
            continue
        seen_keys.add(source_item.key)

        copies = copies_by_key.pop(source_item.key, [])
        current = next((c for c in copies if c.complete and c.fingerprint == source_item.fingerprint), None)
        if current is not None:
            plan.unchanged += 1
            plan.delete.extend(c for c in copies if c is not current)
        elif copies:
            plan.replace.append((copies, source_item))
        else:
            plan.insert.append(source_item)

    vanished = [copy for copies in copies_by_key.values() for copy in copies]
    allowance = max(min_delete_allowance, math.floor(max_delete_fraction * stored_keys))
    if len(copies_by_key) > allowance:
        plan.held_back = vanished
    else:
        plan.delete.extend(vanished)

    return plan


def _is_complete(content: Content) -> bool:
    status = content.status
    return (status.value if isinstance(status, ContentStatus) else status) == ContentStatus.COMPLETED.value


async def _stored_contents(knowledge: Knowledge, source_type: str) -> list[tuple[str, Content]]:
    """``(content_id, content)`` for every stored row of one source type."""
    contents, _ = await knowledge.aget_content()
    return [(c.id, c) for c in contents if c.id and (c.metadata or {}).get("source_type") == source_type]


async def apply_plan(
    knowledge: Knowledge,
    plan: SyncPlan,
    insert: Callable[[SourceItem], Awaitable[None]],
    report: SyncReport,
) -> SyncReport:
    """Carry out a plan, item by item. One item failing never stops the rest."""

    async def remove(item: StoredItem) -> bool:
        # Deletes the chunks by content_id, then the content row; returns False (keeping the row
        # for the next run to retry) when the chunk delete fails.
        if await knowledge.aremove_content_by_id(item.content_id):
            return True
        report.failed += 1
        logger.error("Could not remove content %s; it will be retried on the next run", item.content_id)
        return False

    for stored in plan.delete:
        if await remove(stored):
            report.deleted += 1

    for copies, item in plan.replace:
        removed = [await remove(copy) for copy in copies]
        if not all(removed):
            continue
        try:
            await insert(item)
            report.replaced += 1
        except Exception:
            report.failed += 1
            logger.exception("Could not re-insert %r; it will be retried on the next run", item.key)

    for item in plan.insert:
        try:
            await insert(item)
            report.inserted += 1
        except Exception:
            report.failed += 1
            logger.exception("Could not insert %r; it will be retried on the next run", item.key)

    report.unchanged = plan.unchanged
    report.held_back = len(plan.held_back)
    if plan.held_back:
        logger.error(
            "%s: %d stored items are gone from the source, more than the deletion guard allows; none were "
            "removed. Check the source; if the removals are intended, delete them by hand or re-run with a "
            "higher allowance.",
            report.source,
            len(plan.held_back),
        )
    logger.info(report.summary())
    return report


async def sync_research_papers(knowledge: Knowledge, provider: NextcloudPDFProvider, reader: PDFReader) -> SyncReport:
    """Mirror the PDFs in u:Cloud member folders. Only new or changed PDFs are downloaded."""
    report = SyncReport(source="research papers")

    remote = await provider.discover()
    source = [
        SourceItem(
            key=pdf.remote_path,
            # The member's CSV fields are stored with every chunk of their papers, so a CSV
            # correction (a fixed profile URL) has to reach the papers too, not only the file.
            fingerprint=fingerprint_of(pdf.entry.fingerprint, member_metadata),
            payload=(pdf, member_metadata),
        )
        for pdf, member_metadata in match_member_papers(remote)
    ]
    report.seen = len(source)

    stored = []
    for content_id, c in await _stored_contents(knowledge, RESEARCH_PAPER_SOURCE_TYPE):
        key, fingerprint = decode_sync_marker(c.description)
        stored.append(StoredItem(content_id=content_id, key=key, fingerprint=fingerprint, complete=_is_complete(c)))
    unidentified = [item for item in stored if item.key is None]
    if unidentified:
        # Inserting alongside rows we can't match to a file would duplicate every paper, and
        # deleting them blind is exactly what the guard is for. Fail closed and say how to recover.
        raise SyncAborted(
            f"{len(unidentified)} stored research papers carry no sync identity (stored before the sync job "
            f"existed). Drop the HeX knowledge tables and let this job rebuild them."
        )

    async def insert(item: SourceItem) -> None:
        pdf, member_metadata = item.payload
        local_path = await provider.download(pdf)
        await knowledge.ainsert(
            name=research_paper_name(member_metadata),
            description=encode_sync_marker(item.key, item.fingerprint),
            path=str(local_path),
            reader=reader,
            metadata=build_research_paper_metadata(member_metadata, local_path),
            skip_if_exists=False,
        )

    return await apply_plan(knowledge, plan_sync(source, stored), insert, report)


async def sync_member_profiles(knowledge: Knowledge) -> SyncReport:
    """Mirror the members CSV: one profile per member."""
    report = SyncReport(source="member profiles")

    source = [
        SourceItem(
            key=profile["name"],
            fingerprint=fingerprint_of(profile["text_content"], profile["metadata"]),
            payload=profile,
        )
        for profile in get_member_profiles_data()
    ]
    report.seen = len(source)

    stored = []
    for content_id, c in await _stored_contents(knowledge, MEMBER_PROFILE_SOURCE_TYPE):
        key, fingerprint = decode_sync_marker(c.description)
        # A profile's name is unique, so rows stored before the marker existed are still
        # identifiable; with no fingerprint they are replaced once and carry a marker after.
        stored.append(
            StoredItem(content_id=content_id, key=key or c.name, fingerprint=fingerprint, complete=_is_complete(c))
        )

    async def insert(item: SourceItem) -> None:
        profile = item.payload
        await knowledge.ainsert(
            name=profile["name"],
            description=encode_sync_marker(item.key, item.fingerprint),
            text_content=profile["text_content"],
            metadata=profile["metadata"],
            skip_if_exists=False,
        )

    return await apply_plan(knowledge, plan_sync(source, stored), insert, report)


async def sync_news(knowledge: Knowledge) -> SyncReport:
    """Mirror the network's news feed, keyed by each article's ``guid``.

    The feed lists the site's whole news archive (back to Nov 2024), not a rolling window, so an
    article missing from it has been removed from the site, or is a stale copy from before a title
    change — either way it should go. Either feed failing raises inside ``get_rss_news_data``
    before anything is compared.
    """
    report = SyncReport(source="news")

    items = get_rss_news_data()
    source = [
        SourceItem(key=item["metadata"]["guid"], fingerprint=item["metadata"]["content_hash"], payload=item)
        for item in items
    ]
    report.seen = len(source)

    stored = []
    for content_id, c in await _stored_contents(knowledge, RSS_SOURCE_TYPE):
        metadata = c.metadata or {}
        # An article without a guid can't match any feed item, so it counts as gone from the feed.
        key = metadata.get("guid") or f"no-guid:{content_id}"
        stored.append(
            StoredItem(
                content_id=content_id, key=key, fingerprint=metadata.get("content_hash"), complete=_is_complete(c)
            )
        )

    async def insert(item: SourceItem) -> None:
        article = item.payload
        # Clear chunks an interrupted earlier run left without a content row; news names are unique.
        knowledge.remove_vectors_by_name(article["name"])
        await knowledge.ainsert(
            name=article["name"],
            text_content=article["text_content"],
            metadata=article["metadata"],
            skip_if_exists=False,
        )

    return await apply_plan(knowledge, plan_sync(source, stored), insert, report)
