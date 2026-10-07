// The site in Dutch (the default, at /) and English (under /en/), DECISIONS 2026-10-07.
// A page's language is its <html lang>: the app reads it once, and scripts/pages.ts switches it for each
// page it writes. Texts sit where they're used, as { nl, en } pairs, so neither language can be missing.

export type Lang = "nl" | "en";

/** The page's language. In the browser it comes from <html lang>; in tests and scripts/pages.ts it's Dutch until useLang. */
export let lang: Lang = typeof document !== "undefined" && document.documentElement.lang === "en" ? "en" : "nl";

export function useLang(l: Lang): void {
  lang = l;
}

/** The text in the page's language. */
export function tr(text: Record<Lang, string>): string {
  return text[lang];
}

/** Dates and lists: Dutch, or British English (day before month, 24-hour clock). */
export const LOCALE: Record<Lang, string> = { nl: "nl-NL", en: "en-GB" };

/** Where each language's pages live: /station/x/ and /en/station/x/. */
export const PREFIX: Record<Lang, string> = { nl: "", en: "/en" };

export const other = (l: Lang): Lang => (l === "nl" ? "en" : "nl");

/** The same page and view in another language: /station/x/#dag=zaterdag -> /en/station/x/#dag=zaterdag. */
export function inLang(url: string, to: Lang): string {
  const bare = url.replace(/^\/en(?=[/?#]|$)/, "");
  return PREFIX[to] + (bare.startsWith("/") ? bare : `/${bare}`);
}
