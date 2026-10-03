// Pre-rendered pages for search engines and visitors without JavaScript (PLAN, Phase 3):
//   /station/<slug>/   one page per station: own title and description, step-free status, lifts,
//                      and what you reach within 30 and 60 minutes; the map loads on top
//   /station/          all stations, as plain links
//   /404.html          for addresses that don't exist (otherwise Pages serves the home page with 200)
//   /sitemap.xml and /_redirects (old /station/<CODE> links)
// Plain code from the data, no AI (principle 2). Run after `vite build` and copy-data:
//   node scripts/pages.ts

import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

import { ACCESS_TEXT, duration, pageTitle, shortDate } from "../src/format.ts";
import type { Entry, Meta, OriginDoc, Station } from "../src/types.ts";
import { siteDir } from "../vite.config.ts";

export const SITE = "https://trapvrij.nl";

export function esc(text: string): string {
  return text.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);
}

const link = (s: Station) => `<a href="/station/${s.slug}/">${esc(s.name)}</a>`;

/** "A, B en C" */
function and(parts: string[]): string {
  return parts.length <= 1 ? parts.join("") : `${parts.slice(0, -1).join(", ")} en ${parts[parts.length - 1]}`;
}

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

const STATUS_SENTENCE: Record<Station["status"], (name: string) => string> = {
  yes: (n) => `${n} is drempelvrij: je komt zonder trappen op elk perron.`,
  partial: (n) => `${n} is deels drempelvrij: niet elk perron is zonder trappen te bereiken.`,
  no: (n) => `${n} is niet drempelvrij. Met de kinderwagen kun je hier niet zonder trappen instappen.`,
  unknown: (n) => `Van ${n} weten we niet of het drempelvrij is. Daarom rekenen we er met de kinderwagen niet mee.`,
};

export interface PageText {
  title: string;
  description: string;
  intro: string; // inner HTML of <section id="intro">
}

export function stationText(st: Station, doc: OriginDoc | null, byCode: Map<string, Station>): PageText {
  const pram = st.status === "yes" || st.status === "partial";
  const within30 = reachable(doc, byCode, pram ? "stroller" : "any", 30);
  const within60 = reachable(doc, byCode, pram ? "stroller" : "any", 60);
  const name = esc(st.name);
  const parts: string[] = [`<h1 id="intro-title">Met de kinderwagen vanaf ${name}</h1>`];

  let status = STATUS_SENTENCE[st.status](name);
  if (st.status === "partial") {
    const tracks = (value: string) => Object.entries(st.tracks).filter(([, v]) => v === value).map(([t]) => t);
    const yes = tracks("yes");
    if (yes.length) status += ` Zonder trappen: spoor ${and(yes)}.`;
  }
  const source = `Bron: open data van DOVA en ProRail${st.source_date ? `, ${shortDate(st.source_date)}` : ""}${st.verified ? "; ter plekke gecontroleerd" : ""}.`;
  parts.push(`<p>${status} <span class="small">${source}</span></p>`);
  if (st.lifts.length) {
    const n = st.lifts.length;
    parts.push(`<p>Het station heeft ${n === 1 ? "één lift" : `${n} liften`}. Of er nu een lift buiten gebruik is, zie je bij het station op de kaart hieronder.</p>`);
  }

  const how = pram ? "Met de kinderwagen, sprinters en stoptreinen en hoogstens één overstap" : "Zonder kinderwagen, met sprinters en stoptreinen en hoogstens één overstap";
  const quick = within30.slice(0, 6).map((r) => `${link(r.station)} (${duration(r.entry[0])})`);
  const n30 = within30.length;
  const n60 = within60.length;
  let reach = n30
    ? `${how} bereik je doordeweeks ${n30 === 1 ? "één station" : `${n30} stations`} binnen 30 minuten, zoals ${and(quick)}.`
    : `${how} bereik je doordeweeks binnen 30 minuten geen ander station.`;
  const further = within60
    .filter((r) => r.entry[0] > 30)
    .sort((a, b) => b.station.trains - a.station.trains) // the best-known places...
    .slice(0, 5)
    .sort((a, b) => a.entry[0] - b.entry[0]) // ...nearest first
    .map((r) => `${link(r.station)} (${duration(r.entry[0])})`);
  if (further.length) reach += ` Binnen een uur zijn het er ${n60}, onder andere ${and(further)}.`;
  else if (!n30) reach += " Binnen een uur ook niet.";
  parts.push(`<p>${reach}</p>`);
  parts.push(`<p>Hieronder staan alle bestemmingen op de kaart en in de lijst. Je kunt ook kiezen voor intercity's, meer overstappen of zaterdag.</p>`);

  const description = pram
    ? `${st.name} met de kinderwagen: ${n30} stations zonder trappen binnen 30 minuten, ${n60} binnen een uur. Met reistijden, overstappen en liften.`
    : `${st.name}: ${ACCESS_TEXT[st.status].toLowerCase()}. Zie waar je vanaf hier met de trein heen kunt, met reistijden en overstappen.`;
  return { title: pageTitle(st.name), description, intro: parts.join("\n") };
}

/** Fill the built index.html in for one station. */
export function stationPage(template: string, st: Station, text: PageText): string {
  const url = `${SITE}/station/${st.slug}/`;
  return replaceHead(template, text.title, text.description, url)
    .replace("<h1>Trapvrij</h1>", '<p class="brand"><a href="/">Trapvrij</a></p>')
    .replace(
      '<section id="intro" class="intro" hidden></section>',
      `<section id="intro" class="intro" data-station="${esc(st.code)}" aria-labelledby="intro-title">\n${text.intro}\n</section>`,
    )
    .replace('<input id="origin" type="text"', `<input id="origin" type="text" value="${esc(st.name)}"`);
}

function replaceHead(html: string, title: string, description: string, url: string): string {
  const swap = (from: RegExp, to: string) => {
    if (!from.test(html)) throw new Error(`template has no ${from}`);
    html = html.replace(from, to);
  };
  swap(/<title>[^<]*<\/title>/, `<title>${esc(title)}</title>`);
  swap(/<meta name="description" content="[^"]*" \/>/, `<meta name="description" content="${esc(description)}" />`);
  swap(/<link rel="canonical" href="[^"]*" \/>/, `<link rel="canonical" href="${url}" />`);
  swap(/<meta property="og:title" content="[^"]*" \/>/, `<meta property="og:title" content="${esc(title)}" />`);
  swap(/<meta property="og:description" content="[^"]*" \/>/, `<meta property="og:description" content="${esc(description)}" />`);
  swap(/<meta property="og:url" content="[^"]*" \/>/, `<meta property="og:url" content="${url}" />`);
  return html;
}

/** A page without the app (styled like the rest): `url` null means a page not to index. */
function staticPage(template: string, o: { title: string; description: string; url: string | null; body: string }): string {
  let head = replaceHead(template.slice(0, template.indexOf("</head>")), o.title, o.description, o.url ?? `${SITE}/`)
    .replace(/\s*<script type="module"[^>]*><\/script>/, "")
    .replace(/\s*<link rel="modulepreload"[^>]*>/g, "");
  if (!o.url) head = head.replace(/\s*<link rel="canonical"[^>]*>/, "") + '\n    <meta name="robots" content="noindex" />';
  return `${head}
  </head>
  <body>
    <header class="top">
      <div>
        <p class="brand"><a href="/">Trapvrij</a></p>
        <p class="tagline">Waar kun je met de trein heen zonder trappen?</p>
      </div>
    </header>
    <main class="page">
${o.body}
    </main>
    <footer class="foot"><p>Geen cookies. We tellen bezoeken anoniem met Cloudflare Web Analytics. Niet verbonden aan NS of ProRail. <a href="/station/">Alle stations</a></p></footer>
  </body>
</html>
`;
}

/** /station/: every station as a plain link. */
export function stationsIndex(template: string, stations: Station[]): string {
  const items = [...stations]
    .sort((a, b) => a.name.localeCompare(b.name, "nl"))
    .map((s) => `<li>${link(s)} <span class="small">${esc(ACCESS_TEXT[s.status])}</span></li>`)
    .join("\n");
  return staticPage(template, {
    title: "Alle stations – Trapvrij",
    description: "Alle treinstations in Nederland: welke zijn drempelvrij, en waar kun je vanaf elk station heen met de kinderwagen?",
    url: `${SITE}/station/`,
    body: `      <h1>Alle stations</h1>
      <p>Kies een station om te zien of het drempelvrij is en waar je er met de kinderwagen naartoe kunt.</p>
      <ul class="station-index">
${items}
      </ul>`,
  });
}

/** /404.html: Cloudflare Pages serves it, with status 404, for every address that doesn't exist. */
export function notFound(template: string): string {
  return staticPage(template, {
    title: "Pagina niet gevonden – Trapvrij",
    description: "Deze pagina bestaat niet.",
    url: null,
    body: `      <h1>Pagina niet gevonden</h1>
      <p>Deze pagina bestaat niet (meer). Kies een vertrekstation op <a href="/">de kaart</a> of in de <a href="/station/">lijst met alle stations</a>.</p>`,
  });
}

export function sitemap(stations: Station[], date: string): string {
  const urls = ["/", "/station/", ...stations.map((s) => `/station/${s.slug}/`)];
  const rows = urls.map((u) => `  <url><loc>${SITE}${u}</loc><lastmod>${date}</lastmod></url>`).join("\n");
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
  const template = fs.readFileSync(path.join(site, "index.html"), "utf-8");
  const meta = read<Meta>("meta.json");
  const stations = read<Station[]>("stations.json");
  const byCode = new Map(stations.map((s) => [s.code, s]));
  for (const st of stations) {
    const file = path.join(site, "data", "origins", `${st.code}.json`);
    const doc = fs.existsSync(file) ? (JSON.parse(fs.readFileSync(file, "utf-8")) as OriginDoc) : null;
    const dir = path.join(site, "station", st.slug);
    fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(path.join(dir, "index.html"), stationPage(template, st, stationText(st, doc, byCode)));
  }
  fs.writeFileSync(path.join(site, "station", "index.html"), stationsIndex(template, stations));
  fs.writeFileSync(path.join(site, "404.html"), notFound(template));
  fs.writeFileSync(path.join(site, "sitemap.xml"), sitemap(stations, meta.built.slice(0, 10)));
  fs.writeFileSync(path.join(site, "_redirects"), redirects(stations));
  console.log(`wrote ${stations.length} station pages, /station/, sitemap.xml and _redirects to ${site}`);
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) main();
