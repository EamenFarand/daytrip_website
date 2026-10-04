// Dutch wording for times, frequencies and statuses.

import type { Access, TrackAccess } from "./types";

export function duration(minutes: number): string {
  if (minutes < 60) return `${minutes} min`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return m === 0 ? `${h} uur` : `${h} u ${m} min`;
}

export function changes(n: number): string {
  if (n === 0) return "direct";
  return n === 1 ? "1 overstap" : `${n} overstappen`;
}

/** Departures per hour, averaged over a window of `hours`. */
export function frequency(perHour: number, hours: number, window: string): string {
  if (perHour >= 0.95) return `${Math.round(perHour)}× per uur`;
  const count = Math.max(1, Math.round(perHour * hours));
  return `${count}× tussen ${window}`;
}

export function clock(minutesAfterMidnight: number): string {
  const h = Math.floor(minutesAfterMidnight / 60);
  const m = minutesAfterMidnight % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

export function longDate(iso: string): string {
  return new Date(`${iso}T12:00:00`).toLocaleDateString("nl-NL", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
}

export function shortDate(iso: string): string {
  return new Date(`${iso.slice(0, 10)}T12:00:00`).toLocaleDateString("nl-NL", { day: "numeric", month: "short", year: "numeric" });
}

export function upperFirst(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** The page title: the home page, or a station's page (also used by scripts/pages.ts). */
export function pageTitle(stationName?: string): string {
  return stationName ? `Met de kinderwagen vanaf ${stationName} – Trapvrij` : "Trapvrij – waar kun je heen met de kinderwagen?";
}

export const ACCESS_TEXT: Record<Access, string> = {
  yes: "Drempelvrij",
  partial: "Deels drempelvrij (niet elk spoor)",
  no: "Niet drempelvrij",
  unknown: "Toegankelijkheid onbekend",
};

export const TRACK_TEXT: Record<TrackAccess, string> = {
  yes: "drempelvrij",
  no: "niet drempelvrij",
  unknown: "onbekend",
};

/** Icon glyphs that go with the status text (never shown without it). */
export const ACCESS_ICON: Record<Access, string> = {
  yes: "✓",
  partial: "◐",
  no: "✕",
  unknown: "?",
};
