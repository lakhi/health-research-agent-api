import csv
from pathlib import Path
from urllib.parse import urlparse

from agno.db.postgres import PostgresDb
from agno.knowledge import Knowledge
from agno.vectordb.pgvector import PgVector, SearchType

from db.session import get_db_url_cached
from knowledge_base import get_azure_embedder

# 0. TODO: add DOI-style citations referencing to every file in the knowledge base
# 1. TODO: think about the name field for each document while adding it to kb (becomes part of the embeddings and/or contents db tables)
# 2. TODO: impl async loading of knowledge base if startup time is too long: https://docs-v1.agno.com/vectordb/pgvector
# 3. TODO: try out the SemanticChuking strategy (once the chunker is fixed in agno lib - works well with OpenAI embedder) and compare with RecursiveChunking

NEX_KNOWLEDGE_DIR = Path(__file__).resolve().parent / "nex_knoweldge"
NEX_MEMBERS_CSV = NEX_KNOWLEDGE_DIR / "nex_members_list.csv"
NEX_ARTICLES_CSV = NEX_KNOWLEDGE_DIR / "nex_research_articles.csv"

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

ARTICLE_REQUIRED_COLUMNS = {"doi", "member_email", "pdf_url"}


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


def _normalize_email(value: str) -> str:
    return value.strip().lower()


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


def _validate_blob_pdf_url(url: str) -> None:
    parsed_url = urlparse(url)

    if parsed_url.scheme != "https":
        raise ValueError(f"Invalid URL scheme '{parsed_url.scheme}' for pdf_url: {url}")

    if not parsed_url.netloc.endswith(".blob.core.windows.net"):
        raise ValueError(f"Invalid Azure Blob host for pdf_url: {url}")

    path_parts = [part for part in parsed_url.path.split("/") if part]
    if len(path_parts) < 2:
        raise ValueError(f"Azure Blob URL must include container and blob path: {url}")

    if not path_parts[-1].lower().endswith(".pdf"):
        raise ValueError(f"Expected a PDF URL ending with .pdf: {url}")


def _build_member_index(
    members_rows: list[dict[str, str]],
) -> dict[str, dict[str, str]]:
    _validate_required_columns(MEMBER_REQUIRED_COLUMNS, NEX_MEMBERS_CSV)

    members_by_email: dict[str, dict[str, str]] = {}
    for index, member in enumerate(members_rows, start=2):
        email = _normalize_email(member.get("email_address", ""))
        if not email:
            raise ValueError(f"Missing email_address in {NEX_MEMBERS_CSV.name} at row {index}")

        if email in members_by_email:
            raise ValueError(f"Duplicate email_address in {NEX_MEMBERS_CSV.name}: {email}")

        member_metadata = {key: _normalize_cell(value) for key, value in member.items()}
        member_metadata["email_address"] = email
        members_by_email[email] = member_metadata

    return members_by_email


def get_research_article_dois() -> set[str]:
    article_rows = _read_csv_rows(NEX_ARTICLES_CSV)
    _validate_required_columns(ARTICLE_REQUIRED_COLUMNS, NEX_ARTICLES_CSV)

    return {row["doi"] for row in article_rows if row.get("doi")}


def get_research_articles_data() -> list:
    members_rows = _read_csv_rows(NEX_MEMBERS_CSV)
    article_rows = _read_csv_rows(NEX_ARTICLES_CSV)

    _validate_required_columns(MEMBER_REQUIRED_COLUMNS, NEX_MEMBERS_CSV)
    _validate_required_columns(ARTICLE_REQUIRED_COLUMNS, NEX_ARTICLES_CSV)

    members_by_email = _build_member_index(members_rows)

    seen_dois: set[str] = set()
    seen_pdf_urls: set[str] = set()
    kb_data: list[dict[str, dict[str, str] | str]] = []

    for index, article in enumerate(article_rows, start=2):
        doi = _normalize_cell(article.get("doi", ""))
        member_email = _normalize_email(article.get("member_email", ""))
        pdf_url = _normalize_cell(article.get("pdf_url", ""))

        if not doi:
            raise ValueError(f"Missing doi in {NEX_ARTICLES_CSV.name} at row {index}")
        if not member_email:
            raise ValueError(f"Missing member_email in {NEX_ARTICLES_CSV.name} at row {index}")
        if not pdf_url:
            raise ValueError(f"Missing pdf_url in {NEX_ARTICLES_CSV.name} at row {index}")

        if doi in seen_dois:
            raise ValueError(f"Duplicate doi in {NEX_ARTICLES_CSV.name}: {doi}")
        seen_dois.add(doi)

        if pdf_url in seen_pdf_urls:
            raise ValueError(f"Duplicate pdf_url in {NEX_ARTICLES_CSV.name}: {pdf_url}")
        seen_pdf_urls.add(pdf_url)

        _validate_blob_pdf_url(pdf_url)

        if member_email not in members_by_email:
            raise ValueError(f"Unknown member_email in {NEX_ARTICLES_CSV.name} at row {index}: {member_email}")

        member_metadata = dict(members_by_email[member_email])
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
            "doi": doi,
            "source_type": "research_paper",
        }

        kb_data.append(
            {
                "url": pdf_url,
                "metadata": metadata,
            }
        )

    return kb_data
