"""Q5: log the live lift-status feed (SIRI-FM) to disk for later analysis.

Source: NDOV Loket best-effort ZeroMQ stream (CC0), envelope /DOVA/ServiceDelivery,
tcp://pubsub.besteffort.ndovloket.nl:7666. Per the SIRI-NL FM spec (TMI9 v9.0):
status changes are pushed as they happen, the full state of all lifts is pushed
once a day, and a heartbeat arrives every 60 minutes.

Fair use: exactly one connection, subscribed only to the DOVA envelopes.

Usage:  uv run python lift_listener.py [hours]      (default 72)
Writes: data/raw/lifts/siri_fm_YYYY-MM-DD.jsonl  (one line per FacilityCondition)
"""

from __future__ import annotations

import gzip
import json
import sys
import time
from datetime import datetime, timezone

import zmq
from lxml import etree

from fetch import RAW

ENDPOINT = "tcp://pubsub.besteffort.ndovloket.nl:7666"
ENVELOPE = b"/DOVA/"
S = "{http://www.siri.org.uk/siri}"
OUT = RAW / "lifts"


def decode(body: bytes) -> bytes:
    try:
        return gzip.decompress(body)
    except OSError:
        return body


def conditions(xml: bytes) -> list[dict]:
    root = etree.fromstring(xml)
    rows = []
    for d in root.iter(S + "FacilityMonitoringDelivery"):
        ts = d.findtext(S + "ResponseTimestamp")
        n = len(d.findall(S + "FacilityCondition"))
        for fc in d.iterfind(S + "FacilityCondition"):
            rows.append(
                {
                    "delivery_ts": ts,
                    "delivery_size": n,
                    "facility": fc.findtext(S + "FacilityRef"),
                    "status": fc.findtext(f"{S}FacilityStatus/{S}Status"),
                    "description": fc.findtext(f"{S}FacilityStatus/{S}Description"),
                    "start": fc.findtext(f"{S}ValidityPeriod/{S}StartTime"),
                    "end": fc.findtext(f"{S}ValidityPeriod/{S}EndTime"),
                }
            )
    if root.find(f".//{S}HeartbeatNotification") is not None or root.tag == S + "HeartbeatNotification":
        rows.append({"heartbeat": True})
    return rows


def main(hours: float) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    ctx = zmq.Context()
    sock = ctx.socket(zmq.SUB)
    sock.setsockopt(zmq.RCVTIMEO, 30_000)
    sock.setsockopt(zmq.TCP_KEEPALIVE, 1)
    sock.connect(ENDPOINT)
    sock.setsockopt(zmq.SUBSCRIBE, ENVELOPE)
    stop_at = time.time() + hours * 3600
    while time.time() < stop_at:
        try:
            parts = sock.recv_multipart()
        except zmq.Again:
            continue
        now = datetime.now(timezone.utc)
        envelope = parts[0].decode(errors="replace")
        try:
            rows = conditions(decode(parts[1]))
        except etree.XMLSyntaxError as e:
            rows = [{"parse_error": str(e)}]
        with (OUT / f"siri_fm_{now:%Y-%m-%d}.jsonl").open("a", encoding="utf-8") as f:
            for r in rows or [{"empty": True}]:
                f.write(json.dumps({"received": now.isoformat(), "envelope": envelope, **r}) + "\n")


if __name__ == "__main__":
    main(float(sys.argv[1]) if len(sys.argv) > 1 else 72)
