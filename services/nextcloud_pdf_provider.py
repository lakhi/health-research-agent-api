"""Lists research PDFs on a Nextcloud public share and downloads the ones asked for."""

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path

import httpx

from services.nextcloud_client import NextcloudClient, RemoteEntry

logger = logging.getLogger(__name__)

_MAX_DOWNLOAD_RETRIES = 3
_RETRY_BASE_DELAY_S = 2.0  # doubles each attempt: 2s, 4s, 8s

DEFAULT_DOWNLOAD_DIR = Path("/app/hex_gig_pdfs_cache")


@dataclass(frozen=True)
class RemotePDF:
    """A PDF on the share: the member folder it sits in, its name, and its listed properties."""

    member_folder_name: str
    filename: str
    entry: RemoteEntry

    @property
    def remote_path(self) -> str:
        """Where the file lives on the share, which is also its stable identity across runs."""
        return f"{self.member_folder_name}/{self.filename}"


class NextcloudPDFProvider:
    """Lists every member folder's PDFs without downloading them; downloads on request.

    Listing first lets the caller download only what is new or changed. A listing failure raises
    rather than returning a partial list, because a caller comparing the listing against stored
    documents would otherwise read every PDF in an unlisted folder as deleted.
    """

    def __init__(self, client: NextcloudClient, download_dir: Path = DEFAULT_DOWNLOAD_DIR):
        self._client = client
        self._download_dir = download_dir

    async def discover(self) -> list[RemotePDF]:
        """List the PDFs in every member folder of the share."""
        discovered: list[RemotePDF] = []
        for folder in await self._client.list_folders("/"):
            for entry in await self._client.list_pdf_entries(f"/{folder}"):
                discovered.append(RemotePDF(member_folder_name=folder, filename=entry.name, entry=entry))
        return discovered

    async def download(self, pdf: RemotePDF) -> Path:
        """Download a PDF to a deterministic local path, replacing any older copy there.

        The path is deterministic because agno folds it into the content hash; the file is always
        fetched because it is only asked for when the share's copy is new or has changed.
        """
        local_path = self._download_dir / pdf.member_folder_name / pdf.filename
        for attempt in range(1, _MAX_DOWNLOAD_RETRIES + 1):
            try:
                await self._client.download_file(f"/{pdf.remote_path}", local_path)
                logger.info("Downloaded: %s", pdf.remote_path)
                return local_path
            except (httpx.RemoteProtocolError, httpx.ConnectError, httpx.ReadError) as exc:
                if attempt == _MAX_DOWNLOAD_RETRIES:
                    raise
                delay = _RETRY_BASE_DELAY_S * (2 ** (attempt - 1))
                logger.warning(
                    "Download failed (%s), attempt %d/%d — retrying in %.0fs: %s",
                    pdf.remote_path,
                    attempt,
                    _MAX_DOWNLOAD_RETRIES,
                    delay,
                    exc,
                )
                await asyncio.sleep(delay)
        raise AssertionError("unreachable")  # pragma: no cover - the loop always returns or raises
