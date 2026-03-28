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
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://ssc-psychologie.univie.ac.at"
STUDIUM_PATHS = ["/studium/", "/en/studium/"]
DOWNLOADS_PATHS = ["/downloads/", "/en/downloads/"]
REQUEST_DELAY_SECONDS = 0.5
REQUEST_TIMEOUT_SECONDS = 30
USER_AGENT = "UniVie-SSC-Psych-Agent/1.0 (research chatbot; +https://ssc-psychologie.univie.ac.at/)"


def _get_session() -> requests.Session:
    """Create a requests session with appropriate headers."""
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    return session


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
    Scrape the SSC Psychologie /downloads/ section and download all linked PDFs.

    Returns a list of dicts, each with:
        - name: Document name for the knowledge base
        - path: Path to the downloaded PDF file
        - metadata: Dict with source_type, source_url, document_title
    """
    session = _get_session()
    visited_pages: set[str] = set()
    pdf_urls: set[str] = set()
    results: list[dict] = []

    # Crawl /downloads/ pages to find PDF links
    queue: list[str] = [f"{BASE_URL}{path}" for path in DOWNLOADS_PATHS]
    allowed_prefixes = DOWNLOADS_PATHS.copy()

    while queue:
        url = queue.pop(0)
        parsed = urlparse(url)
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

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

        # Collect PDF links
        for link in soup.find_all("a", href=True):
            href = link["href"]
            full_url = urljoin(url, href)

            if full_url.lower().endswith(".pdf"):
                pdf_urls.add(full_url)

            # Follow internal links within /downloads/
            full_parsed = urlparse(full_url)
            full_normalized = f"{full_parsed.scheme}://{full_parsed.netloc}{full_parsed.path}"
            if full_normalized not in visited_pages and _is_internal_link(full_url, allowed_prefixes):
                queue.append(full_url)

    # Download PDFs to temp directory
    if not pdf_urls:
        logger.warning("No PDF links found on SSC downloads pages")
        return results

    tmp_dir = Path(tempfile.mkdtemp(prefix="ssc_psych_pdfs_"))
    logger.info(f"Downloading {len(pdf_urls)} PDFs to {tmp_dir}")

    for pdf_url in sorted(pdf_urls):
        parsed = urlparse(pdf_url)
        filename = Path(parsed.path).name

        if not filename:
            continue

        try:
            time.sleep(REQUEST_DELAY_SECONDS)
            response = session.get(pdf_url, timeout=REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
        except requests.RequestException as e:
            logger.warning(f"Failed to download {pdf_url}: {e}")
            continue

        local_path = tmp_dir / filename
        local_path.write_bytes(response.content)

        # Derive a human-readable title from the filename
        document_title = filename.replace(".pdf", "").replace("_", " ").replace("-", " ")

        results.append(
            {
                "name": f"SSC PDF - {document_title}",
                "path": local_path,
                "metadata": {
                    "source_type": "pdf_document",
                    "source_url": pdf_url,
                    "document_title": document_title,
                },
            }
        )
        logger.info(f"Downloaded: {filename} ��� {pdf_url}")

    logger.info(f"Downloaded {len(results)} PDFs from SSC Psychologie website")
    return results
