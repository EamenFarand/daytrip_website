import { afterEach, describe, expect, it } from "vitest";

import { useLang } from "../src/i18n";
import type { OriginDoc, Station } from "../src/types";
import { esc, langSwitch, notFound, reachable, redirects, sitemap, stationPage, stationText } from "./pages";

const st = (code: string, name: string, extra: Partial<Station> = {}): Station => ({
  code, name, slug: name.toLowerCase().replace(/[^a-z0-9]+/g, "-"), trains: 100, aliases: [], lat: 52, lon: 5, status: "yes",
  tracks: {}, source: "EPIAP", source_date: "2026-10-02", verified: null, notes: [], uic: null, lifts: [], ...extra,
});

const HTNC = st("HTNC", "Houten Castellum", { lifts: [{ id: "1", code: "HTNC-LIF-001", tracks: ["1"] }, { id: "2", code: "HTNC-LIF-002", tracks: ["2"] }] });
const UT = st("UT", "Utrecht Centraal", { trains: 2000 });
const HTN = st("HTN", "Houten");
const ASD = st("ASD", "Amsterdam Centraal", { trains: 1800 });
const BYCODE = new Map([HTNC, UT, HTN, ASD].map((s) => [s.code, s]));

const DOC: OriginDoc = {
  v: 1, origin: "HTNC", built: "",
  results: {
    weekday: {
      stroller: {
        sprinter: { UT: [[13, 13, 4, 0]], HTN: [[3, 3, 4, 0]], ASD: [null, [49, 49, 4, 1, "UT"]] },
        all: {},
      },
      any: { sprinter: {}, all: {} },
    },
  },
};

const TEMPLATE = `<!doctype html><html lang="nl"><head>
<meta name="description" content="home" />
<title>Trapvrij – home</title>
<link rel="canonical" href="https://trapvrij.nl/" />
<link rel="alternate" hreflang="nl" href="https://trapvrij.nl/" />
<link rel="alternate" hreflang="en" href="https://trapvrij.nl/en/" />
<link rel="alternate" hreflang="x-default" href="https://trapvrij.nl/" />
<meta property="og:title" content="home" />
<meta property="og:description" content="home" />
<meta property="og:url" content="https://trapvrij.nl/" />
<script type="module" src="/assets/app.js"></script>
</head><body><h1>Trapvrij</h1><a id="lang-switch" href="/en/" hreflang="en" lang="en">EN</a>
<section id="intro" class="intro" hidden></section>
<input id="origin" type="text" autocomplete="off" /></body></html>`;

afterEach(() => useLang("nl"));

describe("station pages", () => {
  it("summarises what you reach with a pram, with links to those stations", () => {
    expect(reachable(DOC, BYCODE, "stroller", 30).map((r) => r.station.code)).toEqual(["HTN", "UT"]);
    const text = stationText(HTNC, DOC, BYCODE);
    expect(text.title).toBe("Met de kinderwagen vanaf Houten Castellum – Trapvrij");
    expect(text.intro).toContain("Houten Castellum is drempelvrij");
    expect(text.intro).toContain("2 liften");
    expect(text.intro).toContain('2 stations binnen 30 minuten, zoals <a href="/station/houten/">Houten</a> (3 min) en <a href="/station/utrecht-centraal/">Utrecht Centraal</a> (13 min)');
    expect(text.intro).toContain('Binnen een uur zijn het er 3, onder andere <a href="/station/amsterdam-centraal/">Amsterdam Centraal</a> (49 min)');
    expect(text.description).toBe("Houten Castellum met de kinderwagen: 2 stations zonder trappen binnen 30 minuten, 3 binnen een uur. Met reistijden, overstappen en liften.");
  });

  it("says plainly when a station isn't step-free", () => {
    const text = stationText(st("VG", "Vught", { status: "no" }), null, BYCODE);
    expect(text.intro).toContain("Vught is niet drempelvrij");
    expect(text.intro).toContain("binnen 30 minuten geen ander station");
  });

  it("fills the template in: title, canonical, heading, intro and origin", () => {
    const html = stationPage(TEMPLATE, HTNC, stationText(HTNC, DOC, BYCODE));
    expect(html).toContain("<title>Met de kinderwagen vanaf Houten Castellum – Trapvrij</title>");
    expect(html).toContain('<link rel="canonical" href="https://trapvrij.nl/station/houten-castellum/" />');
    expect(html).toContain('<p class="brand"><a href="/">Trapvrij</a></p>');
    expect(html).toContain('<section id="intro" class="intro" data-station="HTNC"');
    expect(html).toContain('value="Houten Castellum"');
    expect(html.match(/<h1/g)).toHaveLength(1);
  });

  it("links each page to its twin in the other language", () => {
    const html = stationPage(TEMPLATE, HTNC, stationText(HTNC, DOC, BYCODE));
    expect(html).toContain('<link rel="alternate" hreflang="nl" href="https://trapvrij.nl/station/houten-castellum/" />');
    expect(html).toContain('<link rel="alternate" hreflang="en" href="https://trapvrij.nl/en/station/houten-castellum/" />');
    expect(html).toContain('<link rel="alternate" hreflang="x-default" href="https://trapvrij.nl/station/houten-castellum/" />');
    expect(html).toContain('id="lang-switch" href="/en/station/houten-castellum/"');
  });

  it("writes the English page under /en/, linking to English pages", () => {
    useLang("en");
    const text = stationText(HTNC, DOC, BYCODE);
    expect(text.title).toBe("With a pram from Houten Castellum – Trapvrij");
    expect(text.intro).toContain("Houten Castellum is step-free: you can reach every platform without stairs.");
    expect(text.intro).toContain("The station has 2 lifts.");
    expect(text.intro).toContain(
      'you can reach 2 stations within 30 minutes on a weekday, such as <a href="/en/station/houten/">Houten</a> (3 min) and <a href="/en/station/utrecht-centraal/">Utrecht Centraal</a> (13 min).',
    );
    expect(text.intro).toContain('Within an hour it\'s 3, including <a href="/en/station/amsterdam-centraal/">Amsterdam Centraal</a> (49 min).');
    expect(text.description).toBe("Houten Castellum with a pram: 2 stations without stairs within 30 minutes, 3 within an hour. With travel times, changes and lifts.");
    const html = stationPage(TEMPLATE.replace('lang="nl"', 'lang="en"'), HTNC, text);
    expect(html).toContain('<link rel="canonical" href="https://trapvrij.nl/en/station/houten-castellum/" />');
    expect(html).toContain('<meta property="og:url" content="https://trapvrij.nl/en/station/houten-castellum/" />');
    expect(html).toContain('<p class="brand"><a href="/en/">Trapvrij</a></p>');
    expect(html).toContain('id="lang-switch" href="/station/houten-castellum/"');
  });

  it("names the step-free platforms of a partly step-free station", () => {
    const BLB = st("BLB", "Blerick", { status: "partial", tracks: { "1": "yes", "2": "no", "3": "yes" } });
    expect(stationText(BLB, null, BYCODE).intro).toContain("Zonder trappen: spoor 1 en 3.");
    useLang("en");
    expect(stationText(BLB, null, BYCODE).intro).toContain("Without stairs: platforms 1 and 3.");
  });

  it("the language switch shows NL | EN, the current one marked", () => {
    expect(langSwitch("/station/")).toMatch(/aria-label="Taal">\s*<span aria-current="true">NL.*\s*<a id="lang-switch" href="\/en\/station\/" hreflang="en" lang="en">EN/);
    useLang("en");
    expect(langSwitch("/station/")).toMatch(/aria-label="Language">\s*<a id="lang-switch" href="\/station\/" hreflang="nl" lang="nl">NL.*\s*<span aria-current="true">EN/);
  });

  it("the 404 page is not indexed and has no addresses of its own", () => {
    useLang("en");
    const html = notFound(TEMPLATE);
    expect(html).toContain('<meta name="robots" content="noindex" />');
    expect(html).not.toMatch(/rel="(canonical|alternate)"/);
    expect(html).not.toContain("<script");
    expect(html).toContain("<h1>Page not found</h1>");
    expect(html).toContain('href="/en/station/"');
  });

  it("escapes names", () => {
    expect(esc("'s-Hertogenbosch <x>")).toBe("&#39;s-Hertogenbosch &lt;x&gt;");
  });

  it("lists every page in the sitemap, in both languages, and redirects old code links", () => {
    expect(sitemap([UT], "2026-10-02")).toContain("<loc>https://trapvrij.nl/station/utrecht-centraal/</loc><lastmod>2026-10-02</lastmod>");
    expect(sitemap([UT], "2026-10-02")).toContain("<loc>https://trapvrij.nl/en/station/utrecht-centraal/</loc>");
    expect(sitemap([UT], "2026-10-02").match(/<url>/g)).toHaveLength(6); // /, /station/ and the station, twice
    expect(redirects([UT])).toContain("/station/UT  /station/utrecht-centraal/  301");
    expect(redirects([UT])).toContain("/station/ut  /station/utrecht-centraal/  301");
  });
});
