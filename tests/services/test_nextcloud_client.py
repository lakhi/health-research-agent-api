"""Tests for NextcloudClient WebDAV XML parsing."""

import pytest

from services.nextcloud_client import NextcloudClient

PROPFIND_FOLDERS_XML = """\
<?xml version="1.0"?>
<d:multistatus xmlns:d="DAV:">
  <d:response>
    <d:href>/public.php/webdav/</d:href>
    <d:propstat>
      <d:prop>
        <d:resourcetype><d:collection/></d:resourcetype>
      </d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
  <d:response>
    <d:href>/public.php/webdav/Laura%20Maria%20K%C3%B6nig/</d:href>
    <d:propstat>
      <d:prop>
        <d:resourcetype><d:collection/></d:resourcetype>
      </d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
  <d:response>
    <d:href>/public.php/webdav/Barbara%20Wessner/</d:href>
    <d:propstat>
      <d:prop>
        <d:resourcetype><d:collection/></d:resourcetype>
      </d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
</d:multistatus>
"""

PROPFIND_FILES_XML = """\
<?xml version="1.0"?>
<d:multistatus xmlns:d="DAV:">
  <d:response>
    <d:href>/public.php/webdav/Laura%20Maria%20K%C3%B6nig/</d:href>
    <d:propstat>
      <d:prop>
        <d:resourcetype><d:collection/></d:resourcetype>
      </d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
  <d:response>
    <d:href>/public.php/webdav/Laura%20Maria%20K%C3%B6nig/paper1.pdf</d:href>
    <d:propstat>
      <d:prop>
        <d:resourcetype/>
        <d:getcontentlength>12345</d:getcontentlength>
      </d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
  <d:response>
    <d:href>/public.php/webdav/Laura%20Maria%20K%C3%B6nig/notes.txt</d:href>
    <d:propstat>
      <d:prop>
        <d:resourcetype/>
        <d:getcontentlength>100</d:getcontentlength>
      </d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
</d:multistatus>
"""


class FakeResponse:
    def __init__(self, text, status_code=207):
        self.text = text
        self.content = text.encode()
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


class FakeClient:
    def __init__(self, responses):
        self._responses = responses
        self._call_index = 0

    async def request(self, method, url, **kwargs):
        resp = self._responses[self._call_index]
        self._call_index += 1
        return resp

    async def get(self, url, **kwargs):
        resp = self._responses[self._call_index]
        self._call_index += 1
        return resp

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


@pytest.mark.asyncio
async def test_list_folders(monkeypatch):
    client = NextcloudClient("https://example.com/public.php/webdav", "token123")

    async def mock_propfind(self, path):
        return PROPFIND_FOLDERS_XML

    monkeypatch.setattr(NextcloudClient, "_propfind", mock_propfind)

    folders = await client.list_folders("/")
    assert sorted(folders) == ["Barbara Wessner", "Laura Maria König"]


@pytest.mark.asyncio
async def test_list_files_filters_by_extension(monkeypatch):
    client = NextcloudClient("https://example.com/public.php/webdav", "token123")

    async def mock_propfind(self, path):
        return PROPFIND_FILES_XML

    monkeypatch.setattr(NextcloudClient, "_propfind", mock_propfind)

    files = await client.list_files("/Laura Maria König")
    assert files == ["paper1.pdf"]


@pytest.mark.asyncio
async def test_download_file(tmp_path, monkeypatch):
    client = NextcloudClient("https://example.com/public.php/webdav", "token123")
    pdf_content = b"%PDF-1.4 fake content"

    import httpx

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: FakeClient([FakeResponse(pdf_content.decode("latin-1"), status_code=200)]),
    )

    local_path = tmp_path / "test.pdf"
    result = await client.download_file("/Member/test.pdf", local_path)

    assert result == local_path
    assert local_path.read_bytes() == pdf_content.decode("latin-1").encode()
