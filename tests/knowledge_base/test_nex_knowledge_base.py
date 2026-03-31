import sys
import types
from dataclasses import dataclass
from pathlib import Path



def _install_agno_stubs() -> None:
    agno = types.ModuleType("agno")

    knowledge_module = types.ModuleType("agno.knowledge")
    knowledge_module.Knowledge = object

    pgvector_module = types.ModuleType("agno.vectordb.pgvector")
    pgvector_module.PgVector = object
    pgvector_module.SearchType = types.SimpleNamespace(hybrid="hybrid")

    postgres_module = types.ModuleType("agno.db.postgres")
    postgres_module.PostgresDb = object

    azure_embedder_module = types.ModuleType("agno.knowledge.embedder.azure_openai")
    azure_embedder_module.AzureOpenAIEmbedder = object

    sys.modules["agno"] = agno
    sys.modules["agno.knowledge"] = knowledge_module
    sys.modules["agno.vectordb.pgvector"] = pgvector_module
    sys.modules["agno.db.postgres"] = postgres_module
    sys.modules["agno.knowledge.embedder.azure_openai"] = azure_embedder_module


_install_agno_stubs()

from knowledge_base import nex_knowledge_base

MEMBERS_HEADER = (
    "first_name,last_name,gender,email_address,academic_position,"
    "faculty_affiliation,department_affiliation,discipline,uni_wien_url\n"
)


def _write_csv(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


@dataclass
class FakeDiscoveredPDF:
    local_path: Path
    member_folder_name: str
    filename: str


def test_get_research_articles_from_ucloud_matches_member(tmp_path, monkeypatch):
    members_csv = tmp_path / "members.csv"
    _write_csv(
        members_csv,
        MEMBERS_HEADER
        + "Ada,Lovelace,F,ada@univie.ac.at,Professor,Faculty X,Dept Y,Computing,https://ucris.example/ada\n",
    )
    monkeypatch.setattr(nex_knowledge_base, "NEX_MEMBERS_CSV", members_csv)

    pdf_path = tmp_path / "Ada Lovelace" / "paper.pdf"
    pdf_path.parent.mkdir()
    pdf_path.write_bytes(b"%PDF-fake")

    discovered = [FakeDiscoveredPDF(local_path=pdf_path, member_folder_name="Ada Lovelace", filename="paper.pdf")]
    result = nex_knowledge_base.get_research_articles_from_ucloud(discovered)

    assert len(result) == 1
    assert result[0]["path"] == pdf_path
    assert result[0]["metadata"]["first_name"] == "Ada"
    assert result[0]["metadata"]["last_name"] == "Lovelace"
    assert result[0]["metadata"]["email_address"] == "ada@univie.ac.at"
    assert result[0]["metadata"]["source_type"] == "research_paper"
    assert result[0]["metadata"]["network_member_name"] == "Ada Lovelace"
    assert result[0]["name"] == "NEX Research - Ada Lovelace"


def test_get_research_articles_from_ucloud_handles_double_spaces(tmp_path, monkeypatch):
    """u:Cloud folders may have double spaces (e.g. 'Dagmar  Vorlicek') but CSV has single."""
    members_csv = tmp_path / "members.csv"
    _write_csv(
        members_csv,
        MEMBERS_HEADER + "Dagmar ,Vorlicek,F,dagmar@univie.ac.at,PostDoc,Faculty S,Sociology,ISP,\n",
    )
    monkeypatch.setattr(nex_knowledge_base, "NEX_MEMBERS_CSV", members_csv)

    pdf_path = tmp_path / "Dagmar  Vorlicek" / "paper.pdf"
    pdf_path.parent.mkdir()
    pdf_path.write_bytes(b"%PDF-fake")

    discovered = [FakeDiscoveredPDF(local_path=pdf_path, member_folder_name="Dagmar  Vorlicek", filename="paper.pdf")]
    result = nex_knowledge_base.get_research_articles_from_ucloud(discovered)

    assert len(result) == 1
    assert result[0]["metadata"]["last_name"] == "Vorlicek"


def test_get_research_articles_from_ucloud_handles_umlauts(tmp_path, monkeypatch):
    members_csv = tmp_path / "members.csv"
    _write_csv(
        members_csv,
        MEMBERS_HEADER + "Laura Maria,König,F,laura@univie.ac.at,Professor,Faculty P,Dept C,Health,\n",
    )
    monkeypatch.setattr(nex_knowledge_base, "NEX_MEMBERS_CSV", members_csv)

    pdf_path = tmp_path / "Laura Maria König" / "paper.pdf"
    pdf_path.parent.mkdir()
    pdf_path.write_bytes(b"%PDF-fake")

    discovered = [FakeDiscoveredPDF(local_path=pdf_path, member_folder_name="Laura Maria König", filename="paper.pdf")]
    result = nex_knowledge_base.get_research_articles_from_ucloud(discovered)

    assert len(result) == 1
    assert result[0]["metadata"]["last_name"] == "König"


def test_get_research_articles_from_ucloud_skips_unmatched_folder(tmp_path, monkeypatch):
    members_csv = tmp_path / "members.csv"
    _write_csv(
        members_csv,
        MEMBERS_HEADER + "Ada,Lovelace,F,ada@univie.ac.at,Professor,Faculty X,Dept Y,Computing,\n",
    )
    monkeypatch.setattr(nex_knowledge_base, "NEX_MEMBERS_CSV", members_csv)

    pdf_path = tmp_path / "Unknown Person" / "paper.pdf"
    pdf_path.parent.mkdir()
    pdf_path.write_bytes(b"%PDF-fake")

    discovered = [FakeDiscoveredPDF(local_path=pdf_path, member_folder_name="Unknown Person", filename="paper.pdf")]
    result = nex_knowledge_base.get_research_articles_from_ucloud(discovered)

    assert len(result) == 0


def test_get_research_articles_from_ucloud_multiple_pdfs_per_member(tmp_path, monkeypatch):
    members_csv = tmp_path / "members.csv"
    _write_csv(
        members_csv,
        MEMBERS_HEADER + "Ada,Lovelace,F,ada@univie.ac.at,Professor,Faculty X,Dept Y,Computing,\n",
    )
    monkeypatch.setattr(nex_knowledge_base, "NEX_MEMBERS_CSV", members_csv)

    folder = tmp_path / "Ada Lovelace"
    folder.mkdir()
    pdf1 = folder / "paper1.pdf"
    pdf2 = folder / "paper2.pdf"
    pdf1.write_bytes(b"%PDF-1")
    pdf2.write_bytes(b"%PDF-2")

    discovered = [
        FakeDiscoveredPDF(local_path=pdf1, member_folder_name="Ada Lovelace", filename="paper1.pdf"),
        FakeDiscoveredPDF(local_path=pdf2, member_folder_name="Ada Lovelace", filename="paper2.pdf"),
    ]
    result = nex_knowledge_base.get_research_articles_from_ucloud(discovered)

    assert len(result) == 2
    paths = {r["path"] for r in result}
    assert pdf1 in paths
    assert pdf2 in paths
