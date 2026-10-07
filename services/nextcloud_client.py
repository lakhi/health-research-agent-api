"""Async WebDAV client for Nextcloud public folder shares."""

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, unquote

import httpx

DAV_NS = "DAV:"
_NS = {"d": DAV_NS}


@dataclass(frozen=True)
class RemoteEntry:
    """One file or folder in a share listing, with the properties that change when a file does."""

    name: str
    is_dir: bool
    etag: str = ""
    size: int | None = None
    last_modified: str = ""

    @property
    def fingerprint(self) -> str:
        """Changes whenever the file's content does: the ETag, else size and modification time."""
        return self.etag or f"{self.size}:{self.last_modified}"


class NextcloudClient:
    """WebDAV client for accessing files in a Nextcloud public folder share.

    Uses the public WebDAV endpoint (no personal credentials needed):
        https://<host>/public.php/webdav/
    Auth: Basic Auth with share_token as username, share_password as password.
    """

    def __init__(self, webdav_public_url: str, share_token: str, share_password: str = ""):
        self._base_url = webdav_public_url.rstrip("/")
        self._auth = httpx.BasicAuth(share_token, share_password)

    async def list_entries(self, path: str = "/") -> list[RemoteEntry]:
        """List the files and folders directly under a path via PROPFIND depth=1.

        The listed folder itself is left out. Any HTTP error raises: a caller that compares this
        listing against what it has stored must never mistake a failed listing for an empty one.
        """
        xml_body = await self._propfind(path)
        root = ET.fromstring(xml_body)
        own_name = path.strip("/").split("/")[-1] if path.strip("/") else "webdav"

        entries: list[RemoteEntry] = []
        for response in root.findall("d:response", _NS):
            href = response.find("d:href", _NS)
            if href is None or href.text is None:
                continue

            propstat = response.find("d:propstat", _NS)
            if propstat is None:
                continue
            prop = propstat.find("d:prop", _NS)
            if prop is None:
                continue

            name = unquote(href.text.rstrip("/").split("/")[-1])
            resource_type = prop.find("d:resourcetype", _NS)
            is_dir = resource_type is not None and resource_type.find("d:collection", _NS) is not None
            if not name or (is_dir and name == own_name):
                continue

            size_text = (prop.findtext("d:getcontentlength", default="", namespaces=_NS) or "").strip()
            entries.append(
                RemoteEntry(
                    name=name,
                    is_dir=is_dir,
                    etag=(prop.findtext("d:getetag", default="", namespaces=_NS) or "").strip().strip('"'),
                    size=int(size_text) if size_text.isdigit() else None,
                    last_modified=(prop.findtext("d:getlastmodified", default="", namespaces=_NS) or "").strip(),
                )
            )

        return entries

    async def list_folders(self, path: str = "/") -> list[str]:
        """List sub-folder names at the given path via PROPFIND depth=1."""
        return [entry.name for entry in await self.list_entries(path) if entry.is_dir]

    async def list_files(self, path: str, extension: str = ".pdf") -> list[str]:
        """List filenames at the given path, filtered by extension."""
        return [entry.name for entry in await self.list_pdf_entries(path, extension)]

    async def list_pdf_entries(self, path: str, extension: str = ".pdf") -> list[RemoteEntry]:
        """List the files at the given path whose names end with the extension."""
        ext_lower = extension.lower()
        return [
            entry
            for entry in await self.list_entries(path)
            if not entry.is_dir and entry.name.lower().endswith(ext_lower)
        ]

    async def download_file(self, remote_path: str, local_path: Path) -> Path:
        """Download a file from the share to a local path."""
        encoded_path = "/".join(quote(segment, safe="") for segment in remote_path.strip("/").split("/"))
        url = f"{self._base_url}/{encoded_path}"

        local_path.parent.mkdir(parents=True, exist_ok=True)

        async with httpx.AsyncClient(auth=self._auth, timeout=120.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            local_path.write_bytes(response.content)

        return local_path

    async def _propfind(self, path: str) -> str:
        """Send a PROPFIND request and return the XML response body."""
        encoded_path = (
            "/".join(quote(segment, safe="") for segment in path.strip("/").split("/")) if path.strip("/") else ""
        )
        url = f"{self._base_url}/{encoded_path}" if encoded_path else f"{self._base_url}/"

        async with httpx.AsyncClient(auth=self._auth, timeout=30.0, follow_redirects=True) as client:
            response = await client.request("PROPFIND", url, headers={"Depth": "1"})
            response.raise_for_status()
            return response.text
