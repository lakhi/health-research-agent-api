from pathlib import Path
from typing import IO, Any, List, Optional, Union

from agno.agent import Agent
from agno.knowledge.document.base import Document
from agno.knowledge.reader.docx_reader import DocxReader
from agno.knowledge.reader.pdf_reader import PDFReader

from agents.ssc_psych_agent import get_ssc_psych_agent
from api.project_configs.project_config import ProjectConfig, ProjectName


def _drop_blank_documents(documents: List[Document]) -> List[Document]:
    """Blank documents (image-only pages, empty chunks) 400 against the Azure
    embedder and would land in the vector table without embeddings."""
    return [doc for doc in documents if doc.content and doc.content.strip()]


class NonEmptyPDFReader(PDFReader):
    """PDFReader that drops blank documents before they reach the embedder."""

    def read(
        self,
        pdf: Union[str, Path, IO[Any], None] = None,
        name: Optional[str] = None,
        password: Optional[str] = None,
    ) -> List[Document]:
        return _drop_blank_documents(super().read(pdf=pdf, name=name, password=password))

    async def async_read(
        self,
        pdf: Union[str, Path, IO[Any], None] = None,
        name: Optional[str] = None,
        password: Optional[str] = None,
    ) -> List[Document]:
        return _drop_blank_documents(await super().async_read(pdf=pdf, name=name, password=password))


class NonEmptyDocxReader(DocxReader):
    """DocxReader that drops blank documents before they reach the embedder."""

    def read(self, file: Union[Path, IO[Any]], name: Optional[str] = None) -> List[Document]:
        return _drop_blank_documents(super().read(file, name=name))

    async def async_read(self, file: Union[Path, IO[Any]], name: Optional[str] = None) -> List[Document]:
        return _drop_blank_documents(await super().async_read(file, name=name))


class SscPsychConfig(ProjectConfig):
    """Configuration for the SSC Psychologie project."""

    @property
    def project_name(self) -> str:
        return ProjectName.SSC_PSYCH.value

    @property
    def cors_origins(self) -> List[str]:
        # TBD — Azure Container App UI URL added once provisioned
        return []

    def get_agents(self) -> List[Agent]:
        """Initialize SSC Psychologie agent."""
        return [get_ssc_psych_agent()]

    async def load_knowledge(self, agents: List[Agent]) -> None:
        """Load SSC Psychologie knowledge from website scraping into the agent."""
        import os

        load_knowledge = os.environ.get("LOAD_SSC_PSYCH_KNOWLEDGE", "true").lower() == "true"
        if not load_knowledge:
            print("⏭️  Skipping SSC Psych knowledge loading (LOAD_SSC_PSYCH_KNOWLEDGE=false)")
            return

        from agno.knowledge.chunking.semantic import SemanticChunking

        from services.ssc_web_scraper import scrape_ssc_downloads, scrape_ssc_web_pages

        pdf_reader = NonEmptyPDFReader(
            chunking_strategy=SemanticChunking(
                embedder="minishlab/potion-base-32M",
                chunk_size=2000,
                similarity_threshold=0.5,
                similarity_window=3,
            )
        )
        # Default DocumentChunking is appropriate for forms/templates (short, structured)
        docx_reader = NonEmptyDocxReader()

        try:
            ssc_agent = agents[0]

            # Load web pages from SSC website
            web_pages = scrape_ssc_web_pages()
            for i, item in enumerate(web_pages, 1):
                print(f"  [{i}/{len(web_pages)}] Embedding web page: {item['name']}")
                await ssc_agent.knowledge.ainsert(
                    name=item["name"],
                    text_content=item["text_content"],
                    metadata=item["metadata"],
                    skip_if_exists=True,
                )
            print(f"✅ Web pages loaded ({len(web_pages)} pages)")

            # Load PDF and Word documents from SSC downloads section
            docs = scrape_ssc_downloads()
            for i, item in enumerate(docs, 1):
                if "text_content" in item:
                    # Password-locked PDF: embed the download stub so the agent
                    # can still cite the form's URL.
                    print(f"  [{i}/{len(docs)}] Embedding download stub: {item['name']}")
                    await ssc_agent.knowledge.ainsert(
                        name=item["name"],
                        text_content=item["text_content"],
                        metadata=item["metadata"],
                        skip_if_exists=True,
                    )
                    continue
                is_pdf = str(item["path"]).lower().endswith(".pdf")
                reader = pdf_reader if is_pdf else docx_reader
                file_type = "PDF" if is_pdf else "Word doc"
                print(f"  [{i}/{len(docs)}] Embedding {file_type}: {item['name']}")
                await ssc_agent.knowledge.ainsert(
                    name=item["name"],
                    path=str(item["path"]),
                    reader=reader,
                    metadata=item["metadata"],
                    skip_if_exists=True,
                )
            print(f"✅ Documents loaded ({len(docs)} total)")

        except Exception as e:
            print(f"❌ Error loading SSC Psych knowledge: {e}")
            raise
