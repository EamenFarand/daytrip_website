import { describe, expect, it } from "vitest";

import { freshness, freshnessText, journeyWarnings, liftNote, outAt, statusText, warnLine } from "./lifts";
import type { LiftStatus, Station } from "./types";

const st = (code: string, lifts: string[] = []): Station => ({
  code, name: code, slug: code.toLowerCase(), trains: 1, aliases: [], lat: 52, lon: 5, status: "yes", tracks: {}, source: "EPIAP",
  source_date: null, verified: null, notes: [], uic: null, lifts: lifts.map((id) => ({ id, code: `${code}-LIF-${id}`, tracks: ["1"] })),
});

const NOW = new Date("2026-10-02T12:00:00Z");
const LIFTS: LiftStatus = {
  v: 1, updated: "2026-10-02T11:58:00Z", full_state_at: "2026-10-02T02:02:00Z", last_message_at: "2026-10-02T11:55:00Z", lifts: 443,
  out: [{ id: "u1", status: "notAvailable", since: "2026-10-01T08:00:00Z", until: null }, { id: "d1", status: "unknown", since: null, until: null }],
};

describe("lift status", () => {
  it("is live while changes come in, nightly when they stop, unknown when old or missing", () => {
    expect(freshness(LIFTS, NOW)).toBe("live");
    expect(freshness({ ...LIFTS, last_message_at: "2026-10-02T09:00:00Z" }, NOW)).toBe("nightly"); // the stream went quiet
    expect(freshness({ ...LIFTS, updated: "2026-10-02T10:00:00Z" }, NOW)).toBe("nightly"); // the listener stopped publishing
    expect(freshness({ ...LIFTS, full_state_at: "2026-09-30T02:02:00Z" }, NOW)).toBe("unknown");
    expect(freshness(null, NOW)).toBe("unknown");
    expect(freshnessText(null, "unknown")).toContain("niet bekend");
  });

  it("old data shows no outages at all, rather than old ones", () => {
    expect(outAt(st("UT", ["u1", "u2"]), LIFTS, "live").map((o) => o.lift.id)).toEqual(["u1"]);
    expect(outAt(st("UT", ["u1", "u2"]), LIFTS, "unknown")).toEqual([]);
  });

  it("warns for the origin, every change and the destination", () => {
    const O = st("O"), UT = st("UT", ["u1"]), D = st("D", ["d1"]);
    const byCode = new Map([O, UT, D].map((s) => [s.code, s]));
    const w = journeyWarnings([40, 40, 2, 1, "UT"], O, D, byCode, LIFTS, "live");
    expect(w.map((x) => [x.station.code, x.role, x.out.map((o) => o.status)])).toEqual([
      ["UT", "overstap", ["notAvailable"]],
      ["D", "aankomst", ["unknown"]],
    ]);
    expect(journeyWarnings(null, O, D, byCode, LIFTS, "live")).toEqual([]);
  });

  it("only warns about lifts for the tracks the journey uses; hall lifts not when changing", () => {
    const hall = (code: string, id: string): Station => ({ ...st(code), lifts: [{ id, code: `${code}-LIF-${id}`, tracks: [] }] });
    const O = hall("O", "d1"), UT = st("UT", ["u1"]), D = st("D", ["d1"]); // u1 and d1 serve track 1
    const byCode = new Map([O, UT, D].map((s) => [s.code, s]));
    const codes = (tracks: string) =>
      journeyWarnings([40, 40, 2, 1, "UT", tracks], O, D, byCode, LIFTS, "live").map((w) => `${w.station.code}:${w.role}`);
    expect(codes("2|18|5|3")).toEqual(["O:vertrek"]); // the origin's hall lift; tracks 18, 5 and 3 have no lift out
    expect(codes("2|1a|5|1")).toEqual(["O:vertrek", "UT:overstap", "D:aankomst"]); // arriving on 1a uses track 1's lift
    expect(codes("2|?|5|3")).toEqual(["O:vertrek", "UT:overstap"]); // an unknown track counts
    const UThall = hall("UT", "u1");
    expect(journeyWarnings([40, 40, 2, 1, "UT", "2|1|1|3"], st("O"), D, new Map([["UT", UThall]]), LIFTS, "live")).toEqual([]);
  });

  it("a lift that has just come back still warns, in its own words", () => {
    const UT = st("UT", ["u1", "b1"]), D = st("D", ["b2"]);
    const lifts: LiftStatus = {
      ...LIFTS,
      out: [...LIFTS.out, { id: "b1", status: "back", since: "2026-10-02T11:43:00Z", until: null }, { id: "b2", status: "back", since: "2026-10-02T11:50:00Z", until: null }],
    };
    const b1 = outAt(UT, lifts, "live").find((o) => o.lift.id === "b1")!;
    expect(statusText(b1)).toMatch(/^sinds \d\d:\d\d weer in gebruik, maar was net nog buiten gebruik$/); // local time
    const w = journeyWarnings([40, 40, 2, 1, "UT"], st("O"), D, new Map([UT, D].map((s) => [s.code, s])), lifts, "live");
    expect(w.map(liftNote)).toEqual(["⚠ lift buiten gebruik", "⚠ lift net weer in gebruik"]); // at UT one is out, one back
    expect(warnLine(w)).toBe("⚠ Liftstoring: UT; lift net weer in gebruik: D");
    expect(warnLine(w.slice(1))).toBe("⚠ Lift net weer in gebruik: D");
  });
});
