import { describe, expect, it } from "vitest";

import { band, level, originUsable, verdicts } from "./results";
import { DEFAULTS, MAX_MINUTES, fromHash, pagePath, stationFromPath, toHash, type State } from "./state";
import type { OriginDoc, Station } from "./types";

const st = (code: string, status: Station["status"] = "yes"): Station => ({
  code, name: code, slug: code.toLowerCase(), trains: 1, aliases: [], lat: 52, lon: 5, status, tracks: {}, source: "EPIAP",
  source_date: null, verified: null, notes: [], uic: null, lifts: [],
});

const DOC: OriginDoc = {
  v: 1,
  origin: "O",
  built: "",
  results: {
    weekday: {
      stroller: {
        sprinter: {
          A: [[13, 13, 4, 0]], // direct, same for every change limit
          B: [null, [49, 49, 4, 1, "A"]], // needs a change
          C: [null, null, [150, 140, 2, 2, "A|B"]], // two changes, long
        },
        all: {},
      },
      any: { sprinter: {}, all: {} },
    },
  },
};

describe("results", () => {
  const stations = [st("O"), st("A"), st("B"), st("C"), st("X", "no"), st("Y", "unknown"), st("Z")];
  const state: State = { ...DEFAULTS, origin: "O", maxChanges: 1, maxMinutes: 120 };
  const byCode = (s: State) => Object.fromEntries(verdicts(stations, DOC, s).map((v) => [v.station.code, v.category]));

  it("reads the trailing-copies encoding", () => {
    expect(level([[13, 13, 4, 0]], 2)).toEqual([13, 13, 4, 0]);
    expect(level([null, [49, 49, 4, 1]], 0)).toBeNull();
    expect(level(undefined, 1)).toBeNull();
  });

  it("classifies stations by filters and accessibility", () => {
    expect(byCode(state)).toEqual({
      O: "origin", A: "reachable", B: "reachable", C: "out-of-reach", X: "not-step-free", Y: "unknown-access", Z: "out-of-reach",
    });
  });

  it("needs two changes and no time limit for C", () => {
    expect(byCode({ ...state, maxChanges: 2 }).C).toBe("out-of-reach"); // 150 min > 120
    expect(byCode({ ...state, maxChanges: 2, maxMinutes: MAX_MINUTES }).C).toBe("reachable");
  });

  it("without a pram, accessibility doesn't block", () => {
    const any = verdicts(stations, DOC, { ...state, profile: "any" });
    expect(any.find((v) => v.station.code === "X")?.category).toBe("out-of-reach");
  });

  it("before an origin is chosen, step-free stations are idle", () => {
    expect(byCode({ ...state, origin: null }).A).toBe("idle");
  });

  it("without results (loading, or an origin a pram can't use), nothing is called out of reach", () => {
    const waiting = Object.fromEntries(verdicts(stations, null, state).map((v) => [v.station.code, v.category]));
    expect(waiting).toMatchObject({ O: "origin", A: "idle", Z: "idle", X: "not-step-free", Y: "unknown-access" });
  });

  it("an origin without step-free access can't be used with a pram", () => {
    expect(originUsable(st("X", "no"), state)).toBe(false);
    expect(originUsable(st("P", "partial"), state)).toBe(true);
    expect(originUsable(st("X", "no"), { ...state, profile: "any" })).toBe(true);
  });

  it("bands travel times", () => {
    expect([13, 30, 31, 90, 121, 400].map(band)).toEqual([0, 0, 1, 2, 4, 4]);
  });
});

describe("state in the URL", () => {
  const known = (c: string) => ["HTNC", "UT"].includes(c);

  it("round-trips everything but the origin, which is in the path", () => {
    const s: State = { origin: "HTNC", profile: "any", trains: "all", day: "saturday", maxChanges: 2, maxMinutes: MAX_MINUTES, selected: "UT" };
    expect(fromHash(toHash(s), known)).toEqual({ ...s, origin: null });
  });

  it("keeps defaults and the origin out of the hash", () => {
    expect(toHash({ ...DEFAULTS, origin: "HTNC" })).toBe("");
    expect(toHash({ ...DEFAULTS, maxChanges: 2 })).toBe("#overstap=2");
  });

  it("a missing value means the default, not zero; old #van= links still work", () => {
    expect(fromHash("#van=HTNC", known)).toEqual({ ...DEFAULTS, origin: "HTNC" });
  });

  it("ignores unknown or bad values", () => {
    expect(fromHash("#van=NOPE&overstap=7&max=13&profiel=raket", known)).toEqual(DEFAULTS);
  });

  it("reads the station page from the path, and back", () => {
    expect(stationFromPath("/station/houten-castellum/")).toBe("houten-castellum");
    expect(stationFromPath("/station/s-hertogenbosch")).toBe("s-hertogenbosch");
    expect(stationFromPath("/station/")).toBeNull();
    expect(stationFromPath("/station/UT")).toBeNull(); // old code links are redirected by _redirects
    expect(stationFromPath("/")).toBeNull();
    expect(pagePath("houten-castellum")).toBe("/station/houten-castellum/");
    expect(pagePath(null)).toBe("/");
  });
});
