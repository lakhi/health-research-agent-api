import csv
import logging
import re
import unicodedata
from pathlib import Path

from pypdf import PdfReader as _PdfReader

from agno.db.postgres import PostgresDb
from agno.knowledge import Knowledge
from agno.vectordb.pgvector import PgVector, SearchType

from db.session import get_db_url_cached
from knowledge_base import get_azure_embedder

logger = logging.getLogger(__name__)

# Standard DOI pattern — matches "10.NNNN/suffix" anywhere in text
_DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s\],;:\'\"<>()]+)", re.IGNORECASE)

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
    "uni_wien_url",
}


def _extract_doi_from_pdf(path: Path) -> str | None:
    """Extract the first DOI found in a PDF's title/abstract and reference pages.

    Reads the first 3 pages and last 2 pages — sufficient to capture the DOI
    from the title page header/footer, abstract, or reference list without
    loading the full document into memory.

    Returns a full https://doi.org/... URL, or None if no DOI is found or extraction fails.
    """
    try:
        reader = _PdfReader(str(path))
        pages = reader.pages
        n = len(pages)
        # Indices: first 3 + last 2, deduplicated, clamped to actual page count
        indices = list(dict.fromkeys([0, 1, 2, max(0, n - 2), max(0, n - 1)]))
        text_parts = []
        for i in indices:
            if i < n:
                text_parts.append(pages[i].extract_text() or "")
        text = "\n".join(text_parts)
        match = _DOI_RE.search(text)
        if match:
            doi = match.group(1).rstrip(".")
            # Strip trailing "doi"/"DOI" label — PDF text extraction artifact (e.g. "...609825doi")
            doi = re.sub(r"(?i)doi$", "", doi).rstrip(".")
            # Strip supplemental URL path suffix (e.g. /-/DCSupplemental)
            doi = re.sub(r"/-/.*$", "", doi)
            # Discard DOIs with very short suffixes — likely truncated by a line break in the PDF
            # (e.g. "10.1371/j" or "10.5061/dry"). A broken link is worse than no link.
            suffix = doi.split("/", 1)[1] if "/" in doi else doi
            if len(suffix) < 5:
                logger.warning("Discarding likely truncated DOI from %s: %s", path.name, doi)
                return None
            return f"https://doi.org/{doi}"
    except Exception:
        logger.warning("Could not extract DOI from PDF: %s", path)
    return None


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


def _format_member_profile(member: dict[str, str]) -> str:
    """Format a member's CSV row as readable text for embedding."""
    parts = [f"Network Member: {member.get('first_name', '')} {member.get('last_name', '')}".strip()]

    field_map = {
        "academic_position": "Academic Position",
        "faculty_affiliation": "Faculty",
        "department_affiliation": "Department",
        "discipline": "Discipline",
        "email_address": "Email",
    }
    for key, label in field_map.items():
        value = member.get(key, "").strip()
        if value:
            parts.append(f"{label}: {value}")

    return "\n".join(parts)


def get_member_profiles_data() -> list[dict]:
    """Build member profile documents from the members CSV.

    Returns a list of dicts with keys: ``name``, ``text_content``, ``metadata``.
    Each member becomes one searchable document in the knowledge base.
    """
    members_by_name = _build_member_name_index()

    profiles: list[dict] = []
    for full_name, member in members_by_name.items():
        text_content = _format_member_profile(member)

        metadata = {
            **member,
            "network_member_name": full_name,
            "source_type": "member_profile",
        }

        profiles.append(
            {
                "name": f"NEX Member - {full_name}",
                "text_content": text_content,
                "metadata": metadata,
            }
        )

    return profiles


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

        doi_url = _extract_doi_from_pdf(pdf.local_path)
        metadata = {
            **member_metadata,
            "source_type": "research_paper",
            **({"doi": doi_url} if doi_url else {}),
        }

        kb_data.append(
            {
                "path": pdf.local_path,
                "name": f"NEX Research - {member_name}",
                "metadata": metadata,
            }
        )

    return kb_data
