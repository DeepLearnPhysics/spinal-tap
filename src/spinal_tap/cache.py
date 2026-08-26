"""Manage temporary files downloaded or uploaded through Spinal Tap."""

import hashlib
import ipaddress
import os
import re
import secrets
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from threading import RLock

from flask import has_request_context, session

CACHE_DIR = Path(os.getenv("SPINAL_TAP_CACHE_DIR", "/tmp/spinal-tap-cache"))
CACHE_MAX_BYTES = int(os.getenv("SPINAL_TAP_CACHE_MAX_BYTES", str(20 << 30)))
CACHE_FILE_MAX_BYTES = int(os.getenv("SPINAL_TAP_CACHE_FILE_MAX_BYTES", str(2 << 30)))
CACHE_TTL_SECONDS = int(os.getenv("SPINAL_TAP_CACHE_TTL_SECONDS", "86400"))
UPLOAD_CHUNK_BYTES = int(os.getenv("SPINAL_TAP_UPLOAD_CHUNK_BYTES", str(32 << 20)))
UPLOAD_MAX_CHUNK_BYTES = int(
    os.getenv("SPINAL_TAP_UPLOAD_MAX_CHUNK_BYTES", str(64 << 20))
)
ALLOW_UPLOADS = os.getenv("SPINAL_TAP_ALLOW_UPLOADS", "true").lower() == "true"
ALLOW_URLS = os.getenv("SPINAL_TAP_ALLOW_URLS", "true").lower() == "true"

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def cache_session_id() -> str:
    """Return a stable, unguessable cache namespace for the current session."""
    if not has_request_context():
        return "local"
    cache_id = session.get("cache_id")
    if not cache_id:
        cache_id = secrets.token_urlsafe(18)
        session["cache_id"] = cache_id
    return cache_id


def safe_filename(filename: str) -> str:
    """Return a portable basename suitable for a private cache directory."""
    filename = Path(filename or "upload.h5").name
    filename = _SAFE_NAME.sub("_", filename).strip("._")
    return filename or "upload.h5"


class CacheManager:
    """Own temporary upload state and URL-backed source files."""

    def __init__(
        self,
        root: Path = CACHE_DIR,
        max_bytes: int = CACHE_MAX_BYTES,
        max_file_bytes: int = CACHE_FILE_MAX_BYTES,
        ttl_seconds: int = CACHE_TTL_SECONDS,
        chunk_bytes: int = UPLOAD_CHUNK_BYTES,
        max_chunk_bytes: int = UPLOAD_MAX_CHUNK_BYTES,
    ) -> None:
        self.root = Path(root)
        self.max_bytes = max_bytes
        self.max_file_bytes = max_file_bytes
        self.ttl_seconds = ttl_seconds
        self.chunk_bytes = chunk_bytes
        self.max_chunk_bytes = max_chunk_bytes
        self._lock = RLock()
        self._uploads = {}

    def ensure_root(self) -> None:
        """Create the private cache root when it is first needed."""
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)

    def session_root(self, session_id: str | None = None) -> Path:
        """Return and create the private directory for one browser session."""
        self.ensure_root()
        path = self.root / (session_id or cache_session_id())
        path.mkdir(mode=0o700, exist_ok=True)
        return path

    def owns_path(self, file_path: str, session_id: str | None = None) -> bool:
        """Check whether a path is an existing file owned by this session."""
        try:
            path = Path(file_path).resolve(strict=True)
            root = self.session_root(session_id).resolve(strict=True)
            owned = path.is_file() and path.is_relative_to(root)
            if owned:
                # Keep sources which are still being viewed from expiring.
                os.utime(path, None)
            return owned
        except (OSError, RuntimeError, ValueError):
            return False

    def cleanup(self) -> None:
        """Remove expired files and empty session directories."""
        self.ensure_root()
        cutoff = time.time() - self.ttl_seconds
        with self._lock:
            for path in self.root.glob("*/*"):
                try:
                    if path.stat().st_mtime < cutoff:
                        path.unlink()
                except FileNotFoundError:
                    pass
            for directory in self.root.iterdir():
                if directory.is_dir():
                    try:
                        directory.rmdir()
                    except OSError:
                        pass

    def used_bytes(self) -> int:
        """Return the logical size of all files currently in the cache."""
        self.ensure_root()
        return sum(
            path.stat().st_size for path in self.root.glob("*/*") if path.is_file()
        )

    def begin_upload(self, filename: str, size: int) -> dict:
        """Allocate one sparse temporary file and return upload instructions."""
        if not ALLOW_UPLOADS:
            raise PermissionError("Temporary uploads are disabled.")
        filename = safe_filename(filename)
        if size <= 0:
            raise ValueError("The selected file is empty.")
        if size > self.max_file_bytes:
            raise ValueError(
                f"The selected file exceeds the {self.max_file_bytes >> 20} MiB "
                "temporary-upload limit."
            )

        self.cleanup()
        with self._lock:
            if self.used_bytes() + size > self.max_bytes:
                raise ValueError("The temporary file cache is full; try again later.")
            upload_id = secrets.token_urlsafe(18)
            upload_token = secrets.token_urlsafe(24)
            session_id = cache_session_id()
            root = self.session_root(session_id)
            part_path = root / f".{upload_id}.part"
            final_path = root / f"{upload_id}-{filename}"
            with open(part_path, "wb") as output:
                output.truncate(size)
            self._uploads[upload_id] = {
                "token": upload_token,
                "session": session_id,
                "filename": filename,
                "size": size,
                "part_path": part_path,
                "final_path": final_path,
                "chunks": set(),
                "created": time.time(),
            }

        return {
            "upload_id": upload_id,
            "upload_token": upload_token,
            "chunk_size": self.chunk_bytes,
            "chunk_count": (size + self.chunk_bytes - 1) // self.chunk_bytes,
        }

    def _upload(self, upload_id: str, token: str) -> dict:
        """Return upload state after authenticating its session and token."""
        upload = self._uploads.get(upload_id)
        if (
            upload is None
            or upload["token"] != token
            or upload["session"] != cache_session_id()
        ):
            raise PermissionError("Unknown or unauthorized upload.")
        return upload

    def write_chunk(
        self, upload_id: str, token: str, index: int, payload: bytes
    ) -> dict:
        """Write one bounded chunk at its deterministic file offset."""
        with self._lock:
            upload = self._upload(upload_id, token)
            count = (upload["size"] + self.chunk_bytes - 1) // self.chunk_bytes
            if index < 0 or index >= count:
                raise ValueError("Upload chunk index is out of range.")
            expected = min(self.chunk_bytes, upload["size"] - index * self.chunk_bytes)
            if len(payload) != expected or len(payload) > self.max_chunk_bytes:
                raise ValueError(
                    f"Upload chunk has {len(payload)} bytes; expected {expected}."
                )
            with open(upload["part_path"], "r+b", buffering=0) as output:
                output.seek(index * self.chunk_bytes)
                output.write(payload)
            upload["chunks"].add(index)
            os.utime(upload["part_path"], None)
            return {"received": len(upload["chunks"]), "total": count}

    def finish_upload(self, upload_id: str, token: str) -> dict:
        """Validate and atomically publish a completed temporary upload."""
        with self._lock:
            upload = self._upload(upload_id, token)
            count = (upload["size"] + self.chunk_bytes - 1) // self.chunk_bytes
            if upload["chunks"] != set(range(count)):
                raise ValueError("The upload is incomplete.")
            kind = self._validate_file(upload["part_path"])
            os.replace(upload["part_path"], upload["final_path"])
            self._uploads.pop(upload_id, None)
            return {
                "path": str(upload["final_path"]),
                "name": upload["filename"],
                "size": upload["size"],
                "kind": kind,
                "temporary": True,
            }

    def cancel_upload(self, upload_id: str, token: str) -> None:
        """Discard an incomplete upload owned by the current session."""
        with self._lock:
            upload = self._upload(upload_id, token)
            try:
                upload["part_path"].unlink()
            except FileNotFoundError:
                pass
            self._uploads.pop(upload_id, None)

    @staticmethod
    def _validate_file(path: Path) -> str:
        """Validate a source and return its content-detected kind."""
        from .source import detect_source_file

        return detect_source_file(path)

    def fetch_url(self, url: str) -> str:
        """Download an allowed public HTTP(S) source into the shared URL cache."""
        if not ALLOW_URLS:
            raise PermissionError("URL sources are disabled.")
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("URL sources must use an absolute HTTP(S) URL.")
        self._validate_public_host(parsed.hostname)
        filename = safe_filename(Path(parsed.path).name or "download.h5")
        self.cleanup()

        url_id = hashlib.sha256(url.encode()).hexdigest()
        root = self.session_root("url")
        final_path = root / f"{url_id}-{filename}"
        if final_path.is_file():
            os.utime(final_path, None)
            return str(final_path)

        part_path = root / f".{url_id}-{secrets.token_urlsafe(8)}.part"
        manager = self

        class SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
            """Validate every redirect destination before connecting to it."""

            def redirect_request(self, request, fp, code, msg, headers, new_url):
                target = urllib.parse.urlparse(new_url)
                if target.scheme not in {"http", "https"} or not target.hostname:
                    raise ValueError("The URL redirected to an invalid location.")
                manager._validate_public_host(target.hostname)
                return super().redirect_request(
                    request, fp, code, msg, headers, new_url
                )

        request = urllib.request.Request(url, headers={"User-Agent": "spinal-tap"})
        opener = urllib.request.build_opener(SafeRedirectHandler())
        try:
            with opener.open(request, timeout=30) as response:
                final_url = response.geturl()
                final_host = urllib.parse.urlparse(final_url).hostname
                if not final_host:
                    raise ValueError("The URL redirected to an invalid location.")
                self._validate_public_host(final_host)
                declared = response.headers.get("Content-Length")
                if declared and int(declared) > self.max_file_bytes:
                    raise ValueError("The remote file exceeds the download limit.")
                with open(part_path, "wb") as output:
                    copied = 0
                    while True:
                        block = response.read(1 << 20)
                        if not block:
                            break
                        copied += len(block)
                        if copied > self.max_file_bytes:
                            raise ValueError(
                                "The remote file exceeds the download limit."
                            )
                        output.write(block)
            self._validate_file(part_path)
            if self.used_bytes() > self.max_bytes:
                raise ValueError("The temporary file cache is full; try again later.")
            os.replace(part_path, final_path)
        except (OSError, urllib.error.URLError, ValueError):
            try:
                part_path.unlink()
            except FileNotFoundError:
                pass
            raise
        return str(final_path)

    @staticmethod
    def _validate_public_host(hostname: str) -> None:
        """Reject URL destinations on local, private, or special networks."""
        try:
            addresses = {item[4][0] for item in socket.getaddrinfo(hostname, None)}
        except socket.gaierror as error:
            raise ValueError(f"Could not resolve URL host {hostname!r}.") from error
        for address in addresses:
            ip = ipaddress.ip_address(address)
            if not ip.is_global:
                raise ValueError("URL sources cannot target private or local networks.")


cache_manager = CacheManager()
