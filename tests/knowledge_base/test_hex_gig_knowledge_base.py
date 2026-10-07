import sys
import types
from pathlib import Path


def _install_agno_stubs() -> None:
    # setattr rather than plain assignment: mypy cannot see attributes added to a
    # dynamically created ModuleType, and these stubs exist precisely to be dynamic.
    agno = types.ModuleType("agno")

    knowledge_module = types.ModuleType("agno.knowledge")
    setattr(knowledge_module, "Knowledge", object)

    pgvector_module = types.ModuleType("agno.vectordb.pgvector")
    setattr(pgvector_module, "PgVector", object)
    setattr(pgvector_module, "HNSW", object)
    setattr(pgvector_module, "SearchType", types.SimpleNamespace(hybrid="hybrid"))

    pdf_reader_module = types.ModuleType("agno.knowledge.reader.pdf_reader")
    setattr(pdf_reader_module, "PDFReader", object)

    postgres_module = types.ModuleType("agno.db.postgres")
    setattr(postgres_module, "PostgresDb", object)

    azure_embedder_module = types.ModuleType("agno.knowledge.embedder.azure_openai")
    setattr(azure_embedder_module, "AzureOpenAIEmbedder", object)

    sys.modules["agno"] = agno
    sys.modules["agno.knowledge"] = knowledge_module
    sys.modules["agno.vectordb.pgvector"] = pgvector_module
    sys.modules["agno.knowledge.reader.pdf_reader"] = pdf_reader_module
    sys.modules["agno.db.postgres"] = postgres_module
    sys.modules["agno.knowledge.embedder.azure_openai"] = azure_embedder_module


_STUBBED_MODULES = (
    "agno",
    "agno.knowledge",
    "agno.vectordb.pgvector",
    "agno.db.postgres",
    "agno.knowledge.embedder.azure_openai",
    "agno.knowledge.reader.pdf_reader",
)
_real_modules = {name: sys.modules.get(name) for name in _STUBBED_MODULES}
_modules_before = set(sys.modules)

_install_agno_stubs()

# Imported after the stubs are installed, by design — the real agno package must never load.
from knowledge_base import hex_gig_knowledge_base  # noqa: E402
from services.nextcloud_client import RemoteEntry  # noqa: E402
from services.nextcloud_pdf_provider import RemotePDF  # noqa: E402

# Put the real modules back and forget project modules imported against the stubs. This file
# keeps its own reference to the stubbed hex_gig_knowledge_base; without the cleanup, every test
# collected after it would import a knowledge_base whose PgVector is `object`.
for _name, _module in _real_modules.items():
    if _module is None:
        sys.modules.pop(_name, None)
    else:
        sys.modules[_name] = _module
for _name in set(sys.modules) - _modules_before:
    if _name.split(".")[0] in {"knowledge_base", "services"}:
        sys.modules.pop(_name, None)

MEMBERS_HEADER = (
    "first_name,last_name,email_address,academic_position,"
    "faculty_affiliation,department_affiliation,discipline,uni_wien_url\n"
)


def _write_csv(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def _remote_pdf(folder: str, filename: str = "paper.pdf") -> RemotePDF:
    return RemotePDF(member_folder_name=folder, filename=filename, entry=RemoteEntry(name=filename, is_dir=False))


def _members(tmp_path: Path, monkeypatch, rows: str) -> None:
    members_csv = tmp_path / "members.csv"
    _write_csv(members_csv, MEMBERS_HEADER + rows)
    monkeypatch.setattr(hex_gig_knowledge_base, "HEX_GIG_MEMBERS_CSV", members_csv)


def test_match_member_papers_matches_member(tmp_path, monkeypatch):
    _members(
        tmp_path,
        monkeypatch,
        "Ada,Lovelace,ada@univie.ac.at,Professor,Faculty X,Dept Y,Computing,https://ucris.example/ada\n",
    )

    result = hex_gig_knowledge_base.match_member_papers([_remote_pdf("Ada Lovelace")])

    assert len(result) == 1
    pdf, member = result[0]
    assert pdf.remote_path == "Ada Lovelace/paper.pdf"
    assert member["first_name"] == "Ada"
    assert member["last_name"] == "Lovelace"
    assert member["email_address"] == "ada@univie.ac.at"
    assert member["network_member_name"] == "Ada Lovelace"
    assert hex_gig_knowledge_base.research_paper_name(member) == "HeX Research - Ada Lovelace"


def test_match_member_papers_handles_double_spaces(tmp_path, monkeypatch):
    """u:Cloud folders may have double spaces (e.g. 'Dagmar  Vorlicek') but CSV has single."""
    _members(tmp_path, monkeypatch, "Dagmar ,Vorlicek,dagmar@univie.ac.at,PostDoc,Faculty S,Sociology,ISP,\n")

    result = hex_gig_knowledge_base.match_member_papers([_remote_pdf("Dagmar  Vorlicek")])

    assert len(result) == 1
    assert result[0][1]["last_name"] == "Vorlicek"


def test_match_member_papers_handles_umlauts(tmp_path, monkeypatch):
    _members(tmp_path, monkeypatch, "Laura Maria,König,laura@univie.ac.at,Professor,Faculty P,Dept C,Health,\n")

    result = hex_gig_knowledge_base.match_member_papers([_remote_pdf("Laura Maria König")])

    assert len(result) == 1
    assert result[0][1]["last_name"] == "König"


def test_match_member_papers_skips_unmatched_folder(tmp_path, monkeypatch):
    _members(tmp_path, monkeypatch, "Ada,Lovelace,ada@univie.ac.at,Professor,Faculty X,Dept Y,Computing,\n")

    assert hex_gig_knowledge_base.match_member_papers([_remote_pdf("Unknown Person")]) == []


def test_match_member_papers_keeps_each_pdf_of_a_member(tmp_path, monkeypatch):
    _members(tmp_path, monkeypatch, "Ada,Lovelace,ada@univie.ac.at,Professor,Faculty X,Dept Y,Computing,\n")

    result = hex_gig_knowledge_base.match_member_papers(
        [_remote_pdf("Ada Lovelace", "paper1.pdf"), _remote_pdf("Ada Lovelace", "paper2.pdf")]
    )

    # Both share one knowledge name, which is why the sync identifies papers by remote path.
    assert {pdf.remote_path for pdf, _ in result} == {"Ada Lovelace/paper1.pdf", "Ada Lovelace/paper2.pdf"}
    assert {hex_gig_knowledge_base.research_paper_name(member) for _, member in result} == {
        "HeX Research - Ada Lovelace"
    }


def test_build_research_paper_metadata_marks_source_and_omits_missing_doi(tmp_path):
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-fake")

    metadata = hex_gig_knowledge_base.build_research_paper_metadata(
        {"first_name": "Ada", "network_member_name": "Ada Lovelace"}, pdf_path
    )

    assert metadata == {"first_name": "Ada", "network_member_name": "Ada Lovelace", "source_type": "research_paper"}
