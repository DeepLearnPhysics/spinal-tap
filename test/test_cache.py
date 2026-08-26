"""Tests for temporary source caching and chunked uploads."""

import json
import os
import socket
import time

import h5py
import pytest
from flask import Flask

from spinal_tap import cache as cache_module
from spinal_tap.app import create_app
from spinal_tap.cache import CacheManager


def make_hdf5(path):
    """Create a minimal valid HDF5 upload payload."""
    with h5py.File(path, "w") as output:
        output.create_dataset("events", data=[0])


def test_chunked_upload_is_private_and_published_atomically(monkeypatch, tmp_path):
    """Only the owning session should write and complete an upload."""
    source = tmp_path / "source.bin"
    make_hdf5(source)
    payload = source.read_bytes()
    manager = CacheManager(
        root=tmp_path / "cache",
        max_bytes=1 << 20,
        max_file_bytes=1 << 20,
        chunk_bytes=32,
        max_chunk_bytes=64,
    )
    monkeypatch.setattr(cache_module, "cache_manager", manager)
    app = create_app()
    owner = app.server.test_client()
    stranger = app.server.test_client()

    response = owner.post(
        "/api/uploads", json={"name": "events.data", "size": len(payload)}
    )
    assert response.status_code == 201
    upload = response.get_json()
    headers = {"X-Upload-Token": upload["upload_token"]}

    denied = stranger.put(
        f"/api/uploads/{upload['upload_id']}/0",
        data=payload[:32],
        headers=headers,
    )
    assert denied.status_code == 403

    for index in range(upload["chunk_count"]):
        start = index * upload["chunk_size"]
        chunk = payload[start : start + upload["chunk_size"]]
        response = owner.put(
            f"/api/uploads/{upload['upload_id']}/{index}",
            data=chunk,
            headers=headers,
        )
        assert response.status_code == 200

    response = owner.post(
        f"/api/uploads/{upload['upload_id']}/complete", headers=headers
    )
    assert response.status_code == 200
    completed = response.get_json()
    assert completed["name"] == "events.data"
    assert completed["kind"] == "hdf5"
    assert completed["temporary"] is True
    with owner.session_transaction() as upload_session:
        assert manager.owns_path(completed["path"], upload_session["cache_id"])


def test_upload_accepts_extensionless_view_json(monkeypatch, tmp_path):
    """Cached source validation should inspect JSON content, not its name."""
    payload = json.dumps({"version": 1}).encode()
    manager = CacheManager(
        root=tmp_path / "cache",
        max_bytes=1 << 20,
        max_file_bytes=1 << 20,
        chunk_bytes=1024,
        max_chunk_bytes=2048,
    )
    monkeypatch.setattr(cache_module, "cache_manager", manager)
    app = create_app()
    client = app.server.test_client()
    initialized = client.post(
        "/api/uploads", json={"name": "saved-view", "size": len(payload)}
    ).get_json()
    headers = {"X-Upload-Token": initialized["upload_token"]}
    client.put(
        f"/api/uploads/{initialized['upload_id']}/0",
        data=payload,
        headers=headers,
    )
    response = client.post(
        f"/api/uploads/{initialized['upload_id']}/complete", headers=headers
    )
    assert response.status_code == 200
    assert response.get_json()["kind"] == "json"


def test_cache_session_and_safe_filename(monkeypatch, tmp_path):
    """Session namespaces and cached basenames should be stable and portable."""
    assert cache_module.cache_session_id() == "local"
    assert cache_module.safe_filename("../ odd name!!.h5") == "odd_name_.h5"
    assert cache_module.safe_filename("...") == "upload.h5"

    server = Flask(__name__)
    server.secret_key = "test"
    with server.test_request_context("/"):
        first = cache_module.cache_session_id()
        assert cache_module.cache_session_id() == first
        assert cache_module.session["cache_id"] == first


def test_cache_housekeeping_and_ownership(tmp_path):
    """Expired files should be removed while active owned files are refreshed."""
    manager = CacheManager(root=tmp_path / "cache", ttl_seconds=10)
    root = manager.session_root("owner")
    active = root / "active.h5"
    active.write_bytes(b"active")
    old = manager.session_root("old") / "old.h5"
    old.write_bytes(b"old")
    stale = time.time() - 20
    os.utime(old, (stale, stale))

    assert manager.used_bytes() == 9
    assert manager.owns_path(str(active), "owner")
    assert not manager.owns_path(str(active), "stranger")
    assert not manager.owns_path(str(tmp_path / "missing"), "owner")
    manager.cleanup()
    assert active.exists()
    assert not old.exists()
    assert not (manager.root / "old").exists()


def test_begin_upload_limits_and_chunk_validation(monkeypatch, tmp_path):
    """Allocation, authorization and deterministic chunk sizing are enforced."""
    manager = CacheManager(
        root=tmp_path / "cache",
        max_bytes=10,
        max_file_bytes=8,
        chunk_bytes=4,
        max_chunk_bytes=4,
    )
    monkeypatch.setattr(cache_module, "ALLOW_UPLOADS", False)
    with pytest.raises(PermissionError, match="disabled"):
        manager.begin_upload("a.h5", 4)
    monkeypatch.setattr(cache_module, "ALLOW_UPLOADS", True)
    with pytest.raises(ValueError, match="empty"):
        manager.begin_upload("a.h5", 0)
    with pytest.raises(ValueError, match="limit"):
        manager.begin_upload("a.h5", 9)

    upload = manager.begin_upload("a.h5", 8)
    with pytest.raises(ValueError, match="cache is full"):
        manager.begin_upload("b.h5", 4)
    with pytest.raises(PermissionError, match="unauthorized"):
        manager.write_chunk(upload["upload_id"], "wrong", 0, b"1234")
    with pytest.raises(ValueError, match="out of range"):
        manager.write_chunk(upload["upload_id"], upload["upload_token"], 2, b"")
    with pytest.raises(ValueError, match="expected 4"):
        manager.write_chunk(upload["upload_id"], upload["upload_token"], 0, b"1")
    manager.write_chunk(upload["upload_id"], upload["upload_token"], 0, b"1234")
    with pytest.raises(ValueError, match="incomplete"):
        manager.finish_upload(upload["upload_id"], upload["upload_token"])
    manager.cancel_upload(upload["upload_id"], upload["upload_token"])
    assert not manager._uploads


class FakeResponse:
    """Minimal context-managed URL response."""

    def __init__(self, payload, url="https://example.org/file.h5", length=None):
        self.payload = payload
        self.url = url
        self.headers = {} if length is None else {"Content-Length": str(length)}
        self.offset = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def geturl(self):
        return self.url

    def read(self, size):
        block = self.payload[self.offset : self.offset + size]
        self.offset += len(block)
        return block


def test_fetch_url_downloads_validates_and_reuses(monkeypatch, tmp_path):
    """Public URLs should be validated, cached and reused without redownload."""
    source = tmp_path / "source.h5"
    make_hdf5(source)
    payload = source.read_bytes()
    manager = CacheManager(
        root=tmp_path / "cache", max_bytes=1 << 20, max_file_bytes=1 << 20
    )
    monkeypatch.setattr(manager, "_validate_public_host", lambda host: None)
    opens = []

    class Opener:
        def open(self, request, timeout):
            opens.append((request.full_url, timeout))
            return FakeResponse(payload)

    monkeypatch.setattr(
        cache_module.urllib.request, "build_opener", lambda *args: Opener()
    )
    path = manager.fetch_url("https://example.org/file.h5")
    assert os.path.isfile(path)
    assert manager.fetch_url("https://example.org/file.h5") == path
    assert opens == [("https://example.org/file.h5", 30)]


def test_fetch_url_rejects_invalid_and_oversized_sources(monkeypatch, tmp_path):
    """URL policy and declared or streamed size limits should fail safely."""
    manager = CacheManager(root=tmp_path / "cache", max_bytes=20, max_file_bytes=4)
    monkeypatch.setattr(cache_module, "ALLOW_URLS", False)
    with pytest.raises(PermissionError, match="disabled"):
        manager.fetch_url("https://example.org/a")
    monkeypatch.setattr(cache_module, "ALLOW_URLS", True)
    for url in ("file:///tmp/a", "relative"):
        with pytest.raises(ValueError, match="absolute HTTP"):
            manager.fetch_url(url)

    monkeypatch.setattr(manager, "_validate_public_host", lambda host: None)

    class Opener:
        response = FakeResponse(b"12345", length=5)

        def open(self, request, timeout):
            return self.response

    monkeypatch.setattr(
        cache_module.urllib.request, "build_opener", lambda *args: Opener()
    )
    with pytest.raises(ValueError, match="download limit"):
        manager.fetch_url("https://example.org/declared")
    Opener.response = FakeResponse(b"12345")
    with pytest.raises(ValueError, match="download limit"):
        manager.fetch_url("https://example.org/streamed")
    assert not list(manager.root.glob("url/*.part"))


def test_public_host_validation(monkeypatch):
    """Resolution failures and private addresses should be rejected."""
    monkeypatch.setattr(
        cache_module.socket,
        "getaddrinfo",
        lambda *args: [(None, None, None, None, ("8.8.8.8", 0))],
    )
    CacheManager._validate_public_host("public.example")
    monkeypatch.setattr(
        cache_module.socket,
        "getaddrinfo",
        lambda *args: [(None, None, None, None, ("127.0.0.1", 0))],
    )
    with pytest.raises(ValueError, match="private or local"):
        CacheManager._validate_public_host("local.example")

    def fail(*args):
        raise socket.gaierror("failed")

    monkeypatch.setattr(cache_module.socket, "getaddrinfo", fail)
    with pytest.raises(ValueError, match="Could not resolve"):
        CacheManager._validate_public_host("missing.example")


def test_cleanup_and_cancel_tolerate_concurrent_deletion(monkeypatch, tmp_path):
    """Cache cleanup should tolerate files disappearing between checks."""
    manager = CacheManager(root=tmp_path / "cache", ttl_seconds=0)
    path = manager.session_root("owner") / "gone.h5"
    path.write_bytes(b"x")
    original_stat = type(path).stat

    def missing_stat(self, *args, **kwargs):
        if self == path:
            raise FileNotFoundError
        return original_stat(self, *args, **kwargs)

    monkeypatch.setattr(type(path), "stat", missing_stat)
    manager.cleanup()

    monkeypatch.undo()
    upload = manager.begin_upload("a.h5", 1)
    manager._uploads[upload["upload_id"]]["part_path"].unlink()
    manager.cancel_upload(upload["upload_id"], upload["upload_token"])


def test_fetch_url_redirect_and_cache_capacity_errors(monkeypatch, tmp_path):
    """Redirect destinations and post-download cache capacity are revalidated."""
    source = tmp_path / "source.h5"
    make_hdf5(source)
    payload = source.read_bytes()
    manager = CacheManager(root=tmp_path / "cache", max_bytes=1, max_file_bytes=1 << 20)
    validators = []

    def validate(host):
        validators.append(host)

    monkeypatch.setattr(manager, "_validate_public_host", validate)
    handler = None

    class Opener:
        def open(self, request, timeout):
            return FakeResponse(payload)

    def build_opener(candidate):
        nonlocal handler
        handler = candidate
        return Opener()

    monkeypatch.setattr(cache_module.urllib.request, "build_opener", build_opener)
    with pytest.raises(ValueError, match="cache is full"):
        manager.fetch_url("https://example.org/file.h5")
    assert validators == ["example.org", "example.org"]

    with pytest.raises(ValueError, match="invalid location"):
        handler.redirect_request(None, None, 302, "", {}, "file:///tmp/private")
    monkeypatch.setattr(
        cache_module.urllib.request.HTTPRedirectHandler,
        "redirect_request",
        lambda *args: "redirected",
    )
    assert (
        handler.redirect_request(
            None, None, 302, "", {}, "https://redirect.example/file.h5"
        )
        == "redirected"
    )
    assert validators[-1] == "redirect.example"


def test_fetch_url_rejects_response_without_host(monkeypatch, tmp_path):
    """A malformed final response URL should be rejected and cleaned up."""
    manager = CacheManager(root=tmp_path / "cache")
    monkeypatch.setattr(manager, "_validate_public_host", lambda host: None)

    class Opener:
        def open(self, request, timeout):
            return FakeResponse(b"", url="not-a-url")

    monkeypatch.setattr(
        cache_module.urllib.request, "build_opener", lambda *args: Opener()
    )
    with pytest.raises(ValueError, match="invalid location"):
        manager.fetch_url("https://example.org/file.h5")
