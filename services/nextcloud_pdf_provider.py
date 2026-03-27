"""Discovers and downloads research PDFs from a Nextcloud public share."""

import tempfile
from dataclasses import dataclass
from pathlib import Path

from services.nextcloud_client import NextcloudClient


@dataclass
class DiscoveredPDF:
    local_path: Path
    member_folder_name: str
    filename: str


class NextcloudPDFProvider:
    """Discovers member folders and downloads their PDFs to a temp directory."""

    def __init__(self, client: NextcloudClient):
        self._client = client

    async def discover_and_download(self) -> tuple[list[DiscoveredPDF], Path]:
        """Discover all member PDFs and download them to a temp directory.

        Returns:
            (discovered_pdfs, temp_dir) — caller is responsible for cleaning up temp_dir.
        """
        temp_dir = Path(tempfile.mkdtemp(prefix="nex_pdfs_"))
        discovered: list[DiscoveredPDF] = []

        folders = await self._client.list_folders("/")
        for folder in folders:
            pdf_files = await self._client.list_files(f"/{folder}")
            for filename in pdf_files:
                local_path = temp_dir / folder / filename
                await self._client.download_file(f"/{folder}/{filename}", local_path)
                discovered.append(
                    DiscoveredPDF(
                        local_path=local_path,
                        member_folder_name=folder,
                        filename=filename,
                    )
                )

        return discovered, temp_dir
