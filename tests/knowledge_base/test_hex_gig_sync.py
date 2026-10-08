"""The HeX knowledge sync: what it inserts, replaces, deletes, and what it refuses to delete (#42)."""

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from agno.knowledge import Knowledge

from knowledge_base import hex_gig_sync
from knowledge_base.hex_gig_sync import (
    SourceItem,
    StoredItem,
    SyncAborted,
    decode_sync_marker,
    encode_sync_marker,
    fingerprint_of,
    plan_sync,
)
from services.nextcloud_client import RemoteEntry
from services.nextcloud_pdf_provider import RemotePDF

# ─── plan_sync ────────────────────────────────────────────────────────────────


def _src(key: str, fp: str = "v1") -> SourceItem:
    return SourceItem(key=key, fingerprint=fp)


def _stored(key: str | None, fp: str | None = "v1", content_id: str | None = None, complete: bool = True) -> StoredItem:
    return StoredItem(content_id=content_id or f"id-{key}", key=key, fingerprint=fp, complete=complete)


def test_unchanged_item_is_left_alone():
    plan = plan_sync([_src("a")], [_stored("a")])

    assert plan.unchanged == 1
    assert (plan.insert, plan.replace, plan.delete, plan.held_back) == ([], [], [], [])


def test_new_item_is_inserted():
    plan = plan_sync([_src("a"), _src("b")], [_stored("a")])

    assert [item.key for item in plan.insert] == ["b"]


def test_changed_item_is_replaced():
    stored = _stored("a", fp="v1")
    plan = plan_sync([_src("a", fp="v2")], [stored])

    assert plan.replace == [([stored], _src("a", fp="v2"))]


def test_incomplete_item_is_replaced_so_an_interrupted_load_resumes():
    stored = _stored("a", complete=False)
    plan = plan_sync([_src("a")], [stored])

    assert plan.replace == [([stored], _src("a"))]


def test_item_gone_from_the_source_is_deleted():
    gone = _stored("b")
    plan = plan_sync([_src(k) for k in "acdefghij"], [_stored(k) for k in "acdefghij"] + [gone])

    assert plan.delete == [gone]
    assert plan.held_back == []


def test_mass_disappearance_is_held_back():
    stored = [_stored(str(i)) for i in range(10)]
    # 3 of 10 gone is over the 20% guard.
    plan = plan_sync([_src(str(i)) for i in range(7)], stored)

    assert plan.delete == []
    assert {item.key for item in plan.held_back} == {"7", "8", "9"}


def test_empty_listing_deletes_nothing():
    stored = [_stored(str(i)) for i in range(50)]

    plan = plan_sync([], stored)

    assert plan.delete == []
    assert len(plan.held_back) == 50


def test_small_collections_may_still_lose_two_items():
    # 2 of 3 is far above 20%, but the floor lets small collections shed a couple of items.
    plan = plan_sync([_src("a")], [_stored("a"), _stored("b"), _stored("c")])

    assert {item.key for item in plan.delete} == {"b", "c"}


def test_surplus_copies_of_a_current_item_are_removed_without_tripping_the_guard():
    current = _stored("a", content_id="keep")
    duplicates = [_stored("a", content_id=f"dup-{i}") for i in range(5)]

    plan = plan_sync([_src("a")], [current, *duplicates])

    assert plan.unchanged == 1
    assert plan.delete == duplicates
    assert plan.held_back == []


def test_every_copy_is_removed_when_an_item_changes():
    copies = [_stored("a", fp="old", content_id="1"), _stored("a", fp="older", content_id="2")]

    plan = plan_sync([_src("a", fp="new")], copies)

    assert plan.replace == [(copies, _src("a", fp="new"))]


def test_unidentified_rows_are_left_to_the_caller():
    plan = plan_sync([_src("a")], [_stored("a"), _stored(None)])

    assert plan.unchanged == 1
    assert (plan.delete, plan.held_back) == ([], [])


def test_a_key_listed_twice_by_the_source_is_inserted_once():
    plan = plan_sync([_src("a"), _src("a", fp="v2")], [])

    assert plan.insert == [_src("a")]


# ─── identity marker ──────────────────────────────────────────────────────────


def test_sync_marker_round_trips():
    marker = encode_sync_marker("Laura Maria König/paper.pdf", "abc")

    assert decode_sync_marker(marker) == ("Laura Maria König/paper.pdf", "abc")


@pytest.mark.parametrize("description", [None, "", "a human description", '{"sync": "other/9", "key": "k"}', "[1, 2]"])
def test_descriptions_without_a_marker_identify_nothing(description):
    assert decode_sync_marker(description) == (None, None)


def test_fingerprint_ignores_dict_order_but_not_values():
    assert fingerprint_of("etag", {"a": 1, "b": 2}) == fingerprint_of("etag", {"b": 2, "a": 1})
    assert fingerprint_of("etag", {"a": 1}) != fingerprint_of("etag", {"a": 2})


# ─── end to end against a fake knowledge base ─────────────────────────────────


class FakeKnowledge:
    """Records what the sync does; stores what it inserts so a second run sees it."""

    def __init__(
        self,
        contents: list[SimpleNamespace] | None = None,
        failing_removals: frozenset[str] | set[str] = frozenset(),
        insert_status: str = "completed",
    ):
        self.contents = list(contents or [])
        self.failing_removals = set(failing_removals)
        self.insert_status = insert_status
        self.inserted: list[dict[str, Any]] = []
        self.removed: list[str] = []
        self._next_id = 0

    async def aget_content(self):
        return list(self.contents), len(self.contents)

    async def aremove_content_by_id(self, content_id: str) -> bool:
        if content_id in self.failing_removals:
            return False
        self.removed.append(content_id)
        self.contents = [c for c in self.contents if c.id != content_id]
        return True

    async def ainsert(self, **kwargs: Any) -> None:
        self.inserted.append(kwargs)
        self._next_id += 1
        self.contents.append(
            content(
                f"new-{self._next_id}",
                kwargs["name"],
                kwargs.get("metadata") or {},
                description=kwargs.get("description"),
                status=self.insert_status,
            )
        )


def content(content_id, name, metadata, description=None, status="completed") -> SimpleNamespace:
    return SimpleNamespace(
        id=content_id, name=name, metadata=metadata, description=description, status=status, status_message=None
    )


def _run(coro):
    return asyncio.run(coro)


def _k(fake: "FakeKnowledge") -> Knowledge:
    """The fakes implement only what the sync calls; mypy is told so here, once."""
    return cast(Knowledge, fake)


def _p(fake: "FakeProvider") -> Any:
    return fake


# News ─────────────────────────────────────────────────────────────────────────


def _article(guid: str, title: str, body_hash: str) -> dict[str, Any]:
    return {
        "name": f"HeX News - {title}",
        "text_content": f"{title} body",
        "metadata": {"guid": guid, "title": title, "source_type": "news_article", "content_hash": body_hash},
    }


def _stored_article(content_id: str, guid: str, title: str, body_hash: str) -> SimpleNamespace:
    return content(content_id, f"HeX News - {title}", _article(guid, title, body_hash)["metadata"])


def test_news_title_change_replaces_the_article_instead_of_duplicating_it(monkeypatch):
    feed = [_article("news-1", "New title", "h2")] + [_article(f"news-{i}", f"T{i}", "h") for i in range(2, 9)]
    monkeypatch.setattr(hex_gig_sync, "get_rss_news_data", lambda: feed)
    knowledge = FakeKnowledge(
        [_stored_article("old", "news-1", "Old title", "h1")]
        + [_stored_article(f"s{i}", f"news-{i}", f"T{i}", "h") for i in range(2, 9)]
    )

    report = _run(hex_gig_sync.sync_news(_k(knowledge)))

    assert knowledge.removed == ["old"]
    assert [call["name"] for call in knowledge.inserted] == ["HeX News - New title"]
    assert report.replaced == 1 and report.unchanged == 7 and report.ok


def test_news_article_removed_from_the_site_is_deleted(monkeypatch):
    monkeypatch.setattr(
        hex_gig_sync, "get_rss_news_data", lambda: [_article(f"news-{i}", f"T{i}", "h") for i in range(9)]
    )
    knowledge = FakeKnowledge(
        [_stored_article(f"s{i}", f"news-{i}", f"T{i}", "h") for i in range(9)]
        + [_stored_article("gone", "news-99", "Retracted", "h")]
    )

    report = _run(hex_gig_sync.sync_news(_k(knowledge)))

    assert knowledge.removed == ["gone"]
    assert knowledge.inserted == []
    assert report.deleted == 1 and report.ok


def test_news_feed_failure_changes_nothing(monkeypatch):
    def broken_feed():
        raise OSError("feed down")

    monkeypatch.setattr(hex_gig_sync, "get_rss_news_data", broken_feed)
    knowledge = FakeKnowledge([_stored_article("s1", "news-1", "T1", "h")])

    with pytest.raises(OSError):
        _run(hex_gig_sync.sync_news(_k(knowledge)))
    assert knowledge.removed == [] and knowledge.inserted == []


# Research papers ──────────────────────────────────────────────────────────────

MEMBER = {"first_name": "Ada", "last_name": "Lovelace", "network_member_name": "Ada Lovelace"}


class FakeProvider:
    def __init__(self, files: dict[str, str], tmp_path: Path):
        # remote path "Folder/file.pdf" → etag
        self.files = files
        self.tmp_path = tmp_path
        self.downloaded: list[str] = []

    async def discover(self) -> list[RemotePDF]:
        return [
            RemotePDF(
                member_folder_name=path.split("/")[0],
                filename=path.split("/")[1],
                entry=RemoteEntry(name=path.split("/")[1], is_dir=False, etag=etag),
            )
            for path, etag in self.files.items()
        ]

    async def download(self, pdf: RemotePDF) -> Path:
        self.downloaded.append(pdf.remote_path)
        local = self.tmp_path / pdf.remote_path
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_bytes(b"%PDF-fake")
        return local


@pytest.fixture
def papers_env(monkeypatch):
    """Every u:Cloud folder belongs to Ada; DOI extraction is irrelevant here."""
    monkeypatch.setattr(hex_gig_sync, "match_member_papers", lambda pdfs: [(pdf, dict(MEMBER)) for pdf in pdfs])
    monkeypatch.setattr(
        hex_gig_sync,
        "build_research_paper_metadata",
        lambda member, path: {**member, "source_type": "research_paper"},
    )


def _stored_paper(content_id: str, remote_path: str, etag: str, member: dict[str, str] = MEMBER) -> SimpleNamespace:
    marker = encode_sync_marker(remote_path, fingerprint_of(etag, member))
    return content(
        content_id, "HeX Research - Ada Lovelace", {**member, "source_type": "research_paper"}, description=marker
    )


def test_papers_download_only_what_changed(tmp_path, papers_env):
    files = {f"Ada Lovelace/p{i}.pdf": "e1" for i in range(10)}
    files["Ada Lovelace/p0.pdf"] = "e2"  # edited on u:Cloud
    files["Ada Lovelace/new.pdf"] = "e1"  # added on u:Cloud
    provider = FakeProvider(files, tmp_path)
    knowledge = FakeKnowledge([_stored_paper(f"c{i}", f"Ada Lovelace/p{i}.pdf", "e1") for i in range(10)])

    report = _run(hex_gig_sync.sync_research_papers(_k(knowledge), _p(provider), reader=cast(Any, object())))

    assert sorted(provider.downloaded) == ["Ada Lovelace/new.pdf", "Ada Lovelace/p0.pdf"]
    assert knowledge.removed == ["c0"]
    assert report.unchanged == 9 and report.replaced == 1 and report.inserted == 1 and report.ok
    # Identity rides in the description, never in metadata the model could filter on.
    for call in knowledge.inserted:
        assert call["upsert"] is False
        assert decode_sync_marker(call["description"])[0] in {"Ada Lovelace/new.pdf", "Ada Lovelace/p0.pdf"}
        assert "ucloud" not in " ".join(call["metadata"]).lower()


def test_paper_deleted_from_ucloud_is_removed(tmp_path, papers_env):
    provider = FakeProvider({f"Ada Lovelace/p{i}.pdf": "e1" for i in range(9)}, tmp_path)
    knowledge = FakeKnowledge(
        [_stored_paper(f"c{i}", f"Ada Lovelace/p{i}.pdf", "e1") for i in range(9)]
        + [_stored_paper("deleted", "Ada Lovelace/book.pdf", "e1")]
    )

    report = _run(hex_gig_sync.sync_research_papers(_k(knowledge), _p(provider), reader=cast(Any, object())))

    assert knowledge.removed == ["deleted"]
    assert provider.downloaded == []
    assert report.deleted == 1 and report.ok


def test_csv_correction_reaches_the_member_papers(tmp_path, papers_env):
    old_member = {**MEMBER, "uni_wien_url": "https://old.example"}
    provider = FakeProvider({"Ada Lovelace/p.pdf": "e1"}, tmp_path)
    knowledge = FakeKnowledge([_stored_paper("c", "Ada Lovelace/p.pdf", "e1", member=old_member)])

    report = _run(hex_gig_sync.sync_research_papers(_k(knowledge), _p(provider), reader=cast(Any, object())))

    assert knowledge.removed == ["c"] and report.replaced == 1


def test_papers_stored_without_identity_abort_the_sync(tmp_path, papers_env):
    provider = FakeProvider({"Ada Lovelace/p.pdf": "e1"}, tmp_path)
    legacy = content("legacy", "HeX Research - Ada Lovelace", {"source_type": "research_paper"})
    knowledge = FakeKnowledge([legacy])

    with pytest.raises(SyncAborted):
        _run(hex_gig_sync.sync_research_papers(_k(knowledge), _p(provider), reader=cast(Any, object())))
    assert knowledge.removed == [] and knowledge.inserted == [] and provider.downloaded == []


def test_a_failed_removal_skips_the_reinsert_and_fails_the_run(tmp_path, papers_env):
    provider = FakeProvider({"Ada Lovelace/p.pdf": "e2"}, tmp_path)
    knowledge = FakeKnowledge([_stored_paper("c", "Ada Lovelace/p.pdf", "e1")], failing_removals={"c"})

    report = _run(hex_gig_sync.sync_research_papers(_k(knowledge), _p(provider), reader=cast(Any, object())))

    assert knowledge.inserted == [] and provider.downloaded == []
    assert report.failed == 1 and not report.ok


def test_a_removal_error_is_counted_and_the_rest_of_the_plan_still_runs(tmp_path, papers_env):
    provider = FakeProvider({"Ada Lovelace/p.pdf": "e2", "Ada Lovelace/new.pdf": "e1"}, tmp_path)
    knowledge = FakeKnowledge([_stored_paper("c", "Ada Lovelace/p.pdf", "e1")])

    async def broken_remove(content_id: str) -> bool:
        raise OSError("SSL connection has been closed unexpectedly")

    knowledge.aremove_content_by_id = broken_remove  # type: ignore[method-assign]

    report = _run(hex_gig_sync.sync_research_papers(_k(knowledge), _p(provider), reader=cast(Any, object())))

    assert provider.downloaded == ["Ada Lovelace/new.pdf"]
    assert report.failed == 1 and report.inserted == 1 and not report.ok


def test_replace_removes_incomplete_copies_first_and_keeps_the_last_usable_one(tmp_path, papers_env):
    provider = FakeProvider({"Ada Lovelace/p.pdf": "e2"}, tmp_path)
    good = _stored_paper("good", "Ada Lovelace/p.pdf", "e1")
    stub = _stored_paper("stub", "Ada Lovelace/p.pdf", "e1")
    stub.status = "failed"
    knowledge = FakeKnowledge([good, stub], failing_removals={"stub"})

    report = _run(hex_gig_sync.sync_research_papers(_k(knowledge), _p(provider), reader=cast(Any, object())))

    assert knowledge.removed == [] and knowledge.inserted == []
    assert report.failed == 1 and not report.ok


def test_an_insert_agno_marks_failed_fails_the_run(tmp_path, papers_env):
    # agno records an embedding failure on the content row instead of raising.
    provider = FakeProvider({"Ada Lovelace/p.pdf": "e1"}, tmp_path)
    knowledge = FakeKnowledge(insert_status="failed")

    report = _run(hex_gig_sync.sync_research_papers(_k(knowledge), _p(provider), reader=cast(Any, object())))

    assert report.inserted == 1 and report.incomplete == 1 and not report.ok


def test_a_second_run_with_no_changes_writes_nothing(tmp_path, papers_env):
    provider = FakeProvider({f"Ada Lovelace/p{i}.pdf": "e1" for i in range(3)}, tmp_path)
    knowledge = FakeKnowledge()

    _run(hex_gig_sync.sync_research_papers(_k(knowledge), _p(provider), reader=cast(Any, object())))
    provider.downloaded.clear()
    inserted_before = len(knowledge.inserted)
    report = _run(hex_gig_sync.sync_research_papers(_k(knowledge), _p(provider), reader=cast(Any, object())))

    assert provider.downloaded == [] and len(knowledge.inserted) == inserted_before
    assert knowledge.removed == []
    assert report.unchanged == 3 and report.ok


# Member profiles ──────────────────────────────────────────────────────────────


def test_profiles_stored_before_the_marker_are_replaced_once(monkeypatch):
    profile = {
        "name": "HeX Member - Ada Lovelace",
        "text_content": "Network Member: Ada Lovelace",
        "metadata": {"source_type": "member_profile"},
    }
    monkeypatch.setattr(hex_gig_sync, "get_member_profiles_data", lambda: [profile])
    knowledge = FakeKnowledge([content("legacy", profile["name"], profile["metadata"])])

    first = _run(hex_gig_sync.sync_member_profiles(_k(knowledge)))
    second = _run(hex_gig_sync.sync_member_profiles(_k(knowledge)))

    assert first.replaced == 1
    assert second.unchanged == 1 and second.replaced == 0
