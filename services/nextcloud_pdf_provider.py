"""Discovers and downloads research PDFs from a Nextcloud public share."""

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path

import httpx

from services.nextcloud_client import NextcloudClient

logger = logging.getLogger(__name__)

_MAX_DOWNLOAD_RETRIES = 3
_RETRY_BASE_DELAY_S = 2.0  # doubles each attempt: 2s, 4s, 8s

DEFAULT_DOWNLOAD_DIR = Path("/app/nex_pdfs_cache")


@dataclass
class DiscoveredPDF:
    local_path: Path
    member_folder_name: str
    filename: str


class NextcloudPDFProvider:
    """Discovers member folders and downloads their PDFs to a local directory.

    Uses a deterministic download path so that files persist across restarts
    and agno's skip_if_exists content hash remains stable.
    """

    def __init__(self, client: NextcloudClient, download_dir: Path = DEFAULT_DOWNLOAD_DIR):
        self._client = client
        self._download_dir = download_dir

    async def discover_and_download(self) -> list[DiscoveredPDF]:
        """Discover all member PDFs. Only downloads files not already present locally.

        Returns:
            List of DiscoveredPDF objects (both newly downloaded and already-cached).
        """
        self._download_dir.mkdir(parents=True, exist_ok=True)
        discovered: list[DiscoveredPDF] = []

        folders = await self._client.list_folders("/")
        for folder in folders:
            pdf_files = await self._client.list_files(f"/{folder}")
            for filename in pdf_files:
                local_path = self._download_dir / folder / filename
                if not local_path.exists():
                    for attempt in range(1, _MAX_DOWNLOAD_RETRIES + 1):
                        try:
                            await self._client.download_file(f"/{folder}/{filename}", local_path)
                            logger.info("Downloaded: %s/%s", folder, filename)
                            break
                        except (httpx.RemoteProtocolError, httpx.ConnectError, httpx.ReadError) as exc:
                            if attempt == _MAX_DOWNLOAD_RETRIES:
                                raise
                            delay = _RETRY_BASE_DELAY_S * (2 ** (attempt - 1))
                            logger.warning(
                                "Download failed (%s/%s), attempt %d/%d — retrying in %.0fs: %s",
                                folder,
                                filename,
                                attempt,
                                _MAX_DOWNLOAD_RETRIES,
                                delay,
                                exc,
                            )
                            await asyncio.sleep(delay)
                discovered.append(
                    DiscoveredPDF(
                        local_path=local_path,
                        member_folder_name=folder,
                        filename=filename,
                    )
                )

        return discovered
