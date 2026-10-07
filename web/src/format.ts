// Wording for times, frequencies and statuses, in the page's language (i18n.ts).

import { LOCALE, type Lang, lang, tr } from "./i18n.ts"; // with .ts: scripts/pages.ts runs this file in Node
import type { Access, TrackAccess } from "./types";

export function duration(minutes: number): string {
  if (minutes < 60) return `${minutes} min`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return tr({ nl: m === 0 ? `${h} uur` : `${h} u ${m} min`, en: m === 0 ? `${h} hr` : `${h} hr ${m} min` });
}

export function changes(n: number): string {
  if (n === 0) return "direct";
  return tr({ nl: n === 1 ? "1 overstap" : `${n} overstappen`, en: n === 1 ? "1 change" : `${n} changes` });
}

/** Departures per hour, averaged over a window of `hours` (`window` from windowText). */
export function frequency(perHour: number, hours: number, window: string): string {
  if (perHour >= 0.95) return tr({ nl: `${Math.round(perHour)}× per uur`, en: `${Math.round(perHour)}× an hour` });
  const count = Math.max(1, Math.round(perHour * hours));
  return tr({ nl: `${count}× tussen ${window}`, en: `${count}× between ${window}` });
}

export function clock(minutesAfterMidnight: number): string {
  const h = Math.floor(minutesAfterMidnight / 60);
  const m = minutesAfterMidnight % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

/** The departure window, to follow "tussen" / "between": "08:30 en 12:00". */
export function windowText(start: number, end: number): string {
  return tr({ nl: `${clock(start)} en ${clock(end)}`, en: `${clock(start)} and ${clock(end)}` });
}

export function longDate(iso: string): string {
  return new Date(`${iso}T12:00:00`).toLocaleDateString(LOCALE[lang], { weekday: "long", day: "numeric", month: "long", year: "numeric" });
}

export function shortDate(iso: string): string {
  return new Date(`${iso.slice(0, 10)}T12:00:00`).toLocaleDateString(LOCALE[lang], { day: "numeric", month: "short", year: "numeric" });
}

/** "A, B en C" / "A, B and C" */
export function listText(parts: string[]): string {
  return new Intl.ListFormat(LOCALE[lang], { style: "long", type: "conjunction" }).format(parts);
}

export function upperFirst(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** The page title: the home page, or a station's page (also used by scripts/pages.ts). */
export function pageTitle(stationName?: string): string {
  return stationName
    ? tr({ nl: `Met de kinderwagen vanaf ${stationName} – Trapvrij`, en: `With a pram from ${stationName} – Trapvrij` })
    : tr({ nl: "Trapvrij – waar kun je heen met de kinderwagen?", en: "Trapvrij – where can you go with a pram?" });
}

export const originText = (): string => tr({ nl: "Vertrekstation", en: "Starting station" });
export const outOfReach = (): string => tr({ nl: "Niet bereikbaar binnen je keuzes", en: "Not reachable within your choices" });

const ACCESS: Record<Access, Record<Lang, string>> = {
  yes: { nl: "Drempelvrij", en: "Step-free" },
  partial: { nl: "Deels drempelvrij (niet elk spoor)", en: "Partly step-free (not every platform)" },
  no: { nl: "Niet drempelvrij", en: "Not step-free" },
  unknown: { nl: "Toegankelijkheid onbekend", en: "Accessibility unknown" },
};

export const accessText = (a: Access): string => tr(ACCESS[a]);

const TRACK: Record<TrackAccess, Record<Lang, string>> = {
  yes: { nl: "drempelvrij", en: "step-free" },
  no: { nl: "niet drempelvrij", en: "not step-free" },
  unknown: { nl: "onbekend", en: "unknown" },
};

export const trackText = (t: TrackAccess): string => tr(TRACK[t]);

/** "spoor 14/15" / "platform 14/15" (a Dutch "spoor" is a numbered platform edge, as NS's English site calls it). */
export function platformText(tracks: string[]): string {
  return tr({ nl: `spoor ${tracks.join("/")}`, en: `platform ${tracks.join("/")}` });
}

/** Icon glyphs that go with the status text (never shown without it). */
export const ACCESS_ICON: Record<Access, string> = {
  yes: "✓",
  partial: "◐",
  no: "✕",
  unknown: "?",
};
