import { describe, expect, it } from "vitest";

import type { OriginDoc, Station } from "../src/types";
import { esc, reachable, redirects, sitemap, stationPage, stationText } from "./pages";

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
<meta property="og:title" content="home" />
<meta property="og:description" content="home" />
<meta property="og:url" content="https://trapvrij.nl/" />
</head><body><h1>Trapvrij</h1>
<section id="intro" class="intro" hidden></section>
<input id="origin" type="text" autocomplete="off" /></body></html>`;

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

  it("escapes names", () => {
    expect(esc("'s-Hertogenbosch <x>")).toBe("&#39;s-Hertogenbosch &lt;x&gt;");
  });

  it("lists every page in the sitemap and redirects old code links", () => {
    expect(sitemap([UT], "2026-10-02")).toContain("<loc>https://trapvrij.nl/station/utrecht-centraal/</loc><lastmod>2026-10-02</lastmod>");
    expect(redirects([UT])).toContain("/station/UT  /station/utrecht-centraal/  301");
    expect(redirects([UT])).toContain("/station/ut  /station/utrecht-centraal/  301");
  });
});
