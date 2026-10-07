// Station details in a dialog: step-free status with source and date, the journey, lifts, and links to check.

import { reportLink } from "./contact";
import { ACCESS_ICON, accessText, changes, duration, frequency, longDate, platformText, shortDate, trackText, upperFirst, windowText } from "./format";
import { lang, tr } from "./i18n";
import { type Freshness, type StationWarning, freshnessText, journeyWarnings, liftNote, liftPlace, outAt, outText, roleText, statusText, trouble } from "./lifts";
import type { Verdict } from "./results";
import type { LiftStatus, Meta, Station } from "./types";

export interface PanelContext {
  meta: Meta;
  names: Map<string, Station>;
  origin: Station | null;
  dayIso: string;
  lifts: LiftStatus | null;
  fresh: Freshness;
  stroller: boolean;
  onStartHere: (code: string) => void;
}

function warningBox(warnings: StationWarning[]): HTMLElement {
  const box = el("div", undefined, "warn-box");
  box.setAttribute("role", "note");
  box.append(el("strong", tr({ nl: "⚠ Let op: liften op je route", en: "⚠ Note: lifts on your route" })));
  const ul = el("ul");
  for (const w of warnings) {
    for (const o of w.out) ul.append(el("li", `${w.station.name} (${roleText(w.role)}): ${outText(o)}`));
  }
  const advice = tr({
    nl: "Misschien heb je die lift nodig voor je perron. Controleer je route, of vraag hulp op het station.",
    en: "You may need that lift to reach your platform. Check your route, or ask for help at the station.",
  });
  box.append(ul, el("p", advice, "small"));
  return box;
}

function el<K extends keyof HTMLElementTagNameMap>(tag: K, text?: string, cls?: string): HTMLElementTagNameMap[K] {
  const e = document.createElement(tag);
  if (text !== undefined) e.textContent = text;
  if (cls) e.className = cls;
  return e;
}

function statusBlock(st: Station): HTMLElement {
  const box = el("section");
  box.setAttribute("aria-labelledby", "panel-access");
  box.append(el("h3", tr({ nl: "Toegankelijkheid", en: "Accessibility" }), "panel-h"));
  box.lastElementChild!.id = "panel-access";
  const badge = el("p", undefined, `badge access-${st.status}`);
  badge.append(el("span", ACCESS_ICON[st.status], "badge-icon"), document.createTextNode(accessText(st.status)));
  box.append(badge);

  const corrected = st.source !== "EPIAP";
  const date = st.source_date ? `, ${shortDate(st.source_date)}` : "";
  const source = tr({
    nl: `Bron: open data van DOVA en ProRail${corrected ? ", met een handmatige correctie" : ""}${date}.`,
    en: `Source: open data from DOVA and ProRail${corrected ? ", with a manual correction" : ""}${date}.`,
  });
  box.append(el("p", source, "small"));
  if (st.verified) box.append(el("p", tr({ nl: "✓ Ter plekke gecontroleerd.", en: "✓ Checked on site." }), "small"));

  const tracks = Object.entries(st.tracks);
  if (tracks.length) {
    const details = el("details");
    details.append(el("summary", tr({ nl: "Per spoor", en: "Per platform" })));
    const ul = el("ul", undefined, "tracks");
    for (const [track, value] of tracks.sort((a, b) => a[0].localeCompare(b[0], "nl", { numeric: true }))) {
      ul.append(el("li", `${upperFirst(platformText([track]))}: ${trackText(value)}`));
    }
    details.append(ul);
    box.append(details);
  }
  return box;
}

function journeyBlock(v: Verdict, ctx: PanelContext): HTMLElement | null {
  if (!ctx.origin || v.category === "origin") return null;
  const box = el("section");
  box.append(el("h3", tr({ nl: `Vanaf ${ctx.origin.name}`, en: `From ${ctx.origin.name}` }), "panel-h"));
  const [start, end] = ctx.meta.window;
  const window = windowText(start, end);
  if (v.entry) {
    const [median, fastest, perHour, n, via] = v.entry;
    const warnings = journeyWarnings(v.entry, ctx.origin, v.station, ctx.names, ctx.lifts, ctx.fresh);
    const warnAt = new Map(warnings.map((w) => [w.station.code, w]));
    const dl = el("dl", undefined, "facts");
    const add = (term: string, value: string) => dl.append(el("dt", term), el("dd", value));
    const usually = tr({ nl: `meestal ${duration(median)} (snelste ${duration(fastest)})`, en: `usually ${duration(median)} (fastest ${duration(fastest)})` });
    add(tr({ nl: "Reistijd", en: "Travel time" }), median === fastest ? duration(median) : usually);
    add(tr({ nl: "Overstappen", en: "Changes" }), changes(n));
    if (via) {
      const names = via.split("|").map((c) => {
        const s = ctx.names.get(c);
        if (!s) return c;
        const w = warnAt.get(c); // never plain "drempelvrij" while a lift there is out
        return `${s.name} (${accessText(s.status).toLowerCase()}${w ? `, ${liftNote(w)}` : ""})`;
      });
      add(tr({ nl: "Overstappen in", en: "Change at" }), names.join(", "));
    }
    add(tr({ nl: "Hoe vaak", en: "How often" }), frequency(perHour, (end - start) / 60, window));
    box.append(dl);
    if (warnings.length) box.append(warningBox(warnings));
    const basis = tr({
      nl: `Gebaseerd op de dienstregeling van ${longDate(ctx.dayIso)}, vertrek tussen ${window}.`,
      en: `Based on the timetable for ${longDate(ctx.dayIso)}, departing between ${window}.`,
    });
    box.append(el("p", `${basis} ${freshnessText(ctx.lifts, ctx.fresh)}`, "small"));
  } else {
    const why =
      v.category === "not-step-free"
        ? tr({ nl: "Dit station is niet drempelvrij, dus met de kinderwagen raden we het niet aan.", en: "This station is not step-free, so we don't recommend it with a pram." })
        : v.category === "unknown-access"
          ? tr({
              nl: "Van dit station weten we niet of het drempelvrij is. Zolang dat onbekend is, tellen we het niet mee.",
              en: "We don't know whether this station is step-free. As long as that's unknown, we don't count it.",
            })
          : tr({
              nl: "Niet bereikbaar binnen je keuzes. Probeer meer overstappen, een langere reistijd, of ook intercity's.",
              en: "Not reachable within your choices. Try more changes, a longer travel time, or intercity trains too.",
            });
    box.append(el("p", why));
  }
  return box;
}

function liftBlock(st: Station, ctx: PanelContext): HTMLElement | null {
  if (!st.lifts.length) return null;
  const box = el("section");
  box.append(el("h3", tr({ nl: "Liften", en: "Lifts" }), "panel-h"));
  const out = new Map(outAt(st, ctx.lifts, ctx.fresh).map((o) => [o.lift.id, o]));
  const back = [...out.values()].filter((o) => trouble(o) === "back").length;
  const broken = out.size - back;
  const ul = el("ul", undefined, "lifts");
  for (const lift of st.lifts) {
    const li = el("li", `${lift.code ?? lift.id} (${liftPlace(lift)})`);
    const o = out.get(lift.id);
    if (o) {
      // An outage shows no "since": the feed restarts that date with every nightly full status, so it's often wrong.
      // A lift that is back does: that time is the listener's own.
      const what = ` ⚠ ${upperFirst(statusText(o))}`;
      const until = o.until ? tr({ nl: `, naar verwachting tot ${shortDate(o.until)}`, en: `, expected until ${shortDate(o.until)}` }) : "";
      li.append(el("strong", what + until, "warn"));
    }
    ul.append(li);
  }
  // a short list is shown as is; a long one folds away unless a lift is out of order or has just come back
  if (st.lifts.length <= 4) {
    box.append(ul);
  } else {
    const details = el("details");
    details.open = out.size > 0;
    const counts = [
      broken ? tr({ nl: `${broken} met een storing`, en: `${broken} out of order` }) : "",
      back ? tr({ nl: `${back} net weer in gebruik`, en: `${back} just back in service` }) : "",
    ].filter(Boolean);
    details.append(el("summary", [tr({ nl: `${st.lifts.length} liften`, en: `${st.lifts.length} lifts` }), ...counts].join(", ")), ul);
    box.append(details);
  }
  box.append(el("p", freshnessText(ctx.lifts, ctx.fresh), "small"));
  return box;
}

/** NS's pages for checking, in the page's language (the English journey planner takes the same parameters). */
const NS = {
  planner: { nl: "https://www.ns.nl/reisplanner/", en: "https://www.ns.nl/en/journeyplanner/" },
  station: { nl: "https://www.ns.nl/stationsinformatie/", en: "https://www.ns.nl/en/station-information/" },
};

function links(st: Station, ctx: PanelContext): HTMLElement {
  const box = el("section");
  box.append(el("h3", tr({ nl: "Controleer voor vertrek", en: "Check before you go" }), "panel-h"));
  const ul = el("ul", undefined, "links");
  const a = (href: string, text: string) => {
    const link = el("a", text);
    link.href = href;
    link.target = "_blank";
    link.rel = "noopener";
    const li = el("li");
    li.append(link);
    ul.append(li);
  };
  if (ctx.origin && ctx.origin.code !== st.code) {
    const q = new URLSearchParams({ vertrek: ctx.origin.code, vertrektype: "treinstation", aankomst: st.code, aankomsttype: "treinstation", type: "vertrek" });
    const journey = `${ctx.origin.name} – ${st.name}`;
    a(`${NS.planner[lang]}#/?${q}`, tr({ nl: `Reis ${journey} in de NS-reisplanner`, en: `${journey} in the NS Journey Planner` }));
  }
  a(`${NS.station[lang]}${st.code.toLowerCase()}`, tr({ nl: `Stationsinformatie ${st.name} (NS)`, en: `Station information for ${st.name} (NS)` }));
  box.append(ul);
  const report = el("p", undefined, "small");
  report.append(
    reportLink(
      tr({ nl: "Klopt er iets niet bij dit station? Meld het", en: "Something wrong at this station? Report it" }),
      tr({ nl: `Trapvrij: fout bij station ${st.name} (${st.code})`, en: `Trapvrij: error at station ${st.name} (${st.code})` }),
    ),
  );
  box.append(report);
  return box;
}

export function renderPanel(body: HTMLElement, title: HTMLElement, v: Verdict, ctx: PanelContext): void {
  const st = v.station;
  title.textContent = st.name;
  const parts: HTMLElement[] = [statusBlock(st)];
  const j = journeyBlock(v, ctx);
  if (j) parts.push(j);
  const lifts = liftBlock(st, ctx);
  if (lifts) parts.push(lifts);
  parts.push(links(st, ctx));
  if (v.category !== "origin") {
    const start = el("button", tr({ nl: `Vertrek vanaf ${st.name}`, en: `Start from ${st.name}` }), "primary");
    start.type = "button";
    start.addEventListener("click", () => ctx.onStartHere(st.code));
    parts.push(start);
  }
  body.replaceChildren(...parts);
}
