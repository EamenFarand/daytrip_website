import { describe, expect, it } from "vitest";

import { liftColor, parseColor } from "./colors";

describe("softening the dark map", () => {
  it("reads the colour forms the map style uses", () => {
    expect(parseColor("#000")).toEqual([0, 0, 0, 1]);
    expect(parseColor("#2a2a2a")).toEqual([42, 42, 42, 1]);
    expect(parseColor("rgb(27 ,27 ,29)")).toEqual([27, 27, 29, 1]); // spacing as in the real style
    expect(parseColor("rgba(60,60,60,0.8)")).toEqual([60, 60, 60, 0.8]);
    expect(parseColor("hsl(0,0%,50%)")!.map(Math.round)).toEqual([128, 128, 128, 1]);
    expect(parseColor("hsla(120,100%,25%,0.5)")!.map((v) => Math.round(v * 10) / 10)).toEqual([0, 127.5, 0, 0.5]);
    expect(parseColor("zoom")).toBeNull();
  });

  it("turns the near-black background into soft grey and keeps transparency", () => {
    expect(liftColor("rgb(12,12,12)", 0.125)).toBe("rgba(42,42,42,1)");
    expect(liftColor("rgba(0,0,0,0.7)", 0.125)).toBe("rgba(32,32,32,0.7)");
  });

  it("changes only the colours inside an expression", () => {
    const expr = ["interpolate", ["linear"], ["zoom"], 5.8, "#000", 10, "hsl(0,0%,100%)"];
    expect(liftColor(expr, 0.5)).toEqual(["interpolate", ["linear"], ["zoom"], 5.8, "rgba(128,128,128,1)", 10, "rgba(255,255,255,1)"]);
  });
});
