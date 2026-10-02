// Travel-time bands, quick -> slow. Validated as ordinal ramps (dataviz skill) on each base map;
// the dark one on the softened grey map (#2a2a2a), where every step clears 3:1.
// Kept apart from map.ts so the list can use them without loading the map library.
export const RAMP = {
  light: ["#0d366b", "#184f95", "#256abf", "#3987e5", "#6da7ec"],
  dark: ["#e1edfd", "#b7d3f6", "#86b6ef", "#5598e7", "#2a78d6"],
};

/** Parse the colour forms map styles use: #rgb, #rrggbb, rgb(), rgba(), hsl(), hsla(). */
export function parseColor(text: string): [number, number, number, number] | null {
  const s = text.trim().toLowerCase();
  let m = s.match(/^#([0-9a-f]{3}|[0-9a-f]{6})$/);
  if (m) {
    const hex = m[1].length === 3 ? [...m[1]].map((c) => c + c).join("") : m[1];
    const [r, g, b] = [0, 2, 4].map((i) => parseInt(hex.slice(i, i + 2), 16));
    return [r, g, b, 1];
  }
  m = s.match(/^rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*(?:,\s*([\d.]+)\s*)?\)$/);
  if (m) return [+m[1], +m[2], +m[3], m[4] === undefined ? 1 : +m[4]];
  m = s.match(/^hsla?\(\s*([\d.]+)\s*,\s*([\d.]+)%\s*,\s*([\d.]+)%\s*(?:,\s*([\d.]+)\s*)?\)$/);
  if (m) {
    const [h, sat, l] = [+m[1] / 360, +m[2] / 100, +m[3] / 100];
    const q = l < 0.5 ? l * (1 + sat) : l + sat - l * sat;
    const p = 2 * l - q;
    const channel = (t: number) => {
      t = (t + 1) % 1;
      return 255 * (t < 1 / 6 ? p + (q - p) * 6 * t : t < 1 / 2 ? q : t < 2 / 3 ? p + (q - p) * (2 / 3 - t) * 6 : p);
    };
    return [channel(h + 1 / 3), channel(h), channel(h - 1 / 3), m[4] === undefined ? 1 : +m[4]];
  }
  return null;
}

/** Mix a colour, or every colour inside a map-style expression, toward white by `amount` (0..1). */
export function liftColor(value: unknown, amount: number): unknown {
  if (Array.isArray(value)) return value.map((v) => liftColor(v, amount));
  if (typeof value !== "string") return value;
  const c = parseColor(value);
  if (!c) return value; // not a colour, e.g. "zoom" inside an expression
  const [r, g, b] = c.slice(0, 3).map((v) => Math.round(v + (255 - v) * amount));
  return `rgba(${r},${g},${b},${c[3]})`;
}
