// Pre-rendered pages for search engines and visitors without JavaScript (PLAN, Phase 3),
// in Dutch and, under /en/, in English (DECISIONS 2026-10-07):
//   /station/<slug>/   one page per station: own title and description, step-free status, lifts,
//                      and what you reach within 30 and 60 minutes; the map loads on top
//   /station/          all stations, as plain links
//   /404.html          for addresses that don't exist (otherwise Pages serves the home page with 200);
//                      Pages serves the nearest one, so /en/404.html covers /en/…
//   /sitemap.xml (both languages) and /_redirects (old /station/<CODE> links)
// Plain code from the data, no AI (principle 2). Run after `vite build` and copy-data:
//   node scripts/pages.ts

import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

import { accessText, duration, listText, pageTitle, shortDate } from "../src/format.ts";
import { type Lang, PREFIX, lang, other, tr, useLang } from "../src/i18n.ts";
import type { Entry, Meta, OriginDoc, Station } from "../src/types.ts";
import { siteDir } from "../vite.config.ts";

export const SITE = "https://trapvrij.nl";
export const LANGS: Lang[] = ["nl", "en"];

export function esc(text: string): string {
  return text.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);
}

/** A page in the current language: "/station/x/" -> "/en/station/x/". */
const local = (page: string) => PREFIX[lang] + page;

const link = (s: Station) => `<a href="${local(`/station/${s.slug}/`)}">${esc(s.name)}</a>`;

export interface Reach {
  station: Station;
  entry: Entry;
}

/** The site's default view: weekday, sprinters and stopping trains, at most 1 change; quickest first. */
export function reachable(doc: OriginDoc | null, byCode: Map<string, Station>, profile: "stroller" | "any", maxMinutes: number): Reach[] {
  const dests = doc?.results.weekday?.[profile]?.sprinter ?? {};
  const out: Reach[] = [];
  for (const [code, entries] of Object.entries(dests)) {
    const entry = entries.length ? entries[Math.min(1, entries.length - 1)] : null;
    const station = byCode.get(code);
    if (station && entry && entry[0] <= maxMinutes) out.push({ station, entry });
  }
  return out.sort((a, b) => a.entry[0] - b.entry[0] || a.station.name.localeCompare(b.station.name, "nl"));
}

const STATUS_SENTENCE: Record<Station["status"], (name: string) => Record<Lang, string>> = {
  yes: (n) => ({
    nl: `${n} is drempelvrij: je komt zonder trappen op elk perron.`,
    en: `${n} is step-free: you can reach every platform without stairs.`,
  }),
  partial: (n) => ({
    nl: `${n} is deels drempelvrij: niet elk perron is zonder trappen te bereiken.`,
    en: `${n} is partly step-free: not every platform can be reached without stairs.`,
  }),
  no: (n) => ({
    nl: `${n} is niet drempelvrij. Met de kinderwagen kun je hier niet zonder trappen instappen.`,
    en: `${n} is not step-free. With a pram, you can't board here without stairs.`,
  }),
  unknown: (n) => ({
    nl: `Van ${n} weten we niet of het drempelvrij is. Daarom rekenen we er met de kinderwagen niet mee.`,
    en: `We don't know whether ${n} is step-free, so we don't count it for travelling with a pram.`,
  }),
};

export interface PageText {
  title: string;
  description: string;
  intro: string; // inner HTML of <section id="intro">
}

/** A station page's own text, in the current language. */
export function stationText(st: Station, doc: OriginDoc | null, byCode: Map<string, Station>): PageText {
  const pram = st.status === "yes" || st.status === "partial";
  const within30 = reachable(doc, byCode, pram ? "stroller" : "any", 30);
  const within60 = reachable(doc, byCode, pram ? "stroller" : "any", 60);
  const name = esc(st.name);
  const parts: string[] = [`<h1 id="intro-title">${tr({ nl: `Met de kinderwagen vanaf ${name}`, en: `With a pram from ${name}` })}</h1>`];

  let status = tr(STATUS_SENTENCE[st.status](name));
  if (st.status === "partial") {
    const yes = Object.entries(st.tracks).filter(([, v]) => v === "yes").map(([t]) => t);
    if (yes.length) status += tr({ nl: ` Zonder trappen: spoor ${listText(yes)}.`, en: ` Without stairs: platform${yes.length > 1 ? "s" : ""} ${listText(yes)}.` });
  }
  const date = st.source_date ? `, ${shortDate(st.source_date)}` : "";
  const source = tr({
    nl: `Bron: open data van DOVA en ProRail${date}${st.verified ? "; ter plekke gecontroleerd" : ""}.`,
    en: `Source: open data from DOVA and ProRail${date}${st.verified ? "; checked on site" : ""}.`,
  });
  parts.push(`<p>${status} <span class="small">${source}</span></p>`);
  if (st.lifts.length) {
    const n = st.lifts.length;
    parts.push(
      `<p>${tr({
        nl: `Het station heeft ${n === 1 ? "één lift" : `${n} liften`}. Of er nu een lift buiten gebruik is, zie je bij het station op de kaart hieronder.`,
        en: `The station has ${n === 1 ? "one lift" : `${n} lifts`}. To see whether a lift is out of order right now, open the station on the map below.`,
      })}</p>`,
    );
  }

  const quick = within30.slice(0, 6).map((r) => `${link(r.station)} (${duration(r.entry[0])})`);
  const n30 = within30.length;
  const n60 = within60.length;
  const how = pram
    ? tr({ nl: "Met de kinderwagen, sprinters en stoptreinen en hoogstens één overstap", en: "With a pram, using sprinters and stopping trains with at most one change" })
    : tr({ nl: "Zonder kinderwagen, met sprinters en stoptreinen en hoogstens één overstap", en: "Without a pram, using sprinters and stopping trains with at most one change" });
  let reach = n30
    ? tr({
        nl: `${how} bereik je doordeweeks ${n30 === 1 ? "één station" : `${n30} stations`} binnen 30 minuten, zoals ${listText(quick)}.`,
        en: `${how}, you can reach ${n30 === 1 ? "one station" : `${n30} stations`} within 30 minutes on a weekday, such as ${listText(quick)}.`,
      })
    : tr({
        nl: `${how} bereik je doordeweeks binnen 30 minuten geen ander station.`,
        en: `${how}, you can't reach any other station within 30 minutes on a weekday.`,
      });
  const further = within60
    .filter((r) => r.entry[0] > 30)
    .sort((a, b) => b.station.trains - a.station.trains) // the best-known places...
    .slice(0, 5)
    .sort((a, b) => a.entry[0] - b.entry[0]) // ...nearest first
    .map((r) => `${link(r.station)} (${duration(r.entry[0])})`);
  if (further.length) reach += tr({ nl: ` Binnen een uur zijn het er ${n60}, onder andere ${listText(further)}.`, en: ` Within an hour it's ${n60}, including ${listText(further)}.` });
  else if (!n30) reach += tr({ nl: " Binnen een uur ook niet.", en: " Nor within an hour." });
  parts.push(`<p>${reach}</p>`);
  parts.push(
    `<p>${tr({
      nl: "Hieronder staan alle bestemmingen op de kaart en in de lijst. Je kunt ook kiezen voor intercity's, meer overstappen of zaterdag.",
      en: "Below, you'll find every destination on the map and in the list. You can also choose intercity trains, more changes or Saturday.",
    })}</p>`,
  );

  const stations = (n: number) => tr({ nl: n === 1 ? "1 station" : `${n} stations`, en: n === 1 ? "1 station" : `${n} stations` });
  const description = pram
    ? tr({
        nl: `${st.name} met de kinderwagen: ${stations(n30)} zonder trappen binnen 30 minuten, ${n60} binnen een uur. Met reistijden, overstappen en liften.`,
        en: `${st.name} with a pram: ${stations(n30)} without stairs within 30 minutes, ${n60} within an hour. With travel times, changes and lifts.`,
      })
    : tr({
        nl: `${st.name}: ${accessText(st.status).toLowerCase()}. Zie waar je vanaf hier met de trein heen kunt, met reistijden en overstappen.`,
        en: `${st.name}: ${accessText(st.status).toLowerCase()}. See where you can go by train from here, with travel times and changes.`,
      });
  return { title: pageTitle(st.name), description, intro: parts.join("\n") };
}

/** Fill the built index.html (or en/index.html) in for one station. */
export function stationPage(template: string, st: Station, text: PageText): string {
  const page = `/station/${st.slug}/`;
  return replace(replaceHead(template, text.title, text.description, page), [
    ["<h1>Trapvrij</h1>", `<p class="brand"><a href="${local("/")}">Trapvrij</a></p>`],
    [
      '<section id="intro" class="intro" hidden></section>',
      `<section id="intro" class="intro" data-station="${esc(st.code)}" aria-labelledby="intro-title">\n${text.intro}\n</section>`,
    ],
    ['<input id="origin" type="text"', `<input id="origin" type="text" value="${esc(st.name)}"`],
    [/id="lang-switch" href="[^"]*"/, `id="lang-switch" href="${PREFIX[other(lang)]}${page}"`],
  ]);
}

/** Every swap must find its target: a template that changed shape fails loudly instead of losing a part. */
function replace(html: string, swaps: [string | RegExp, string][]): string {
  for (const [from, to] of swaps) {
    if (typeof from === "string" ? !html.includes(from) : !from.test(html)) throw new Error(`template has no ${from}`);
    html = html.replace(from, () => to);
  }
  return html;
}

/** Title, description and addresses for `page` ("/station/x/") in the current language; null: a page not to index. */
function replaceHead(html: string, title: string, description: string, page: string | null): string {
  const url = (l: Lang) => `${SITE}${PREFIX[l]}${page ?? "/"}`;
  html = replace(html, [
    [/<title>[^<]*<\/title>/, `<title>${esc(title)}</title>`],
    [/<meta name="description" content="[^"]*" \/>/, `<meta name="description" content="${esc(description)}" />`],
    [/<meta property="og:title" content="[^"]*" \/>/, `<meta property="og:title" content="${esc(title)}" />`],
    [/<meta property="og:description" content="[^"]*" \/>/, `<meta property="og:description" content="${esc(description)}" />`],
    [/<meta property="og:url" content="[^"]*" \/>/, `<meta property="og:url" content="${url(lang)}" />`],
  ]);
  if (!page) return html.replace(/\s*<link rel="(?:canonical|alternate)"[^>]*>/g, "");
  return replace(html, [
    [/<link rel="canonical" href="[^"]*" \/>/, `<link rel="canonical" href="${url(lang)}" />`],
    ...LANGS.map((l): [RegExp, string] => [new RegExp(`<link rel="alternate" hreflang="${l}" href="[^"]*" />`), `<link rel="alternate" hreflang="${l}" href="${url(l)}" />`]),
    [/<link rel="alternate" hreflang="x-default" href="[^"]*" \/>/, `<link rel="alternate" hreflang="x-default" href="${url("nl")}" />`],
  ]);
}

/** The language switch as in index.html: the current language, and a link to `page` in the other one. */
export function langSwitch(page: string): string {
  const names: Record<Lang, string> = { nl: "Nederlands", en: "English" };
  const o = other(lang);
  const current = `<span aria-current="true">${lang.toUpperCase()}<span class="visually-hidden"> ${names[lang]}</span></span>`;
  const link = `<a id="lang-switch" href="${PREFIX[o]}${page}" hreflang="${o}" lang="${o}">${o.toUpperCase()}<span class="visually-hidden"> ${names[o]}</span></a>`;
  const items = lang === "nl" ? [current, link] : [link, current]; // always NL | EN
  return `<nav class="lang" aria-label="${tr({ nl: "Taal", en: "Language" })}">\n          ${items.join("\n          ")}\n        </nav>`;
}

/** A page without the app (styled like the rest): `page` null means a page not to index. */
function staticPage(template: string, o: { title: string; description: string; page: string | null; body: string }): string {
  let head = replaceHead(template.slice(0, template.indexOf("</head>")), o.title, o.description, o.page)
    .replace(/\s*<script type="module"[^>]*><\/script>/, "")
    .replace(/\s*<link rel="modulepreload"[^>]*>/g, "");
  if (!o.page) head += '\n    <meta name="robots" content="noindex" />';
  const footer = tr({
    nl: "Geen cookies. We tellen bezoeken anoniem met Cloudflare Web Analytics. Niet verbonden aan NS of ProRail.",
    en: "No cookies. We count visits anonymously with Cloudflare Web Analytics. Not affiliated with NS or ProRail.",
  });
  return `${head}
  </head>
  <body>
    <header class="top">
      <div>
        <p class="brand"><a href="${local("/")}">Trapvrij</a></p>
        <p class="tagline">${tr({ nl: "Waar kun je met de trein heen zonder trappen?", en: "Where can you go by train in the Netherlands without stairs?" })}</p>
      </div>
      <div class="top-actions">
        ${langSwitch(o.page ?? "/")}
      </div>
    </header>
    <main class="page">
${o.body}
    </main>
    <footer class="foot"><p>${footer} <a href="${local("/station/")}">${tr({ nl: "Alle stations", en: "All stations" })}</a></p></footer>
  </body>
</html>
`;
}

/** /station/: every station as a plain link. */
export function stationsIndex(template: string, stations: Station[]): string {
  const items = [...stations]
    .sort((a, b) => a.name.localeCompare(b.name, "nl"))
    .map((s) => `<li>${link(s)} <span class="small">${esc(accessText(s.status))}</span></li>`)
    .join("\n");
  const title = tr({ nl: "Alle stations", en: "All stations" });
  return staticPage(template, {
    title: `${title} – Trapvrij`,
    description: tr({
      nl: "Alle treinstations in Nederland: welke zijn drempelvrij, en waar kun je vanaf elk station heen met de kinderwagen?",
      en: "Every railway station in the Netherlands: which are step-free, and where can you go from each one with a pram?",
    }),
    page: "/station/",
    body: `      <h1>${title}</h1>
      <p>${tr({
        nl: "Kies een station om te zien of het drempelvrij is en waar je er met de kinderwagen naartoe kunt.",
        en: "Choose a station to see whether it's step-free and where you can go from there with a pram.",
      })}</p>
      <ul class="station-index">
${items}
      </ul>`,
  });
}

/** /404.html and /en/404.html: Cloudflare Pages serves the nearest one, with status 404, for every address that doesn't exist. */
export function notFound(template: string): string {
  const title = tr({ nl: "Pagina niet gevonden", en: "Page not found" });
  return staticPage(template, {
    title: `${title} – Trapvrij`,
    description: tr({ nl: "Deze pagina bestaat niet.", en: "This page doesn't exist." }),
    page: null,
    body: `      <h1>${title}</h1>
      <p>${tr({
        nl: `Deze pagina bestaat niet (meer). Kies een vertrekstation op <a href="/">de kaart</a> of in de <a href="/station/">lijst met alle stations</a>.`,
        en: `This page doesn't exist (any more). Choose a starting station on <a href="/en/">the map</a> or in the <a href="/en/station/">list of all stations</a>.`,
      })}</p>`,
  });
}

/** Every page, in both languages (each page links to its twin with hreflang). */
export function sitemap(stations: Station[], date: string): string {
  const pages = ["/", "/station/", ...stations.map((s) => `/station/${s.slug}/`)];
  const rows = LANGS.flatMap((l) => pages.map((p) => `  <url><loc>${SITE}${PREFIX[l]}${p}</loc><lastmod>${date}</lastmod></url>`)).join("\n");
  return `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${rows}\n</urlset>\n`;
}

/** /station/UT and /station/ut lead to /station/utrecht-centraal/. */
export function redirects(stations: Station[]): string {
  const slugs = new Set(stations.map((s) => s.slug));
  const lines = ["# Generated by scripts/pages.ts: old /station/<code> links go to the station page."];
  for (const s of stations) {
    for (const code of new Set([s.code, s.code.toLowerCase()])) {
      if (!slugs.has(code)) lines.push(`/station/${code}  /station/${s.slug}/  301`);
    }
  }
  return lines.join("\n") + "\n";
}

function main(): void {
  const site = siteDir();
  const read = <T>(rel: string): T => JSON.parse(fs.readFileSync(path.join(site, "data", rel), "utf-8")) as T;
  const write = (file: string, html: string) => {
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.writeFileSync(file, html);
  };
  const root = (l: Lang) => path.join(site, PREFIX[l]); // site/ and site/en/
  const templates = Object.fromEntries(LANGS.map((l) => [l, fs.readFileSync(path.join(root(l), "index.html"), "utf-8")])) as Record<Lang, string>;
  const meta = read<Meta>("meta.json");
  const stations = read<Station[]>("stations.json");
  const byCode = new Map(stations.map((s) => [s.code, s]));
  for (const st of stations) {
    const file = path.join(site, "data", "origins", `${st.code}.json`);
    const doc = fs.existsSync(file) ? (JSON.parse(fs.readFileSync(file, "utf-8")) as OriginDoc) : null;
    for (const l of LANGS) {
      useLang(l);
      write(path.join(root(l), "station", st.slug, "index.html"), stationPage(templates[l], st, stationText(st, doc, byCode)));
    }
  }
  for (const l of LANGS) {
    useLang(l);
    write(path.join(root(l), "station", "index.html"), stationsIndex(templates[l], stations));
    write(path.join(root(l), "404.html"), notFound(templates[l]));
  }
  useLang("nl");
  write(path.join(site, "sitemap.xml"), sitemap(stations, meta.built.slice(0, 10)));
  write(path.join(site, "_redirects"), redirects(stations));
  console.log(`wrote ${stations.length} station pages in Dutch and English, /station/, 404 pages, sitemap.xml and _redirects to ${site}`);
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) main();
