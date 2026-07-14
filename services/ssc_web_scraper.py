"""
Web scraper for the SSC Psychologie website.

Crawls pages under https://ssc-psychologie.univie.ac.at/studium/ and
downloads PDF documents from https://ssc-psychologie.univie.ac.at/downloads/.
Preserves source URLs as metadata so the agent can cite them in responses.
"""

import hashlib
import logging
import tempfile
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader, PdfWriter

logger = logging.getLogger(__name__)

BASE_URL = "https://ssc-psychologie.univie.ac.at"
STUDIUM_PATHS = ["/studium/", "/en/studium/"]
DOWNLOADS_PATHS = ["/downloads/", "/en/downloads/"]
REQUEST_DELAY_SECONDS = 0.5
REQUEST_TIMEOUT_SECONDS = 30
DOWNLOAD_RETRY_ATTEMPTS = 3
USER_AGENT = "UniVie-SSC-Psych-Agent/1.0 (research chatbot; +https://ssc-psychologie.univie.ac.at/)"


def _get_session() -> requests.Session:
    """Create a requests session with appropriate headers."""
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def _download_with_retry(session: requests.Session, url: str) -> Optional[requests.Response]:
    """GET with retries — the SSC file server occasionally aborts connections."""
    for attempt in range(1, DOWNLOAD_RETRY_ATTEMPTS + 1):
        try:
            time.sleep(REQUEST_DELAY_SECONDS)
            response = session.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            if attempt < DOWNLOAD_RETRY_ATTEMPTS:
                logger.info(f"Download attempt {attempt}/{DOWNLOAD_RETRY_ATTEMPTS} failed for {url}: {e} — retrying")
            else:
                logger.warning(f"Failed to download {url} after {DOWNLOAD_RETRY_ATTEMPTS} attempts: {e}")
    return None


def _unlock_pdf_in_place(path: Path) -> bool:
    """True when the PDF at `path` is readable, decrypting it in place if needed.

    The SSC forms are owner-locked (edit restrictions, empty user password) —
    pypdf opens those with decrypt(""). False means a real user password (or an
    unparseable file): the content is unreachable and the caller should embed a
    download stub instead.
    """
    try:
        reader = PdfReader(str(path))
        if not reader.is_encrypted:
            return True
        if not reader.decrypt(""):
            return False
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        with path.open("wb") as fh:
            writer.write(fh)
        logger.info(f"Decrypted owner-locked PDF: {path.name}")
        return True
    except Exception as e:
        logger.warning(f"Could not unlock PDF {path.name}: {e}")
        return False


def _is_internal_link(url: str, allowed_prefixes: list[str]) -> bool:
    """Check if a URL is an internal link within the allowed path prefixes."""
    parsed = urlparse(url)
    if parsed.netloc and parsed.netloc != urlparse(BASE_URL).netloc:
        return False
    path = parsed.path
    return any(path.startswith(prefix) for prefix in allowed_prefixes)


def _detect_language(url: str) -> str:
    """Detect language from URL path. /en/ prefix = English, otherwise German."""
    return "en" if "/en/" in urlparse(url).path else "de"


def _extract_main_content(soup: BeautifulSoup) -> str:
    """
    Extract the main content text from an SSC page, stripping navigation,
    footer, and sidebar elements.
    """
    # Try common content area selectors for TYPO3 (used by univie.ac.at)
    content_selectors = [
        "div.content-main",
        "div#content",
        "main",
        "article",
        "div.tx-felogin-pi1",  # fallback
    ]

    content_area = None
    for selector in content_selectors:
        content_area = soup.select_one(selector)
        if content_area:
            break

    if not content_area:
        # Fallback: use the body but strip known non-content elements
        content_area = soup.find("body")

    if not content_area:
        return ""

    # Remove navigation, footer, sidebar elements
    for tag in content_area.select("nav, footer, .nav, .footer, .sidebar, .breadcrumb, script, style, noscript"):
        tag.decompose()

    text = content_area.get_text(separator="\n", strip=True)
    # Collapse multiple blank lines
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _extract_page_title(soup: BeautifulSoup) -> str:
    """Extract page title from h1 or title tag."""
    h1 = soup.find("h1")
    if h1:
        return h1.get_text(strip=True)
    title = soup.find("title")
    if title:
        return title.get_text(strip=True)
    return "Untitled"


def _content_hash(text: str) -> str:
    """Generate SHA-256 hash of content for deduplication."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def scrape_ssc_web_pages() -> list[dict]:
    """
    Crawl all pages under the SSC Psychologie /studium/ section (German + English).

    Returns a list of dicts, each with:
        - name: Document name for the knowledge base
        - text_content: Extracted page text
        - metadata: Dict with source_type, source_url, page_title, language, content_hash
    """
    session = _get_session()
    visited: set[str] = set()
    results: list[dict] = []

    # Build initial queue from both German and English entry points
    queue: list[str] = [f"{BASE_URL}{path}" for path in STUDIUM_PATHS]
    allowed_prefixes = STUDIUM_PATHS.copy()

    while queue:
        url = queue.pop(0)

        # Normalize URL (strip fragment, ensure trailing consistency)
        parsed = urlparse(url)
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if normalized in visited:
            continue
        visited.add(normalized)

        try:
            time.sleep(REQUEST_DELAY_SECONDS)
            response = session.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
        except requests.RequestException as e:
            logger.warning(f"Failed to fetch {url}: {e}")
            continue

        if "text/html" not in response.headers.get("content-type", ""):
            continue

        soup = BeautifulSoup(response.text, "html.parser")
        title = _extract_page_title(soup)
        content = _extract_main_content(soup)

        if not content or len(content) < 50:
            logger.debug(f"Skipping {url} — insufficient content ({len(content)} chars)")
            continue

        language = _detect_language(url)
        results.append(
            {
                "name": f"SSC Page - {title}",
                "text_content": content,
                "metadata": {
                    "source_type": "web_page",
                    "source_url": normalized,
                    "page_title": title,
                    "language": language,
                    "content_hash": _content_hash(content),
                },
            }
        )
        logger.info(f"Scraped: {title} ({language}) — {normalized}")

        # Discover internal links within /studium/
        for link in soup.find_all("a", href=True):
            href = link["href"]
            full_url = urljoin(url, href)
            full_parsed = urlparse(full_url)
            full_normalized = f"{full_parsed.scheme}://{full_parsed.netloc}{full_parsed.path}"

            if full_normalized not in visited and _is_internal_link(full_url, allowed_prefixes):
                queue.append(full_url)

    logger.info(f"Scraped {len(results)} web pages from SSC Psychologie website")
    return results


def scrape_ssc_downloads() -> list[dict]:
    """
    Scrape the SSC Psychologie /downloads/ section and download all linked PDFs and Word docs.

    The TYPO3 filelist extension serves every folder view at /downloads/ with a
    tx_filelist_filelist[path] query param. Both the visited-page key and the link-dedup
    key must include the query string, otherwise all subfolder pages collapse to the same
    normalized path and are skipped after the first visit.

    Returns a list of dicts, each with:
        - name: Document name for the knowledge base
        - path: Path to the downloaded file
        - metadata: Dict with source_type, source_url, document_title, language
    """
    session = _get_session()
    visited_pages: set[str] = set()
    doc_urls: set[str] = set()
    results: list[dict] = []

    # Crawl /downloads/ pages to find document links
    queue: list[str] = [f"{BASE_URL}{path}" for path in DOWNLOADS_PATHS]
    allowed_prefixes = DOWNLOADS_PATHS.copy()

    while queue:
        url = queue.pop(0)
        parsed = urlparse(url)
        # Include query string — TYPO3 folder nav uses tx_filelist_filelist[path] params
        qs = f"?{parsed.query}" if parsed.query else ""
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}{qs}"

        if normalized in visited_pages:
            continue
        visited_pages.add(normalized)

        try:
            time.sleep(REQUEST_DELAY_SECONDS)
            response = session.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
        except requests.RequestException as e:
            logger.warning(f"Failed to fetch {url}: {e}")
            continue

        if "text/html" not in response.headers.get("content-type", ""):
            continue

        soup = BeautifulSoup(response.text, "html.parser")

        # Collect PDF and Word document links
        for link in soup.find_all("a", href=True):
            href = link["href"]
            full_url = urljoin(url, href)

            if full_url.lower().endswith((".pdf", ".docx")):
                doc_urls.add(full_url)

            # Follow internal links within /downloads/ (includes query-param subfolder pages)
            full_parsed = urlparse(full_url)
            full_qs = f"?{full_parsed.query}" if full_parsed.query else ""
            full_normalized = f"{full_parsed.scheme}://{full_parsed.netloc}{full_parsed.path}{full_qs}"
            if full_normalized not in visited_pages and _is_internal_link(full_url, allowed_prefixes):
                queue.append(full_url)

    # Download documents to temp directory
    if not doc_urls:
        logger.warning("No documents found on SSC downloads pages")
        return results

    # Fixed path (not mkdtemp): agno's skip_if_exists hashes the file *path*, so a
    # random temp dir per run defeats dedup and re-embeds every document on restart.
    tmp_dir = Path(tempfile.gettempdir()) / "ssc_psych_pdfs"
    tmp_dir.mkdir(exist_ok=True)
    logger.info(f"Downloading {len(doc_urls)} documents to {tmp_dir}")

    for doc_url in sorted(doc_urls):
        parsed = urlparse(doc_url)
        filename = Path(parsed.path).name

        if not filename:
            continue

        response = _download_with_retry(session, doc_url)
        if response is None:
            continue

        local_path = tmp_dir / filename
        local_path.write_bytes(response.content)

        filename_lower = filename.lower()
        source_type = "pdf_document" if filename_lower.endswith(".pdf") else "word_document"
        # Derive a human-readable title from the filename (strip extension)
        document_title = filename.rsplit(".", 1)[0].replace("_", " ").replace("-", " ")
        # Simple language heuristic: filenames containing _E_ or ending with E.pdf/E.docx are English
        language = (
            "en" if ("_E_" in filename or filename_lower.endswith(("e.pdf", "e.docx", "_en.pdf", "_en.docx"))) else "de"
        )
        file_label = "PDF" if source_type == "pdf_document" else "DOCX"

        item: dict = {
            "name": f"SSC {file_label} - {document_title}",
            "metadata": {
                "source_type": source_type,
                "source_url": doc_url,
                "document_title": document_title,
                "language": language,
            },
        }
        if source_type == "pdf_document" and not _unlock_pdf_in_place(local_path):
            # Content is unreachable, but the agent must still be able to cite
            # the download link when a page tells students to fetch this form.
            item["text_content"] = (
                f"{document_title}: Dieses Formular ist als geschütztes PDF verfügbar; "
                f"Download unter {doc_url}. / This form is available as a protected PDF; "
                f"download it at {doc_url}."
            )
            logger.warning(f"Password-protected PDF (no empty-password unlock): {filename} — embedding download stub")
        else:
            item["path"] = local_path

        results.append(item)
        logger.info(f"Downloaded: {filename} → {doc_url}")

    logger.info(f"Downloaded {len(results)} documents from SSC Psychologie website")
    return results
