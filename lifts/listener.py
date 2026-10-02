"""Live lift status for Trapvrij (trapvrij.nl).

Listens to the SIRI-FM lift feed on NDOV Loket and publishes lifts.json to Cloudflare Workers KV,
which the site reads through functions/api/lifts.js. Runs in Docker on Daan's home server
(README.md). Why this design: docs/DECISIONS.md, 2026-10-02.

- One connection to the best-effort ZeroMQ stream (fair use), only the /DOVA/ messages.
- Every lift keeps its open conditions. The full state that arrives every night (~04:02 CEST)
  replaces them all; a change message adds to one lift. A lift can have several open conditions
  at once; its status now is the one that started last among those valid now.
- The state is saved after every status message, so a restart carries on where it stopped.
- lifts.json goes out when the lifts that are out change (at most every 2 minutes), and at least
  every 10 minutes, so its timestamps show the listener is alive. An implausible state is never
  published; the site then lets the last good one age into "unknown".
"""

from __future__ import annotations

import gzip
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
import zmq
from lxml import etree

ENDPOINT = "tcp://pubsub.besteffort.ndovloket.nl:7666"
ENVELOPE = b"/DOVA/"
S = "{http://www.siri.org.uk/siri}"
PREFIX = "NL:CHB:LiftEquipment:"
FULL_STATE_MIN = 300  # a message with at least this many lifts is the nightly full state (~457)
MIN_LIFTS = 300  # never publish a state with fewer lifts than this...
MAX_OUT_SHARE = 0.5  # ...or with more than half of them out: then something is wrong upstream
PUBLISH_MIN = timedelta(minutes=2)
PUBLISH_MAX = timedelta(minutes=10)
RECONNECT_AFTER = timedelta(minutes=30)  # heartbeats normally come every 10 minutes
USER_AGENT = "trapvrij-lifts/0.1 (+https://trapvrij.nl)"

log = logging.getLogger("lifts")


def _time(text: str | None) -> datetime | None:
    return datetime.fromisoformat(text.replace("Z", "+00:00")) if text else None


def _iso(t: datetime | None) -> str | None:
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if t else None


def parse(body: bytes) -> tuple[list[dict], bool]:
    """The lift conditions in one message, and whether it is a heartbeat."""
    try:
        body = gzip.decompress(body)
    except OSError:
        pass  # not compressed
    root = etree.fromstring(body)
    conditions = []
    for fc in root.iter(S + "FacilityCondition"):
        ref = fc.findtext(S + "FacilityRef") or ""
        if ref.startswith(PREFIX):
            conditions.append({
                "id": ref.removeprefix(PREFIX),
                "status": fc.findtext(f"{S}FacilityStatus/{S}Status") or "unknown",
                "start": fc.findtext(f"{S}ValidityPeriod/{S}StartTime"),
                "end": fc.findtext(f"{S}ValidityPeriod/{S}EndTime"),
            })
    heartbeat = root.tag == S + "HeartbeatNotification" or root.find(f".//{S}HeartbeatNotification") is not None
    return conditions, heartbeat


@dataclass
class State:
    lifts: dict[str, list[dict]] = field(default_factory=dict)  # lift id -> its open conditions
    full_state_at: datetime | None = None
    last_message_at: datetime | None = None  # last status message; heartbeats don't count

    def apply(self, conditions: list[dict], now: datetime) -> None:
        if not conditions:
            return
        if len(conditions) >= FULL_STATE_MIN:
            self.lifts = {}
            self.full_state_at = now
        for c in conditions:
            kept = [k for k in self.lifts.get(c["id"], []) if k["start"] != c["start"]]  # a resend replaces itself
            self.lifts[c["id"]] = sorted(kept + [c], key=lambda k: k["start"] or "")[-3:]
        self.last_message_at = now

    def current(self, lift_id: str, now: datetime) -> dict:
        """The condition that started last among those valid now."""
        valid = [
            c for c in self.lifts.get(lift_id, [])
            if (_time(c["start"]) or now) <= now and (c["end"] is None or _time(c["end"]) > now)
        ]
        return max(valid, key=lambda c: c["start"] or "") if valid else {"status": "unknown", "start": None, "end": None}

    def payload(self, now: datetime) -> dict:
        out = []
        for lift_id in sorted(self.lifts):
            c = self.current(lift_id, now)
            if c["status"] != "available":
                out.append({"id": lift_id, "status": c["status"], "since": _iso(_time(c["start"])), "until": _iso(_time(c["end"]))})
        return {
            "v": 1,
            "updated": _iso(now),
            "full_state_at": _iso(self.full_state_at),
            "last_message_at": _iso(self.last_message_at),
            "lifts": len(self.lifts),
            "out": out,
        }

    def save(self, path: Path) -> None:
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps({"lifts": self.lifts, "full_state_at": _iso(self.full_state_at), "last_message_at": _iso(self.last_message_at)}))
        tmp.replace(path)

    @classmethod
    def load(cls, path: Path) -> State:
        if not path.exists():
            return cls()
        d = json.loads(path.read_text())
        return cls(d["lifts"], _time(d["full_state_at"]), _time(d["last_message_at"]))


def problem(payload: dict) -> str | None:
    """Why this payload must not be published, or None if it may."""
    if not payload["full_state_at"]:
        return "no full state yet (it arrives every night around 04:02)"
    if payload["lifts"] < MIN_LIFTS:
        return f"only {payload['lifts']} lifts known"
    if len(payload["out"]) > MAX_OUT_SHARE * payload["lifts"]:
        return f"{len(payload['out'])} of {payload['lifts']} lifts out"
    return None


class Publisher:
    def __init__(self, account: str | None, namespace: str | None, token: str | None, dry_run_file: Path | None = None):
        self.url = f"https://api.cloudflare.com/client/v4/accounts/{account}/storage/kv/namespaces/{namespace}/values/lifts"
        self.token = token
        self.dry_run_file = dry_run_file
        self.last_try: datetime | None = None
        self.last_at: datetime | None = None
        self.last_out: list | None = None

    def due(self, payload: dict, now: datetime) -> bool:
        if self.last_try and now - self.last_try < PUBLISH_MIN:
            return False
        return self.last_at is None or payload["out"] != self.last_out or now - self.last_at >= PUBLISH_MAX

    def publish(self, payload: dict, now: datetime) -> None:
        self.last_try = now
        body = json.dumps(payload, separators=(",", ":"))
        if self.dry_run_file:
            self.dry_run_file.write_text(body)
        else:
            headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json", "User-Agent": USER_AGENT}
            requests.put(self.url, headers=headers, data=body.encode(), timeout=30).raise_for_status()
        self.last_at, self.last_out = now, payload["out"]


def _connect(ctx: zmq.Context) -> zmq.Socket:
    sock = ctx.socket(zmq.SUB)
    sock.setsockopt(zmq.RCVTIMEO, 30_000)
    sock.setsockopt(zmq.TCP_KEEPALIVE, 1)
    sock.connect(ENDPOINT)
    sock.setsockopt(zmq.SUBSCRIBE, ENVELOPE)
    log.info("connected to %s", ENDPOINT)
    return sock


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    state_file = Path(os.environ.get("STATE_FILE", "/data/state.json"))
    dry_run = os.environ.get("DRY_RUN") == "1"
    settings = {k: os.environ.get(k) for k in ("CF_ACCOUNT_ID", "CF_KV_NAMESPACE_ID", "CF_API_TOKEN")}
    if not dry_run and not all(settings.values()):
        sys.exit(f"missing settings in .env: {', '.join(k for k, v in settings.items() if not v)}")
    publisher = Publisher(*settings.values(), dry_run_file=state_file.with_name("lifts.json") if dry_run else None)
    state = State.load(state_file)
    log.info("state: %d lifts, full state from %s%s", len(state.lifts), _iso(state.full_state_at), " (dry run)" if dry_run else "")

    ctx = zmq.Context()
    while True:
        sock, seen = _connect(ctx), datetime.now(timezone.utc)
        while True:
            try:
                parts = sock.recv_multipart()
            except zmq.Again:
                parts = None
            now = datetime.now(timezone.utc)
            if parts and len(parts) >= 2:
                seen = now
                try:
                    conditions, _ = parse(parts[1])
                except etree.XMLSyntaxError as e:
                    log.warning("unreadable message: %s", e)
                    conditions = []
                if conditions:
                    state.apply(conditions, now)
                    state.save(state_file)
                    if len(conditions) >= FULL_STATE_MIN:
                        log.info("full state: %d lifts", len(state.lifts))
            payload = state.payload(now)
            if publisher.due(payload, now):
                if why := problem(payload):
                    publisher.last_try = now
                    log.warning("not publishing: %s", why)
                else:
                    try:
                        publisher.publish(payload, now)
                        log.info("published: %d of %d lifts out", len(payload["out"]), payload["lifts"])
                    except requests.RequestException as e:
                        log.warning("publishing failed: %s", e)
            if now - seen > RECONNECT_AFTER:
                log.warning("nothing received for %s; reconnecting", now - seen)
                sock.close(linger=0)
                break


if __name__ == "__main__":
    main()
