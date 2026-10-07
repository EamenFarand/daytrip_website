"""Live lift status for Trapvrij (trapvrij.nl), and which trains run without steps.

Runs in Docker on Daan's home server (README.md) and writes to Cloudflare Workers KV, which the site
and the build read through functions/api/. Why this design: docs/DECISIONS.md, 2026-10-02 and 2026-10-07.

Lifts (`lifts`, read by the site through functions/api/lifts.js):
- One connection to the best-effort ZeroMQ stream (fair use), only the /DOVA/ messages.
- Every lift keeps its open conditions. The full state that arrives every night (~04:02 CEST)
  replaces them all; a change message adds to one lift. A lift can have several open conditions
  at once; its status now is the one that started last among those valid now.
- A lift that came back less than 30 minutes ago is still listed, as "back": in the audit's 72-hour log,
  3 in 10 lifts that came back were out again within the hour (docs/DECISIONS.md, 2026-10-04).
- The state is saved after every status message, so a restart carries on where it stopped.
- lifts.json goes out when the lifts that are out change (at most every 2 minutes), and at least
  every 10 minutes, so its timestamps show the listener is alive. An implausible state is never
  published; the site then lets the last good one age into "unknown".

Trains (`trains`, read by the build through functions/api/trains.js):
- A second connection, to NS's journey messages (InfoPlus RIT, a separate stream, so still one per stream).
- NS marks every train unit accessible or not (MaterieelDeelToegankelijk). Per service date the listener
  keeps which train numbers ran with only accessible units ("yes") and which with one that isn't ("no").
  A "no" stays for that date. The build decides from the last four weeks which trains count as without steps.
- Saved every 10 minutes and published every hour.
"""

from __future__ import annotations

import gzip
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
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
HOLD = timedelta(minutes=30)  # a lift that came back is listed as "back" this long
USER_AGENT = "trapvrij-lifts/0.1 (+https://trapvrij.nl)"

RIT_ENDPOINT = "tcp://pubsub.besteffort.ndovloket.nl:7664"
RIT_ENVELOPE = b"/RIG/InfoPlusRITInterface5"
RIT_RECONNECT_AFTER = timedelta(minutes=60)  # journey messages come every few seconds while trains run
TRAINS_KEEP = timedelta(days=35)  # service dates kept; the build uses the last four weeks
TRAINS_SAVE_EVERY = timedelta(minutes=10)
TRAINS_PUBLISH_EVERY = timedelta(hours=1)

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
    last_out: dict[str, str] = field(default_factory=dict)  # lift id -> when it was last seen out, for HOLD

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
        """What the site gets. Also notes which lifts are out now, so one that comes back is listed as "back" for HOLD."""
        out = []
        for lift_id in sorted(self.lifts):
            c = self.current(lift_id, now)
            if c["status"] != "available":
                self.last_out[lift_id] = _iso(now)
                out.append({"id": lift_id, "status": c["status"], "since": _iso(_time(c["start"])), "until": _iso(_time(c["end"]))})
            elif (seen := _time(self.last_out.get(lift_id))) and now - seen < HOLD:
                out.append({"id": lift_id, "status": "back", "since": _iso(seen), "until": None})
        self.last_out = {k: t for k, t in self.last_out.items() if now - _time(t) < HOLD}
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
        tmp.write_text(json.dumps({"lifts": self.lifts, "full_state_at": _iso(self.full_state_at), "last_message_at": _iso(self.last_message_at), "last_out": self.last_out}))
        tmp.replace(path)

    @classmethod
    def load(cls, path: Path) -> State:
        if not path.exists():
            return cls()
        d = json.loads(path.read_text())
        return cls(d["lifts"], _time(d["full_state_at"]), _time(d["last_message_at"]), d.get("last_out", {}))


def problem(payload: dict) -> str | None:
    """Why this payload must not be published, or None if it may."""
    if not payload["full_state_at"]:
        return "no full state yet (it arrives every night around 04:02)"
    if payload["lifts"] < MIN_LIFTS:
        return f"only {payload['lifts']} lifts known"
    out = [o for o in payload["out"] if o["status"] != "back"]
    if len(out) > MAX_OUT_SHARE * payload["lifts"]:
        return f"{len(out)} of {payload['lifts']} lifts out"
    return None


def parse_rit(body: bytes) -> list[tuple[str, str, str]]:
    """(service date, train number, "J" or "N") for each part of the train in one journey message.

    "N" as soon as NS marks one unit of that part not accessible, "J" when it marks all of them accessible;
    nothing when NS lists no units, or a unit without the mark. A train that continues under another
    number is one run with several parts (1778, then 2878), each with its own units.
    """
    try:
        body = gzip.decompress(body)
    except OSError:
        pass  # not compressed
    root = etree.fromstring(body)
    out = []
    for rit in root.iter("{*}RitInfo"):
        day = rit.findtext("{*}TreinDatum")
        for part in rit.iter("{*}LogischeRitDeel"):
            number = part.findtext("{*}LogischeRitDeelNummer")
            marks = [unit.findtext("{*}MaterieelDeelToegankelijk") for unit in part.iter("{*}MaterieelDeel")]
            if not day or not number or not marks:
                continue
            if "N" in marks:
                out.append((day, number, "N"))
            elif all(m == "J" for m in marks):
                out.append((day, number, "J"))
    return out


def _numbers(numbers) -> str:
    return " ".join(sorted(numbers, key=lambda n: (len(n), n)))  # train numbers in numeric order


@dataclass
class Trains:
    days: dict[str, dict[str, str]] = field(default_factory=dict)  # service date -> train number -> "J" or "N"

    def add(self, records: list[tuple[str, str, str]]) -> None:
        for day, number, mark in records:
            seen = self.days.setdefault(day, {})
            if seen.get(number) != "N":  # one unit with steps that day is enough
                seen[number] = mark

    def prune(self, today: date) -> None:
        oldest = (today - TRAINS_KEEP).isoformat()
        self.days = {d: v for d, v in self.days.items() if d >= oldest}

    def payload(self, now: datetime) -> dict:
        """What the build gets: per date, the train numbers that ran with accessible units only, and the others."""
        return {
            "v": 1,
            "updated": _iso(now),
            "days": {
                d: {"yes": _numbers(n for n, m in seen.items() if m == "J"), "no": _numbers(n for n, m in seen.items() if m == "N")}
                for d, seen in sorted(self.days.items())
            },
        }

    def save(self, path: Path) -> None:
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps({"days": self.days}, separators=(",", ":")))
        tmp.replace(path)

    @classmethod
    def load(cls, path: Path) -> Trains:
        return cls(json.loads(path.read_text())["days"]) if path.exists() else cls()


class Publisher:
    def __init__(self, account: str | None, namespace: str | None, token: str | None, dry_run_file: Path | None = None,
                 key: str = "lifts"):
        self.url = f"https://api.cloudflare.com/client/v4/accounts/{account}/storage/kv/namespaces/{namespace}/values/{key}"
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
            requests.put(self.url, headers=headers, data=body.encode(), timeout=60).raise_for_status()
        self.last_at, self.last_out = now, payload.get("out")


def _connect(ctx: zmq.Context, endpoint: str, envelope: bytes) -> zmq.Socket:
    sock = ctx.socket(zmq.SUB)
    sock.setsockopt(zmq.RCVTIMEO, 30_000)
    sock.setsockopt(zmq.TCP_KEEPALIVE, 1)
    sock.connect(endpoint)
    sock.setsockopt(zmq.SUBSCRIBE, envelope)
    log.info("connected to %s", endpoint)
    return sock


def _log_trains(trains: Trains, today: date) -> None:
    yesterday = trains.days.get((today - timedelta(days=1)).isoformat(), {})
    accessible = sum(1 for m in yesterday.values() if m == "J")
    log.info("trains published: %d days; yesterday %d trains, %d with accessible units only", len(trains.days), len(yesterday), accessible)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    state_file = Path(os.environ.get("STATE_FILE", "/data/state.json"))
    dry_run = os.environ.get("DRY_RUN") == "1"
    settings = {k: os.environ.get(k) for k in ("CF_ACCOUNT_ID", "CF_KV_NAMESPACE_ID", "CF_API_TOKEN")}
    if not dry_run and not all(settings.values()):
        sys.exit(f"missing settings in .env: {', '.join(k for k, v in settings.items() if not v)}")
    publisher = Publisher(*settings.values(), dry_run_file=state_file.with_name("lifts.json") if dry_run else None)
    trains_publisher = Publisher(*settings.values(), dry_run_file=state_file.with_name("trains-out.json") if dry_run else None, key="trains")
    trains_file = state_file.with_name("trains.json")
    state, trains = State.load(state_file), Trains.load(trains_file)
    log.info("state: %d lifts, full state from %s; trains on %d days%s",
             len(state.lifts), _iso(state.full_state_at), len(trains.days), " (dry run)" if dry_run else "")

    ctx, poller = zmq.Context(), zmq.Poller()
    feeds = {"lifts": (ENDPOINT, ENVELOPE, RECONNECT_AFTER), "trains": (RIT_ENDPOINT, RIT_ENVELOPE, RIT_RECONNECT_AFTER)}
    socks: dict[str, zmq.Socket] = {}
    seen: dict[str, datetime] = {}

    def connect(name: str) -> None:
        if name in socks:
            poller.unregister(socks[name])
            socks[name].close(linger=0)
        socks[name] = _connect(ctx, *feeds[name][:2])
        poller.register(socks[name], zmq.POLLIN)
        seen[name] = datetime.now(timezone.utc)

    for name in feeds:
        connect(name)
    trains_saved = datetime.now(timezone.utc)
    while True:
        ready = dict(poller.poll(30_000))
        now = datetime.now(timezone.utc)
        for name, sock in socks.items():
            if sock not in ready:
                continue
            parts = sock.recv_multipart()
            seen[name] = now
            if len(parts) < 2:
                continue
            try:
                if name == "trains":
                    trains.add(parse_rit(parts[1]))
                    continue
                conditions, _ = parse(parts[1])
            except etree.XMLSyntaxError as e:
                log.warning("unreadable %s message: %s", name, e)
                continue
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
                    back = sum(1 for o in payload["out"] if o["status"] == "back")
                    log.info("published: %d of %d lifts out, %d just back", len(payload["out"]) - back, payload["lifts"], back)
                except requests.RequestException as e:
                    log.warning("publishing failed: %s", e)

        if now - trains_saved >= TRAINS_SAVE_EVERY:
            trains.prune(now.date())
            trains.save(trains_file)
            trains_saved = now
        if trains.days and (trains_publisher.last_try is None or now - trains_publisher.last_try >= TRAINS_PUBLISH_EVERY):
            try:
                trains_publisher.publish(trains.payload(now), now)
                _log_trains(trains, now.date())
            except requests.RequestException as e:
                log.warning("publishing trains failed: %s", e)

        for name in list(socks):
            if now - seen[name] > feeds[name][2]:
                log.warning("%s: nothing received for %s; reconnecting", name, now - seen[name])
                connect(name)


if __name__ == "__main__":
    main()
