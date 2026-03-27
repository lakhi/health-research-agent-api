import csv
import logging
import unicodedata
from pathlib import Path

from agno.db.postgres import PostgresDb
from agno.knowledge import Knowledge
from agno.vectordb.pgvector import PgVector, SearchType

from db.session import get_db_url_cached
from knowledge_base import get_azure_embedder

logger = logging.getLogger(__name__)

NEX_KNOWLEDGE_DIR = Path(__file__).resolve().parent / "nex_knoweldge"
NEX_MEMBERS_CSV = NEX_KNOWLEDGE_DIR / "nex_members_list.csv"

MEMBER_REQUIRED_COLUMNS = {
    "first_name",
    "last_name",
    "gender",
    "email_address",
    "academic_position",
    "faculty_affiliation",
    "department_affiliation",
    "discipline",
    "ucris_url",
}


def get_nex_knowledge() -> Knowledge:
    db_url = get_db_url_cached()

    nex_knowledge = Knowledge(
        name="Health in Society Research Network Knowledge",
        vector_db=PgVector(
            db_url=db_url,
            search_type=SearchType.hybrid,
            table_name="nex_embeddings",
            embedder=get_azure_embedder(),
        ),
        contents_db=get_nex_contents_db(),
    )

    return nex_knowledge


def get_nex_contents_db():
    db_url = get_db_url_cached()

    nex_contents = PostgresDb(
        db_url,
        id="nex_contents",
        knowledge_table="nex_contents",
    )

    return nex_contents


def _normalize_cell(value: str | None) -> str:
    if value is None:
        return ""
    return value.strip()


def _normalize_name(name: str) -> str:
    """Normalize a name for matching: NFC unicode, collapse whitespace, strip."""
    return " ".join(unicodedata.normalize("NFC", name).split()).strip()


def _read_csv_rows(file_path: Path) -> list[dict[str, str]]:
    if not file_path.exists():
        raise ValueError(f"Required CSV not found: {file_path}")

    with file_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if not reader.fieldnames:
            raise ValueError(f"CSV has no header row: {file_path}")

        rows: list[dict[str, str]] = []
        for raw_row in reader:
            normalized_row: dict[str, str] = {}
            for key, value in raw_row.items():
                if key is None:
                    continue
                normalized_row[key.strip()] = _normalize_cell(value)
            rows.append(normalized_row)

    return rows


def _read_csv_headers(file_path: Path) -> set[str]:
    if not file_path.exists():
        raise ValueError(f"Required CSV not found: {file_path}")

    with file_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.reader(csv_file)
        try:
            first_row = next(reader)
        except StopIteration as exc:
            raise ValueError(f"CSV has no header row: {file_path}") from exc

    return {header.strip() for header in first_row if header is not None}


def _validate_required_columns(required_columns: set[str], file_path: Path) -> None:
    headers = _read_csv_headers(file_path)
    missing_columns = sorted(required_columns - headers)
    if missing_columns:
        raise ValueError(f"Missing required columns in {file_path.name}: {', '.join(missing_columns)}")


def _build_member_name_index() -> dict[str, dict[str, str]]:
    """Build a mapping from normalized "FirstName LastName" → full member metadata dict.

    Reads from the members CSV. Used for matching u:Cloud folder names to members.
    """
    members_rows = _read_csv_rows(NEX_MEMBERS_CSV)
    _validate_required_columns(MEMBER_REQUIRED_COLUMNS, NEX_MEMBERS_CSV)

    members_by_name: dict[str, dict[str, str]] = {}
    for index, member in enumerate(members_rows, start=2):
        first_name = _normalize_cell(member.get("first_name", ""))
        last_name = _normalize_cell(member.get("last_name", ""))
        full_name = _normalize_name(f"{first_name} {last_name}")

        if not full_name:
            logger.warning("Empty name in %s at row %d, skipping", NEX_MEMBERS_CSV.name, index)
            continue

        if full_name in members_by_name:
            logger.warning(
                "Duplicate name in %s: '%s' (row %d), keeping first occurrence", NEX_MEMBERS_CSV.name, full_name, index
            )
            continue

        member_metadata = {key: _normalize_cell(value) for key, value in member.items()}
        member_metadata["email_address"] = member_metadata.get("email_address", "").strip().lower()
        members_by_name[full_name] = member_metadata

    return members_by_name


def get_research_articles_from_ucloud(discovered_pdfs: list) -> list[dict]:
    """Match discovered PDFs from u:Cloud to network members and build knowledge base data.

    Args:
        discovered_pdfs: List of DiscoveredPDF objects from NextcloudPDFProvider.

    Returns:
        List of dicts with "path" (Path) and "metadata" (dict) keys.
    """
    members_by_name = _build_member_name_index()

    kb_data: list[dict] = []
    for pdf in discovered_pdfs:
        normalized_folder = _normalize_name(pdf.member_folder_name)
        member_metadata = members_by_name.get(normalized_folder)

        if member_metadata is None:
            logger.warning(
                "u:Cloud folder '%s' does not match any member in %s, skipping",
                pdf.member_folder_name,
                NEX_MEMBERS_CSV.name,
            )
            continue

        member_metadata = dict(member_metadata)
        member_name = " ".join(
            part
            for part in [
                member_metadata.get("first_name", ""),
                member_metadata.get("last_name", ""),
            ]
            if part
        ).strip()
        member_metadata["network_member_name"] = member_name or "Unknown"

        metadata = {
            **member_metadata,
            "source_type": "research_paper",
        }

        kb_data.append(
            {
                "path": pdf.local_path,
                "name": f"NEX Research - {member_name}",
                "metadata": metadata,
            }
        )

    return kb_data
