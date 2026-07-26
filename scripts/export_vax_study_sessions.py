"""Read-only export of the vax-study chat sessions for offline analysis.

Pulls every session and writes two artefacts for the researcher:

  * a long-format CSV (one row per conversational turn), keyed by participant
    ID and condition so it joins straight onto the Prolific/survey data;
  * a self-contained HTML archive for reading the transcripts.

The script never writes: the ``db`` source opens a ``READ ONLY`` connection and
the ``api`` source issues only GETs.

Two sources, and ``db`` is strongly preferred:

  ``db``   One ``SELECT`` over a server-side cursor. Completes in minutes and
           puts no load on the running Container App.
  ``api``  Fetches each session over HTTP. Measured at ~10s/session against the
           0.5 vCPU deployment (the app must deserialise and re-serialise a
           multi-MB payload per request), i.e. hours for the full study, with a
           real risk of OOMing the 1Gi container on the largest sessions. Use
           only when the database is unreachable.

The other shape detail that drives the design: a single session's ``runs``
payload is ~2 MB because every run re-sends the system prompt, retrieved
references and the full prior history. Only ``run_input`` (the participant's
message) and ``content`` (the agent's reply) are kept, which is both ~300x
smaller and the correct view of the conversation. Fetched sessions are cached
as trimmed JSON, so switching sources or re-running costs nothing.

The database password is read from --password-file or $VAX_DB_PASSWORD; it is
never accepted as a command-line argument, where it would leak into shell
history and the process table.

Usage:
    python scripts/export_vax_study_sessions.py --password-file ~/.vaxpw
    python scripts/export_vax_study_sessions.py --source api --out-dir exports
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import quote

import httpx

logger = logging.getLogger("vax_export")

DEFAULT_API_URL = "https://marhinovirus-api.wittywave-d78264d4.swedencentral.azurecontainerapps.io"

# Live vax-study Postgres. Agno names session tables "<project>_agentos_sessions"
# and puts them in the "ai" schema, not public. The hyphen in the project name
# means the identifier must always be quoted.
#
# The two legacy tables in the same schema (ai.control_agent_sessions,
# ai.simple_language_sessions, 19 rows total) are pre-launch testing from
# 22-23 Apr 2026 and contain no Prolific IDs; the whole study is in this table.
DEFAULT_DB_HOST = "vax-db.postgres.database.azure.com"
DEFAULT_DB_NAME = "postgres"
DEFAULT_DB_USER = "postgres"
DEFAULT_DB_SCHEMA = "ai"
DEFAULT_DB_TABLE = "vax-study_agentos_sessions"

# Page size for GET /sessions. The endpoint materialises full session rows
# server-side, so 300+ reliably OOMs the container; 100 is verified safe.
DEFAULT_PAGE_SIZE = 100

# Agent id -> human-readable study condition.
CONDITION_LABELS = {"c": "control", "sl": "simple_language"}

# Prolific participant IDs are 24 lowercase hex characters.
_PROLIFIC_ID = re.compile(r"^[0-9a-f]{24}$")
# Near-misses seen in the live data (truncated / overlong paste).
_PROLIFIC_LIKE = re.compile(r"^[0-9a-f]{20,26}$")


@dataclass
class Turn:
    """One participant message or one agent reply."""

    index: int
    run_index: int
    role: str
    content: str
    created_at: str


@dataclass
class SessionRecord:
    session_id: str
    participant_id: str
    condition: str
    condition_label: str
    id_kind: str
    session_name: str
    created_at: str
    updated_at: str
    total_tokens: int
    turns: list[Turn] = field(default_factory=list)


def parse_session_id(raw_session_id: str) -> tuple[str, str, str]:
    """Split a session id into (participant_id, condition, id_kind).

    Session ids are written by the survey platform as ``<prolific-id>-<agent>``.
    The live data contains a handful of malformed variants, so rather than drop
    them the classification is surfaced as ``id_kind`` and the researcher can
    filter:

      ``prolific``  - clean 24-hex id with a condition suffix
      ``variant``   - recognisably a participant, but the id needs a look
                      (``@email.prolific.com`` suffix, stray whitespace,
                      wrong length)
      ``test``      - internal testing (first names, bare UUIDs, empty id)
    """
    session_id = raw_session_id.strip()
    had_whitespace = session_id != raw_session_id

    condition = ""
    remainder = session_id
    for suffix in ("-sl", "-c"):
        if session_id.endswith(suffix):
            condition = suffix[1:]
            remainder = session_id[: -len(suffix)]
            break

    # Some participants pasted their Prolific email rather than the bare id.
    had_email = "@" in remainder
    participant_id = remainder.split("@", 1)[0].strip()

    if not condition or not participant_id:
        kind = "test"
    elif _PROLIFIC_ID.match(participant_id) and not had_email and not had_whitespace:
        kind = "prolific"
    elif _PROLIFIC_LIKE.match(participant_id):
        kind = "variant"
    else:
        kind = "test"

    return participant_id, condition, kind


def fetch_session_index(client: httpx.Client, page_size: int) -> list[dict[str, Any]]:
    """Page through GET /sessions until every session summary is collected."""
    sessions: list[dict[str, Any]] = []
    page = 1
    while True:
        response = client.get(
            "/sessions",
            params={"limit": page_size, "page": page, "sort_by": "created_at", "sort_order": "asc"},
        )
        response.raise_for_status()
        payload = response.json()
        batch = payload.get("data") or []
        sessions.extend(batch)

        meta = payload.get("meta") or {}
        total_pages = meta.get("total_pages") or 0
        logger.info("session index: page %d/%s (%d rows, %d total)", page, total_pages, len(batch), len(sessions))
        if page >= total_pages or not batch:
            if meta.get("total_count") is not None:
                logger.info("session index complete: %d of %d reported", len(sessions), meta["total_count"])
            return sessions
        page += 1


def _iso(value: Any) -> str:
    """Normalise a timestamp to the ISO form the API emits.

    The API serialises timestamps for us, but the raw ``created_at`` columns and
    in-JSON run timestamps are BigInteger epoch seconds. Both sources must
    produce identical CSV output, so everything is funnelled through here.
    """
    if value is None or value == "":
        return ""
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return str(value)


def _extract_turns(runs: list[dict[str, Any]]) -> list[Turn]:
    """Reduce a raw runs payload to alternating participant/agent turns.

    The participant's message and ``content`` (the agent's reply) are stored per
    run, so no de-duplication of the resent history is needed.

    The two sources spell the input field differently: Postgres stores
    ``input: {"input_content": ...}`` and the API serialises the same thing as
    ``run_input``. Both are accepted, otherwise one source silently yields
    agent-only transcripts.
    """
    turns: list[Turn] = []
    for run_index, run in enumerate(runs):
        created_at = _iso(run.get("created_at"))

        user_text = run.get("run_input")
        if user_text is None:
            user_text = run.get("input")
        if isinstance(user_text, dict):  # DB shape, and multimodal input
            user_text = user_text.get("input_content") or user_text.get("content")
        if user_text:
            turns.append(Turn(len(turns), run_index, "participant", str(user_text), created_at))

        agent_text = run.get("content")
        if agent_text:
            turns.append(Turn(len(turns), run_index, "agent", str(agent_text), created_at))

    return turns


def _cache_path(session_id: str, cache_dir: Path) -> Path:
    """Stable on-disk name for a session's trimmed transcript.

    Session ids come from an external system, so they are never trusted as
    filenames. sha1 (not ``hash()``) because PYTHONHASHSEED randomisation would
    make the cache miss on every fresh process.
    """
    digest = hashlib.sha1(session_id.encode("utf-8")).hexdigest()[:16]
    return cache_dir / f"{digest}-{re.sub(r'[^A-Za-z0-9_.-]', '_', session_id)[:80]}.json"


def _write_cache(session_id: str, turns: list[Turn], cache_dir: Path) -> None:
    _cache_path(session_id, cache_dir).write_text(
        json.dumps([turn.__dict__ for turn in turns], ensure_ascii=False), encoding="utf-8"
    )


def _read_cache(session_id: str, cache_dir: Path) -> list[Turn] | None:
    cache_file = _cache_path(session_id, cache_dir)
    if not cache_file.exists():
        return None
    return [Turn(**turn) for turn in json.loads(cache_file.read_text(encoding="utf-8"))]


def fetch_turns(client: httpx.Client, session_id: str, cache_dir: Path, refresh: bool) -> list[Turn]:
    """Fetch one session's runs over HTTP, trimmed to turns and cached on disk."""
    if not refresh:
        cached = _read_cache(session_id, cache_dir)
        if cached is not None:
            return cached

    response = client.get(f"/sessions/{quote(session_id, safe='')}/runs", params={"type": "agent"})
    response.raise_for_status()
    runs = response.json()
    if not isinstance(runs, list):
        runs = runs.get("data") or []

    turns = _extract_turns(runs)
    _write_cache(session_id, turns, cache_dir)
    return turns


def build_records(
    client: httpx.Client,
    index: list[dict[str, Any]],
    cache_dir: Path,
    refresh: bool,
    pause: float,
) -> Iterator[SessionRecord]:
    total = len(index)
    for position, summary in enumerate(index, start=1):
        session_id = str(summary.get("session_id") or "")

        try:
            turns = fetch_turns(client, session_id, cache_dir, refresh)
        except httpx.HTTPError as exc:
            logger.warning("session %s: fetch failed (%s) - exported with 0 turns", session_id, exc)
            turns = []
        else:
            # Only pace real network calls; cached reads need no backoff.
            if pause:
                time.sleep(pause)

        if position % 25 == 0 or position == total:
            logger.info("transcripts: %d/%d", position, total)

        yield _make_record(
            session_id=session_id,
            agent_id=str(summary.get("agent_id") or ""),
            session_name=str(summary.get("session_name") or ""),
            created_at=summary.get("created_at"),
            updated_at=summary.get("updated_at"),
            total_tokens=summary.get("total_tokens"),
            turns=turns,
        )


def _make_record(
    session_id: str,
    agent_id: str,
    session_name: str,
    created_at: Any,
    updated_at: Any,
    total_tokens: Any,
    turns: list[Turn],
) -> SessionRecord:
    participant_id, condition, kind = parse_session_id(session_id)
    # agent_id is the authoritative condition; the id suffix is what the survey
    # platform wrote and can disagree (or be missing) on malformed ids.
    condition = agent_id or condition
    return SessionRecord(
        session_id=session_id,
        participant_id=participant_id,
        condition=condition,
        condition_label=CONDITION_LABELS.get(condition, ""),
        id_kind=kind,
        session_name=session_name,
        created_at=_iso(created_at),
        updated_at=_iso(updated_at),
        total_tokens=int(total_tokens or 0),
        turns=turns,
    )


def iter_db_records(dsn: str, schema: str, table: str, cache_dir: Path) -> Iterator[SessionRecord]:
    """Stream every session straight from Postgres.

    Uses a named (server-side) cursor so the multi-MB ``runs`` blobs arrive in
    small batches instead of materialising the whole ~1.4 GB table client-side —
    the same mistake that OOMs the API container at large page sizes.
    """
    import psycopg2
    import psycopg2.extras

    connection = psycopg2.connect(dsn)
    try:
        # Belt and braces: the export must not be able to mutate study data.
        # Not autocommit - a server-side cursor only lives inside a transaction.
        connection.set_session(readonly=True)
        with connection.cursor(name="vax_export", cursor_factory=psycopg2.extras.DictCursor) as cursor:
            cursor.itersize = 20
            cursor.execute(
                "SELECT session_id, agent_id, session_data, created_at, updated_at, runs "
                f'FROM "{schema}"."{table}" ORDER BY created_at ASC'  # noqa: S608 - not user input
            )
            for position, row in enumerate(cursor, start=1):
                session_id = str(row["session_id"] or "")
                session_data = row["session_data"] or {}
                metrics = session_data.get("session_metrics") or {}

                turns = _extract_turns(row["runs"] or [])
                _write_cache(session_id, turns, cache_dir)

                if position % 100 == 0:
                    logger.info("read %d sessions from postgres", position)

                yield _make_record(
                    session_id=session_id,
                    agent_id=str(row["agent_id"] or ""),
                    session_name=str(session_data.get("session_name") or ""),
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    total_tokens=metrics.get("total_tokens"),
                    turns=turns,
                )
    finally:
        connection.rollback()
        connection.close()


def build_dsn(host: str, port: int, user: str, dbname: str, password: str) -> str:
    """libpq keyword DSN. Azure Postgres Flexible Server requires TLS."""
    sslmode = "require" if "azure" in host else "prefer"
    escaped = password.replace("\\", "\\\\").replace("'", "\\'")
    return f"host={host} port={port} user={user} dbname={dbname} sslmode={sslmode} password='{escaped}'"


def read_password(password_file: Path | None) -> str:
    """Never taken as an argv value, which would leak to shell history and `ps`."""
    if password_file:
        return password_file.read_text(encoding="utf-8").strip()
    return os.environ.get("VAX_DB_PASSWORD", "").strip()


CSV_COLUMNS = [
    "participant_id",
    "condition",
    "condition_label",
    "id_kind",
    "duplicate_participant",
    "session_id",
    "session_created_at",
    "turn_index",
    "run_index",
    "role",
    "turn_created_at",
    "content",
]


def write_turns_csv(records: list[SessionRecord], duplicates: set[str], path: Path) -> int:
    """Long format: one row per turn, ready for R/pandas."""
    rows = 0
    # utf-8-sig so Excel opens the German/English text correctly.
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        for record in records:
            for turn in record.turns:
                writer.writerow(
                    {
                        "participant_id": record.participant_id,
                        "condition": record.condition,
                        "condition_label": record.condition_label,
                        "id_kind": record.id_kind,
                        "duplicate_participant": int(record.participant_id in duplicates),
                        "session_id": record.session_id,
                        "session_created_at": record.created_at,
                        "turn_index": turn.index,
                        "run_index": turn.run_index,
                        "role": turn.role,
                        "turn_created_at": turn.created_at,
                        "content": turn.content,
                    }
                )
                rows += 1
    return rows


_HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Vax study - conversation archive</title>
<style>
  :root {
    --bg: #f8fafc; --panel: #ffffff; --border: #dbe2ea; --text: #1e293b;
    --muted: #64748b; --accent: #1e40af; --participant: #eef2f6; --agent: #fff7ed;
  }
  * { box-sizing: border-box; }
  body { margin: 0; font: 15px/1.55 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
         background: var(--bg); color: var(--text); }
  header { padding: 14px 20px; background: var(--panel); border-bottom: 1px solid var(--border);
            display: flex; gap: 14px; align-items: center; flex-wrap: wrap; }
  header h1 { font-size: 16px; margin: 0 12px 0 0; }
  header .stat { color: var(--muted); font-size: 13px; }
  input, select { font: inherit; padding: 6px 10px; border: 1px solid var(--border);
                   border-radius: 6px; background: var(--panel); color: inherit; }
  input[type=search] { min-width: 260px; }
  main { display: grid; grid-template-columns: minmax(240px, 340px) 1fr; height: calc(100vh - 59px); }
  #list { overflow-y: auto; border-right: 1px solid var(--border); background: var(--panel); }
  #list button { display: block; width: 100%; text-align: left; padding: 9px 14px; border: 0;
                  border-bottom: 1px solid var(--border); background: none; cursor: pointer;
                  font: inherit; color: inherit; }
  #list button:hover { background: var(--participant); }
  #list button[aria-current="true"] { background: var(--accent); color: #fff; }
  #list .pid { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12.5px; }
  #list .sub { font-size: 12px; color: var(--muted); }
  #list button[aria-current="true"] .sub { color: #dbeafe; }
  #detail { overflow-y: auto; padding: 22px 26px; }
  .turn { margin-bottom: 14px; padding: 11px 14px; border-radius: 8px; max-width: 74ch;
           white-space: pre-wrap; overflow-wrap: anywhere; }
  .turn.participant { background: var(--participant); }
  .turn.agent { background: var(--agent); }
  .turn .who { font-size: 11px; text-transform: uppercase; letter-spacing: .05em;
                color: var(--muted); margin-bottom: 5px; }
  .badge { display: inline-block; font-size: 11.5px; padding: 2px 8px; border-radius: 99px;
            background: var(--participant); color: var(--muted); margin-left: 6px; }
  .empty { color: var(--muted); }
  h2 { font-size: 15px; margin: 0 0 4px; font-family: ui-monospace, Menlo, monospace; }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#0f172a; --panel:#111c33; --border:#24344f; --text:#e2e8f0; --muted:#94a3b8;
             --accent:#3b82f6; --participant:#1c2942; --agent:#33240f; }
  }
</style>
</head>
<body>
<header>
  <h1>Vax study - conversation archive</h1>
  <input type="search" id="q" placeholder="Search participant ID or message text...">
  <select id="condition">
    <option value="">All conditions</option>
    <option value="c">Control (c)</option>
    <option value="sl">Simple language (sl)</option>
  </select>
  <select id="kind">
    <option value="participants">Participants only</option>
    <option value="prolific">Clean Prolific IDs</option>
    <option value="variant">Variant IDs</option>
    <option value="test">Internal tests</option>
    <option value="">Everything</option>
  </select>
  <span class="stat" id="stat"></span>
</header>
<main>
  <nav id="list"></nav>
  <section id="detail"><p class="empty">Select a conversation on the left.</p></section>
</main>
<script id="data" type="application/json">__PAYLOAD__</script>
<script>
  const SESSIONS = JSON.parse(document.getElementById('data').textContent);
  const list = document.getElementById('list');
  const detail = document.getElementById('detail');
  const stat = document.getElementById('stat');
  const q = document.getElementById('q');
  const condition = document.getElementById('condition');
  const kind = document.getElementById('kind');
  let current = null;

  const matchesKind = (s, want) =>
    want === '' ? true :
    want === 'participants' ? s.id_kind !== 'test' : s.id_kind === want;

  function filtered() {
    const term = q.value.trim().toLowerCase();
    const cond = condition.value;
    const want = kind.value;
    return SESSIONS.filter(s => {
      if (cond && s.condition !== cond) return false;
      if (!matchesKind(s, want)) return false;
      if (!term) return true;
      if (s.participant_id.toLowerCase().includes(term)) return true;
      return s.turns.some(t => t.content.toLowerCase().includes(term));
    });
  }

  function render() {
    const rows = filtered();
    stat.textContent = rows.length + ' of ' + SESSIONS.length + ' conversations';
    list.replaceChildren(...rows.map(s => {
      const b = document.createElement('button');
      b.setAttribute('aria-current', String(s.session_id === current));
      const pid = document.createElement('div');
      pid.className = 'pid';
      pid.textContent = s.participant_id || '(no id)';
      const sub = document.createElement('div');
      sub.className = 'sub';
      sub.textContent = `${s.condition_label || s.id_kind} · ${s.turns.length} turns · ${s.created_at.slice(0, 10)}`;
      b.append(pid, sub);
      b.onclick = () => { current = s.session_id; show(s); render(); };
      return b;
    }));
    if (!rows.length) list.replaceChildren(Object.assign(
      document.createElement('p'), { className: 'empty', style: 'padding:14px', textContent: 'No matches.' }));
  }

  function show(s) {
    const head = document.createElement('div');
    const h2 = document.createElement('h2');
    h2.textContent = s.participant_id || '(no id)';
    const badges = document.createElement('div');
    for (const text of [s.condition_label || 'unknown condition', s.id_kind,
                        s.created_at.slice(0, 16).replace('T', ' '), s.turns.length + ' turns']) {
      const span = document.createElement('span');
      span.className = 'badge';
      span.textContent = text;
      badges.append(span);
    }
    head.append(h2, badges);

    const turns = s.turns.map(t => {
      const d = document.createElement('div');
      d.className = 'turn ' + t.role;
      const who = document.createElement('div');
      who.className = 'who';
      who.textContent = t.role;
      const body = document.createElement('div');
      body.textContent = t.content;
      d.append(who, body);
      return d;
    });
    detail.replaceChildren(head, ...turns);
    detail.scrollTop = 0;
  }

  for (const el of [q, condition, kind]) el.addEventListener('input', render);
  render();
</script>
</body>
</html>
"""


def write_html_archive(records: list[SessionRecord], path: Path) -> None:
    """Self-contained, offline-readable transcript browser."""
    payload = [
        {
            "session_id": record.session_id,
            "participant_id": record.participant_id,
            "condition": record.condition,
            "condition_label": record.condition_label,
            "id_kind": record.id_kind,
            "created_at": record.created_at,
            "turns": [{"role": turn.role, "content": turn.content} for turn in record.turns],
        }
        for record in records
    ]
    # </script> inside transcript text would close the data island early.
    encoded = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    # Plain replace, not str.format: the template contains literal JS/CSS braces.
    path.write_text(_HTML_TEMPLATE.replace("__PAYLOAD__", encoded), encoding="utf-8")


def summarise(records: list[SessionRecord], duplicates: set[str]) -> str:
    by_kind: dict[str, int] = {}
    by_condition: dict[str, int] = {}
    for record in records:
        by_kind[record.id_kind] = by_kind.get(record.id_kind, 0) + 1
        if record.id_kind != "test":
            key = record.condition_label or record.condition or "unknown"
            by_condition[key] = by_condition.get(key, 0) + 1

    participants = {r.participant_id for r in records if r.id_kind != "test"}
    turns = sum(len(r.turns) for r in records)
    empty = sum(1 for r in records if not r.turns)

    lines = [
        f"sessions exported      : {len(records)}",
        f"  by id kind           : {by_kind}",
        f"  participant sessions : {sum(v for k, v in by_kind.items() if k != 'test')}",
        f"  by condition         : {by_condition}",
        f"unique participants    : {len(participants)}",
        f"in both conditions     : {len(duplicates)}",
        f"turns                  : {turns}",
        f"sessions with 0 turns  : {empty}",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", choices=("db", "api"), default="db", help="Where to read sessions from")
    parser.add_argument("--out-dir", type=Path, default=Path("exports"), help="Where to write the CSV and HTML")
    parser.add_argument("--cache-dir", type=Path, default=None, help="Trimmed-transcript cache (default: OUT/.cache)")
    parser.add_argument("--refresh", action="store_true", help="Ignore the cache and refetch every transcript")

    db_group = parser.add_argument_group("db source")
    db_group.add_argument("--db-host", default=DEFAULT_DB_HOST)
    db_group.add_argument("--db-port", type=int, default=5432)
    db_group.add_argument("--db-user", default=DEFAULT_DB_USER)
    db_group.add_argument("--db-name", default=DEFAULT_DB_NAME)
    db_group.add_argument("--db-schema", default=DEFAULT_DB_SCHEMA)
    db_group.add_argument("--db-table", default=DEFAULT_DB_TABLE)
    db_group.add_argument("--password-file", type=Path, default=None, help="File holding the DB password")

    api_group = parser.add_argument_group("api source")
    api_group.add_argument("--api-url", default=DEFAULT_API_URL, help="Base URL of the vax-study API")
    api_group.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE, help="GET /sessions page size")
    api_group.add_argument("--pause", type=float, default=0.15, help="Seconds between transcript fetches")
    api_group.add_argument("--timeout", type=float, default=120.0, help="Per-request timeout in seconds")
    args = parser.parse_args(argv)

    if args.page_size > 200:
        parser.error("--page-size above 200 OOMs the API container; keep it at or below 200")

    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    cache_dir: Path = args.cache_dir or (out_dir / ".cache")
    cache_dir.mkdir(parents=True, exist_ok=True)

    started = time.monotonic()
    if args.source == "db":
        password = read_password(args.password_file)
        if not password:
            parser.error("no database password: pass --password-file or set VAX_DB_PASSWORD")
        dsn = build_dsn(args.db_host, args.db_port, args.db_user, args.db_name, password)
        logger.info(
            "reading from postgres %s/%s table %s.%s", args.db_host, args.db_name, args.db_schema, args.db_table
        )
        records = list(iter_db_records(dsn, args.db_schema, args.db_table, cache_dir))
    else:
        logger.warning("api source is slow and loads the live container; prefer --source db")
        with httpx.Client(base_url=args.api_url.rstrip("/"), timeout=args.timeout) as client:
            index = fetch_session_index(client, args.page_size)
            records = list(build_records(client, index, cache_dir, args.refresh, args.pause))

    seen: dict[str, set[str]] = {}
    for record in records:
        if record.id_kind != "test":
            seen.setdefault(record.participant_id, set()).add(record.condition)
    duplicates = {pid for pid, conditions in seen.items() if len(conditions) > 1}

    stamp = date.today().isoformat()
    csv_path = out_dir / f"vax_study_turns_{stamp}.csv"
    html_path = out_dir / f"vax_study_transcripts_{stamp}.html"

    rows = write_turns_csv(records, duplicates, csv_path)
    write_html_archive(records, html_path)

    logger.info("\n%s", summarise(records, duplicates))
    logger.info("wrote %s (%d rows, %.1f MB)", csv_path, rows, csv_path.stat().st_size / 1e6)
    logger.info("wrote %s (%.1f MB)", html_path, html_path.stat().st_size / 1e6)
    logger.info("done in %.0fs", time.monotonic() - started)
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        logger.warning("interrupted; cached transcripts are kept, re-run to resume")
        sys.exit(130)
