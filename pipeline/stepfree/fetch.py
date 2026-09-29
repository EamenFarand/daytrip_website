"""Polite, cached HTTP downloads.

Identifying User-Agent, conditional requests (If-None-Match / If-Modified-Since),
gzip, and at most one request per second. Unchanged files are not re-downloaded.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import requests

from .config import CACHE, USER_AGENT

MIN_INTERVAL_S = 1.0
_last_request = 0.0


def _throttle() -> None:
    global _last_request
    wait = _last_request + MIN_INTERVAL_S - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    _last_request = time.monotonic()


def fetch(url: str, name: str, timeout: int = 600) -> Path:
    """Download url to CACHE/name, reusing the cached copy if the server says it is unchanged."""
    target = CACHE / name
    target.parent.mkdir(parents=True, exist_ok=True)
    meta_path = target.with_name(target.name + ".meta.json")
    meta = json.loads(meta_path.read_text()) if meta_path.exists() and target.exists() else {}

    headers = {"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"}
    if meta.get("etag"):
        headers["If-None-Match"] = meta["etag"]
    if meta.get("last_modified"):
        headers["If-Modified-Since"] = meta["last_modified"]

    _throttle()
    with requests.get(url, headers=headers, stream=True, timeout=timeout) as r:
        if r.status_code == 304:
            return target
        r.raise_for_status()
        tmp = target.with_name(target.name + ".part")
        with tmp.open("wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
        tmp.replace(target)
        meta_path.write_text(
            json.dumps(
                {
                    "url": url,
                    "etag": r.headers.get("ETag"),
                    "last_modified": r.headers.get("Last-Modified"),
                    "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                },
                indent=2,
            )
        )
    return target


def latest_listed(directory_url: str, pattern: str) -> str:
    """Newest file in an Apache/Cherokee-style directory listing whose name matches pattern."""
    _throttle()
    html = requests.get(directory_url, headers={"User-Agent": USER_AGENT}, timeout=60).text
    names = sorted(set(re.findall(rf'href="({pattern})"', html)))
    if not names:
        raise RuntimeError(f"nothing matching {pattern!r} listed at {directory_url}")
    return directory_url + names[-1]
