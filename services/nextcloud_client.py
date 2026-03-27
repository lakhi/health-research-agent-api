"""Async WebDAV client for Nextcloud public folder shares."""

import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote, unquote

import httpx

DAV_NS = "DAV:"
_NS = {"d": DAV_NS}


class NextcloudClient:
    """WebDAV client for accessing files in a Nextcloud public folder share.

    Uses the public WebDAV endpoint (no personal credentials needed):
        https://<host>/public.php/webdav/
    Auth: Basic Auth with share_token as username, share_password as password.
    """

    def __init__(self, webdav_public_url: str, share_token: str, share_password: str = ""):
        self._base_url = webdav_public_url.rstrip("/")
        self._auth = httpx.BasicAuth(share_token, share_password)

    async def list_folders(self, path: str = "/") -> list[str]:
        """List sub-folder names at the given path via PROPFIND depth=1."""
        xml_body = await self._propfind(path)
        root = ET.fromstring(xml_body)

        folders: list[str] = []
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
            resource_type = prop.find("d:resourcetype", _NS)
            if resource_type is None:
                continue
            if resource_type.find("d:collection", _NS) is None:
                continue

            name = unquote(href.text.rstrip("/").split("/")[-1])
            if name and name != "webdav":
                folders.append(name)

        return folders

    async def list_files(self, path: str, extension: str = ".pdf") -> list[str]:
        """List filenames at the given path, filtered by extension."""
        xml_body = await self._propfind(path)
        root = ET.fromstring(xml_body)

        files: list[str] = []
        ext_lower = extension.lower()
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
            resource_type = prop.find("d:resourcetype", _NS)
            # Skip collections (folders)
            if resource_type is not None and resource_type.find("d:collection", _NS) is not None:
                continue

            name = unquote(href.text.rstrip("/").split("/")[-1])
            if name and name.lower().endswith(ext_lower):
                files.append(name)

        return files

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
