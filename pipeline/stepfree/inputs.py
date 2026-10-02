"""What a build is made from, so the nightly job can skip a build when nothing changed.

  uv run python -m stepfree.inputs --live https://trapvrij.pages.dev/data/meta.json [--always]

Downloads the sources (conditional requests: an unchanged file isn't downloaded again) and
prints `build=true|false` and `reason=...` for GitHub Actions. A build is needed when there is
no live build, when the sources, the corrections file or the pipeline code differ from the live
build's, or when a day the live build is based on has passed. `--always` says true regardless
(pushes and manual runs) but still downloads, so the cache stays warm.
"""

from __future__ import annotations

import argparse
import hashlib
from datetime import date
from pathlib import Path

import requests

from . import access
from .config import CACHE, GTFS_URL, IFF_URL, OVERRIDES, ROOT, USER_AGENT
from .fetch import fetch


def _sha(paths: list[Path]) -> str:
    h = hashlib.sha256()
    for p in paths:
        with p.open("rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
    return h.hexdigest()[:16]


def fetch_sources() -> None:
    fetch(GTFS_URL, "gtfs-nl.zip")
    fetch(IFF_URL, "ns-latest.zip")
    access.fetch_epiap()


def fingerprint() -> dict[str, str]:
    """Hashes of the downloaded sources and of our own rules and code (after fetch_sources)."""
    code = sorted((ROOT / "pipeline" / "stepfree").glob("*.py")) + [ROOT / "pipeline" / "uv.lock"]
    return {
        "gtfs": _sha([CACHE / "gtfs-nl.zip"]),
        "epiap": _sha([CACHE / "netex" / "epiap.xml.gz"]),
        "iff": _sha([CACHE / "ns-latest.zip"]),
        "overrides": _sha([OVERRIDES]),
        "code": _sha(code),
    }


def needs_build(live: dict | None, current: dict[str, str], today: date) -> tuple[bool, str]:
    if not live or "inputs" not in live:
        return True, "no live build to compare with"
    changed = [k for k, v in current.items() if live["inputs"].get(k) != v]
    if changed:
        return True, "changed: " + ", ".join(changed)
    if any(date.fromisoformat(d) < today for d in live.get("days", {}).values()):
        return True, "a timetable day of the live build has passed"
    return False, "nothing changed since the live build"


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--live", required=True, help="URL of the live build's meta.json")
    ap.add_argument("--always", action="store_true", help="build anyway (push or manual run)")
    args = ap.parse_args(argv)
    fetch_sources()
    try:
        r = requests.get(args.live, headers={"User-Agent": USER_AGENT}, timeout=30)
        live = r.json() if r.ok else None
    except (requests.RequestException, ValueError):
        live = None
    build, reason = needs_build(live, fingerprint(), date.today())
    if args.always:
        build, reason = True, f"requested ({reason})"
    print(f"build={'true' if build else 'false'}")
    print(f"reason={reason}")


if __name__ == "__main__":
    main()
