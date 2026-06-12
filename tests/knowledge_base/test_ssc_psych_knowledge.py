"""
Unit tests for the SSC Psychologie web scraper.

Tests URL parsing, content extraction, metadata schema, and language detection.
Run with: pytest tests/knowledge_base/test_ssc_psych_knowledge.py -v
"""

from unittest.mock import MagicMock, patch

from services.ssc_web_scraper import (
    _content_hash,
    _detect_language,
    _extract_main_content,
    _extract_page_title,
    _is_internal_link,
)


class TestLanguageDetection:
    """Tests for URL-based language detection."""

    def test_german_url(self):
        assert _detect_language("https://ssc-psychologie.univie.ac.at/studium/") == "de"

    def test_english_url(self):
        assert _detect_language("https://ssc-psychologie.univie.ac.at/en/studium/") == "en"

    def test_german_downloads(self):
        assert _detect_language("https://ssc-psychologie.univie.ac.at/downloads/") == "de"

    def test_english_downloads(self):
        assert _detect_language("https://ssc-psychologie.univie.ac.at/en/downloads/") == "en"

    def test_nested_path_german(self):
        assert _detect_language("https://ssc-psychologie.univie.ac.at/studium/bachelorstudium/") == "de"


class TestInternalLinkDetection:
    """Tests for internal link filtering."""

    def test_internal_studium_link(self):
        assert _is_internal_link(
            "https://ssc-psychologie.univie.ac.at/studium/bachelorstudium/",
            ["/studium/"],
        )

    def test_external_link_rejected(self):
        assert not _is_internal_link(
            "https://www.univie.ac.at/some-other-page/",
            ["/studium/"],
        )

    def test_root_link_rejected(self):
        assert not _is_internal_link(
            "https://ssc-psychologie.univie.ac.at/",
            ["/studium/"],
        )

    def test_downloads_link_accepted(self):
        assert _is_internal_link(
            "https://ssc-psychologie.univie.ac.at/downloads/dissertation/",
            ["/downloads/"],
        )

    def test_english_studium_link(self):
        assert _is_internal_link(
            "https://ssc-psychologie.univie.ac.at/en/studium/bachelor/",
            ["/en/studium/"],
        )


class TestContentExtraction:
    """Tests for page content extraction."""

    def test_extracts_from_content_main(self):
        from bs4 import BeautifulSoup

        html = """
        <html><body>
            <nav>Navigation</nav>
            <div class="content-main"><p>Main content here</p></div>
            <footer>Footer</footer>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        content = _extract_main_content(soup)
        assert "Main content here" in content
        assert "Navigation" not in content
        assert "Footer" not in content

    def test_extracts_page_title_from_h1(self):
        from bs4 import BeautifulSoup

        html = "<html><head><title>Page Title</title></head><body><h1>H1 Title</h1></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        assert _extract_page_title(soup) == "H1 Title"

    def test_falls_back_to_title_tag(self):
        from bs4 import BeautifulSoup

        html = "<html><head><title>Page Title</title></head><body><p>No h1</p></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        assert _extract_page_title(soup) == "Page Title"


class TestContentHash:
    """Tests for content deduplication hashing."""

    def test_same_content_same_hash(self):
        assert _content_hash("hello world") == _content_hash("hello world")

    def test_different_content_different_hash(self):
        assert _content_hash("hello") != _content_hash("world")

    def test_hash_is_hex_string(self):
        h = _content_hash("test")
        assert len(h) == 64  # SHA-256 produces 64 hex characters
        assert all(c in "0123456789abcdef" for c in h)


class TestScrapeWebPages:
    """Tests for the full web scraping pipeline (mocked HTTP)."""

    @patch("services.ssc_web_scraper._get_session")
    @patch("services.ssc_web_scraper.time.sleep")  # Skip delays in tests
    def test_scrape_returns_correct_metadata_schema(self, mock_sleep, mock_session):
        """Scraped pages should have the expected metadata keys."""
        from services.ssc_web_scraper import scrape_ssc_web_pages

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html; charset=utf-8"}
        mock_response.text = """
        <html><head><title>Bachelorstudium</title></head>
        <body>
            <h1>Bachelorstudium Psychologie</h1>
            <div class="content-main">
                <p>Das Bachelorstudium Psychologie vermittelt grundlegende Kenntnisse
                und Kompetenzen in den zentralen Bereichen der Psychologie als Wissenschaft.</p>
            </div>
        </body></html>
        """
        mock_response.raise_for_status = MagicMock()

        session = MagicMock()
        session.get.return_value = mock_response
        mock_session.return_value = session

        results = scrape_ssc_web_pages()

        assert len(results) > 0
        first = results[0]
        assert "name" in first
        assert "text_content" in first
        assert "metadata" in first

        meta = first["metadata"]
        assert meta["source_type"] == "web_page"
        assert "source_url" in meta
        assert "page_title" in meta
        assert meta["language"] in ("de", "en")
        assert "content_hash" in meta


class TestScrapeDownloads:
    """Regression tests for issue #38 — subfolder traversal and Word-doc support
    in scrape_ssc_downloads (mocked HTTP)."""

    ROOT_HTML = """
    <html><body><div class="content-main">
        <a href="/downloads/?tx_filelist_filelist%5Bpath%5D=%2FDissertation%2F">Dissertation</a>
        <a href="/fileadmin/root_form.pdf">Root Form</a>
        <a href="/fileadmin/Vorlage_KI-Verwendungserklaerung.docx">KI Vorlage</a>
    </div></body></html>
    """
    SUBFOLDER_HTML = """
    <html><body><div class="content-main">
        <a href="/fileadmin/diss_registration.pdf">Diss Registration</a>
    </div></body></html>
    """
    EMPTY_HTML = "<html><body><div class='content-main'></div></body></html>"

    def _fake_session(self):
        def fake_get(url, timeout=None):
            response = MagicMock()
            response.raise_for_status = MagicMock()
            if url.lower().endswith((".pdf", ".docx")):
                response.headers = {"content-type": "application/octet-stream"}
                response.content = b"fake file bytes"
            else:
                response.headers = {"content-type": "text/html; charset=utf-8"}
                if "tx_filelist_filelist" in url:
                    response.text = self.SUBFOLDER_HTML
                elif "/en/downloads/" in url:
                    response.text = self.EMPTY_HTML
                else:
                    response.text = self.ROOT_HTML
            return response

        session = MagicMock()
        session.get.side_effect = fake_get
        return session

    @patch("services.ssc_web_scraper._get_session")
    @patch("services.ssc_web_scraper.time.sleep")
    def test_subfolder_pages_are_traversed(self, mock_sleep, mock_session):
        """Bug 1: query-param subfolder pages must not collapse into the root visited key."""
        from services.ssc_web_scraper import scrape_ssc_downloads

        mock_session.return_value = self._fake_session()
        results = scrape_ssc_downloads()

        urls = {r["metadata"]["source_url"] for r in results}
        assert any(u.endswith("diss_registration.pdf") for u in urls), (
            "PDF linked only from the tx_filelist subfolder page was not collected"
        )

    @patch("services.ssc_web_scraper._get_session")
    @patch("services.ssc_web_scraper.time.sleep")
    def test_docx_files_are_collected(self, mock_sleep, mock_session):
        """Bug 2: .docx links must be downloaded and tagged as word_document."""
        from services.ssc_web_scraper import scrape_ssc_downloads

        mock_session.return_value = self._fake_session()
        results = scrape_ssc_downloads()

        docx = [r for r in results if str(r["path"]).endswith(".docx")]
        assert len(docx) == 1
        assert docx[0]["metadata"]["source_type"] == "word_document"
        assert "DOCX" in docx[0]["name"]

    @patch("services.ssc_web_scraper._get_session")
    @patch("services.ssc_web_scraper.time.sleep")
    def test_pdfs_keep_pdf_metadata(self, mock_sleep, mock_session):
        from services.ssc_web_scraper import scrape_ssc_downloads

        mock_session.return_value = self._fake_session()
        results = scrape_ssc_downloads()

        pdfs = [r for r in results if str(r["path"]).endswith(".pdf")]
        assert len(pdfs) == 2
        assert all(r["metadata"]["source_type"] == "pdf_document" for r in pdfs)
