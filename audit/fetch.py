"""Polite, cached HTTP downloads for the audit.

Every source gets an identifying User-Agent and conditional requests
(If-None-Match / If-Modified-Since), so re-running the audit does not
re-download unchanged files. Cached files live in data/raw/ (git-ignored).
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent


def _cache_dir() -> Path:
    """STEPFREE_CACHE from the environment or .env, else data/raw (as in CI)."""
    value = os.environ.get("STEPFREE_CACHE")
    env_file = ROOT / ".env"
    if not value and env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            key, _, val = line.partition("=")
            if key.strip() == "STEPFREE_CACHE" and val.strip():
                value = val.strip()
    return Path(value) if value else ROOT / "data" / "raw"


RAW = _cache_dir()
USER_AGENT = "stepfree-nl-audit/0.1 (+https://github.com/EamenFarand/daytrip_website)"
MIN_INTERVAL_S = 1.0  # at most one request per second to any source

_last_request = 0.0


def _throttle() -> None:
    global _last_request
    wait = _last_request + MIN_INTERVAL_S - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    _last_request = time.monotonic()


def fetch(url: str, name: str, headers: dict[str, str] | None = None, timeout: int = 600) -> Path:
    """Download url to data/raw/<name>, reusing the cached copy if unchanged."""
    target = RAW / name
    target.parent.mkdir(parents=True, exist_ok=True)
    meta_path = RAW / f"{name}.meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() and target.exists() else {}

    req_headers = {"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"}
    if meta.get("etag"):
        req_headers["If-None-Match"] = meta["etag"]
    if meta.get("last_modified"):
        req_headers["If-Modified-Since"] = meta["last_modified"]
    req_headers.update(headers or {})

    _throttle()
    with requests.get(url, headers=req_headers, stream=True, timeout=timeout) as r:
        if r.status_code == 304:
            return target
        r.raise_for_status()
        tmp = target.with_suffix(target.suffix + ".part")
        with tmp.open("wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
        tmp.replace(target)
        meta = {
            "url": url,
            "etag": r.headers.get("ETag"),
            "last_modified": r.headers.get("Last-Modified"),
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        meta_path.write_text(json.dumps(meta, indent=2))
    return target


def fetch_meta(name: str) -> dict:
    p = RAW / f"{name}.meta.json"
    return json.loads(p.read_text()) if p.exists() else {}
