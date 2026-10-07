import fs from "node:fs";
import path from "node:path";

import { afterEach, describe, expect, it } from "vitest";

import { changes, duration, frequency, listText, longDate, pageTitle, windowText } from "./format";
import { inLang, useLang } from "./i18n";
import { pagePath, stationFromPath } from "./state";

afterEach(() => useLang("nl"));

describe("languages", () => {
  it("speaks Dutch unless told otherwise", () => {
    expect(changes(2)).toBe("2 overstappen");
    useLang("en");
    expect(changes(2)).toBe("2 changes");
  });

  it("says times, frequencies and dates in English", () => {
    useLang("en");
    expect([duration(45), duration(60), duration(75)]).toEqual(["45 min", "1 hr", "1 hr 15 min"]);
    expect(changes(0)).toBe("direct");
    expect(frequency(4, 3.5, windowText(510, 720))).toBe("4× an hour");
    expect(frequency(0.3, 3.5, windowText(510, 720))).toBe("1× between 08:30 and 12:00");
    expect(longDate("2026-11-04")).toMatch(/^Wednesday,? 4 November 2026$/); // the comma depends on the ICU version
    expect(listText(["A", "B", "C"])).toBe("A, B and C");
    expect(pageTitle("Houten")).toBe("With a pram from Houten – Trapvrij");
  });

  it("switches a page and its view to the other language", () => {
    expect(inLang("/", "en")).toBe("/en/");
    expect(inLang("/station/houten/#dag=zaterdag", "en")).toBe("/en/station/houten/#dag=zaterdag");
    expect(inLang("/en/station/houten/#dag=zaterdag", "nl")).toBe("/station/houten/#dag=zaterdag");
    expect(inLang("/en/#overstap=2", "nl")).toBe("/#overstap=2");
    expect(inLang("/en", "nl")).toBe("/");
    expect(inLang("/en/", "en")).toBe("/en/");
  });

  it("keeps English pages under /en/", () => {
    expect(stationFromPath("/en/station/houten-castellum/")).toBe("houten-castellum");
    expect(stationFromPath("/en/")).toBeNull();
    expect(stationFromPath("/entree/station/x/")).toBeNull();
    expect(pagePath("houten-castellum", "en")).toBe("/en/station/houten-castellum/");
    expect(pagePath(null, "en")).toBe("/en/");
    useLang("en");
    expect(pagePath(null)).toBe("/en/");
  });
});

describe("the two page shells", () => {
  const read = (rel: string) => fs.readFileSync(path.join(import.meta.dirname, "..", rel), "utf-8");
  /** Every tag with the attributes the app and the styles use; no text, and not the language switch (it differs on purpose). */
  const KEEP = new Set(["id", "class", "name", "value", "type", "for", "src", "role", "hidden", "disabled", "tabindex", "rel", "hreflang", "property"]);
  const skeleton = (html: string) =>
    [...html.replace(/<nav class="lang"[\s\S]*?<\/nav>/, "").matchAll(/<([a-z][a-z0-9]*)\b([^>]*)>/g)].map(([, tag, attrs]) => {
      const kept = [...attrs.matchAll(/([a-z][a-z0-9:-]*)(?:="[^"]*")?/g)].filter(([, name]) => KEEP.has(name) || name.startsWith("data-"));
      return [tag, ...kept.map((m) => m[0])].join(" ");
    });
  const nl = read("index.html");
  const en = read("en/index.html");

  it("are the same page: same elements in the same order", () => {
    expect(skeleton(en)).toEqual(skeleton(nl));
  });

  it("each say their own language, link to each other and to their own switch target", () => {
    expect(nl).toContain('<html lang="nl">');
    expect(en).toContain('<html lang="en">');
    expect(nl).toContain('<link rel="canonical" href="https://trapvrij.nl/" />');
    expect(en).toContain('<link rel="canonical" href="https://trapvrij.nl/en/" />');
    for (const html of [nl, en]) {
      expect(html).toContain('<link rel="alternate" hreflang="nl" href="https://trapvrij.nl/" />');
      expect(html).toContain('<link rel="alternate" hreflang="en" href="https://trapvrij.nl/en/" />');
    }
    expect(nl).toContain('<a id="lang-switch" href="/en/" hreflang="en" lang="en">');
    expect(en).toContain('<a id="lang-switch" href="/" hreflang="nl" lang="nl">');
  });
});
