from pathlib import Path
import sys
import types

import pytest


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

from knowledge_base import hrn_knowledge_base


MEMBERS_HEADER = (
    "first_name,last_name,gender,email_address,academic_position,"
    "faculty_affiliation,department_affiliation,discipline,ucris_url\n"
)


ARTICLES_HEADER = "doi,member_email,pdf_url\n"


def _write_csv(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def test_get_research_articles_data_joins_member_metadata(tmp_path, monkeypatch):
    members_csv = tmp_path / "members.csv"
    articles_csv = tmp_path / "articles.csv"

    _write_csv(
        members_csv,
        MEMBERS_HEADER
        + "Ada,Lovelace,F,ada@univie.ac.at,Professor,Faculty X,Dept Y,Computing,https://ucris.example/ada\n",
    )
    _write_csv(
        articles_csv,
        ARTICLES_HEADER
        + "10.1234/example-doi,ada@univie.ac.at,https://demo.blob.core.windows.net/research/ada-paper.pdf\n",
    )

    monkeypatch.setattr(hrn_knowledge_base, "NEX_MEMBERS_CSV", members_csv)
    monkeypatch.setattr(hrn_knowledge_base, "NEX_ARTICLES_CSV", articles_csv)

    rows = hrn_knowledge_base.get_research_articles_data()

    assert len(rows) == 1
    assert rows[0]["url"] == "https://demo.blob.core.windows.net/research/ada-paper.pdf"
    assert rows[0]["metadata"]["doi"] == "10.1234/example-doi"
    assert rows[0]["metadata"]["first_name"] == "Ada"
    assert rows[0]["metadata"]["last_name"] == "Lovelace"
    assert rows[0]["metadata"]["ucris_url"] == "https://ucris.example/ada"


def test_get_research_articles_data_fails_on_duplicate_doi(tmp_path, monkeypatch):
    members_csv = tmp_path / "members.csv"
    articles_csv = tmp_path / "articles.csv"

    _write_csv(
        members_csv,
        MEMBERS_HEADER
        + "Ada,Lovelace,F,ada@univie.ac.at,Professor,Faculty X,Dept Y,Computing,https://ucris.example/ada\n",
    )
    _write_csv(
        articles_csv,
        ARTICLES_HEADER
        + "10.1234/dup,ada@univie.ac.at,https://demo.blob.core.windows.net/research/a.pdf\n"
        + "10.1234/dup,ada@univie.ac.at,https://demo.blob.core.windows.net/research/b.pdf\n",
    )

    monkeypatch.setattr(hrn_knowledge_base, "NEX_MEMBERS_CSV", members_csv)
    monkeypatch.setattr(hrn_knowledge_base, "NEX_ARTICLES_CSV", articles_csv)

    with pytest.raises(ValueError, match="Duplicate doi"):
        hrn_knowledge_base.get_research_articles_data()


def test_get_research_articles_data_fails_on_unknown_member_email(
    tmp_path, monkeypatch
):
    members_csv = tmp_path / "members.csv"
    articles_csv = tmp_path / "articles.csv"

    _write_csv(
        members_csv,
        MEMBERS_HEADER
        + "Ada,Lovelace,F,ada@univie.ac.at,Professor,Faculty X,Dept Y,Computing,https://ucris.example/ada\n",
    )
    _write_csv(
        articles_csv,
        ARTICLES_HEADER
        + "10.1234/doi,missing@univie.ac.at,https://demo.blob.core.windows.net/research/unknown.pdf\n",
    )

    monkeypatch.setattr(hrn_knowledge_base, "NEX_MEMBERS_CSV", members_csv)
    monkeypatch.setattr(hrn_knowledge_base, "NEX_ARTICLES_CSV", articles_csv)

    with pytest.raises(ValueError, match="Unknown member_email"):
        hrn_knowledge_base.get_research_articles_data()
