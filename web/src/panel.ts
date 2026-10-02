// Station details in a dialog: step-free status with source and date, the journey, lifts, and links to check.

import { reportLink } from "./contact";
import { ACCESS_ICON, ACCESS_TEXT, TRACK_TEXT, changes, clock, duration, frequency, longDate, shortDate } from "./format";
import { type Freshness, type StationWarning, freshnessText, journeyWarnings, outAt, outText } from "./lifts";
import type { Verdict } from "./results";
import type { LiftStatus, Meta, Station } from "./types";

export interface PanelContext {
  meta: Meta;
  names: Map<string, Station>;
  origin: Station | null;
  dayLabel: string; // "doordeweeks" / "op zaterdag"
  dayIso: string;
  lifts: LiftStatus | null;
  fresh: Freshness;
  stroller: boolean;
  onStartHere: (code: string) => void;
}

const ROLE_TEXT = { vertrek: "vertrek", overstap: "overstap", aankomst: "aankomst" };

/** "⚠ lift buiten gebruik" or "⚠ liftstatus onbekend", for a station on the journey. */
export function liftNote(w: StationWarning): string {
  return w.out.some((o) => o.status !== "unknown") ? "⚠ lift buiten gebruik" : "⚠ liftstatus onbekend";
}

function warningBox(warnings: StationWarning[]): HTMLElement {
  const box = el("div", undefined, "warn-box");
  box.setAttribute("role", "note");
  box.append(el("strong", "⚠ Let op: liften op je route"));
  const ul = el("ul");
  for (const w of warnings) {
    for (const o of w.out) ul.append(el("li", `${w.station.name} (${ROLE_TEXT[w.role]}): ${outText(o)}`));
  }
  box.append(ul, el("p", "Misschien heb je die lift nodig voor je perron. Controleer je route, of vraag hulp op het station.", "small"));
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
  box.append(el("h3", "Toegankelijkheid", "panel-h"));
  box.lastElementChild!.id = "panel-access";
  const badge = el("p", undefined, `badge access-${st.status}`);
  badge.append(el("span", ACCESS_ICON[st.status], "badge-icon"), document.createTextNode(ACCESS_TEXT[st.status]));
  box.append(badge);

  const source = st.source === "EPIAP" ? "open data van DOVA en ProRail" : "open data van DOVA en ProRail, met een handmatige correctie";
  const src = el("p", `Bron: ${source}${st.source_date ? `, ${shortDate(st.source_date)}` : ""}.`, "small");
  box.append(src);
  if (st.verified) box.append(el("p", "✓ Ter plekke gecontroleerd.", "small"));

  const tracks = Object.entries(st.tracks);
  if (tracks.length) {
    const details = el("details");
    details.append(el("summary", "Per spoor"));
    const ul = el("ul", undefined, "tracks");
    for (const [track, value] of tracks.sort((a, b) => a[0].localeCompare(b[0], "nl", { numeric: true }))) {
      ul.append(el("li", `Spoor ${track}: ${TRACK_TEXT[value]}`));
    }
    details.append(ul);
    box.append(details);
  }
  return box;
}

function journeyBlock(v: Verdict, ctx: PanelContext): HTMLElement | null {
  if (!ctx.origin || v.category === "origin") return null;
  const box = el("section");
  box.append(el("h3", `Vanaf ${ctx.origin.name}`, "panel-h"));
  const [start, end] = ctx.meta.window;
  const windowText = `${clock(start)} en ${clock(end)}`;
  if (v.entry) {
    const [median, fastest, perHour, n, via] = v.entry;
    const warnings = journeyWarnings(v.entry, ctx.origin, v.station, ctx.names, ctx.lifts, ctx.fresh);
    const warnAt = new Map(warnings.map((w) => [w.station.code, w]));
    const dl = el("dl", undefined, "facts");
    const add = (term: string, value: string) => dl.append(el("dt", term), el("dd", value));
    add("Reistijd", median === fastest ? duration(median) : `meestal ${duration(median)} (snelste ${duration(fastest)})`);
    add("Overstappen", changes(n));
    if (via) {
      const names = via.split("|").map((c) => {
        const s = ctx.names.get(c);
        if (!s) return c;
        const w = warnAt.get(c); // never plain "drempelvrij" while a lift there is out
        return `${s.name} (${ACCESS_TEXT[s.status].toLowerCase()}${w ? `, ${liftNote(w)}` : ""})`;
      });
      add("Overstappen in", names.join(", "));
    }
    add("Hoe vaak", frequency(perHour, (end - start) / 60, windowText));
    box.append(dl);
    if (warnings.length) box.append(warningBox(warnings));
    box.append(el("p", `Gebaseerd op de dienstregeling van ${longDate(ctx.dayIso)}, vertrek tussen ${windowText}. ${freshnessText(ctx.lifts, ctx.fresh)}`, "small"));
  } else {
    const why =
      v.category === "not-step-free"
        ? "Dit station is niet drempelvrij, dus met de kinderwagen raden we het niet aan."
        : v.category === "unknown-access"
          ? "Van dit station weten we niet of het drempelvrij is. Zolang dat onbekend is, tellen we het niet mee."
          : "Niet bereikbaar binnen je keuzes. Probeer meer overstappen, een langere reistijd, of ook intercity's.";
    box.append(el("p", why));
  }
  return box;
}

function liftBlock(st: Station, ctx: PanelContext): HTMLElement | null {
  if (!st.lifts.length) return null;
  const box = el("section");
  box.append(el("h3", "Liften", "panel-h"));
  const out = new Map(outAt(st, ctx.lifts, ctx.fresh).map((o) => [o.lift.id, o]));
  const broken = out.size;
  const ul = el("ul", undefined, "lifts");
  for (const lift of st.lifts) {
    const where = lift.tracks.length ? `spoor ${lift.tracks.join("/")}` : "hal of ingang";
    const li = el("li", `${lift.code ?? lift.id} (${where})`);
    const o = out.get(lift.id);
    if (o) {
      // no "since": the feed restarts that date with every nightly full status, so it's often wrong
      const what = o.status === "unknown" ? " ⚠ Status onbekend" : " ⚠ Buiten gebruik";
      li.append(el("strong", what + (o.until ? `, naar verwachting tot ${shortDate(o.until)}` : ""), "warn"));
    }
    ul.append(li);
  }
  // a short list is shown as is; a long one folds away unless a lift is out of order
  if (st.lifts.length <= 4) {
    box.append(ul);
  } else {
    const details = el("details");
    details.open = broken > 0;
    details.append(el("summary", `${st.lifts.length} liften${broken ? `, ${broken} met een storing` : ""}`), ul);
    box.append(details);
  }
  box.append(el("p", freshnessText(ctx.lifts, ctx.fresh), "small"));
  return box;
}

function links(st: Station, ctx: PanelContext): HTMLElement {
  const box = el("section");
  box.append(el("h3", "Controleer voor vertrek", "panel-h"));
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
    a(`https://www.ns.nl/reisplanner/#/?${q}`, `Reis ${ctx.origin.name} – ${st.name} in de NS-reisplanner`);
  }
  a(`https://www.ns.nl/stationsinformatie/${st.code.toLowerCase()}`, `Stationsinformatie ${st.name} (NS)`);
  box.append(ul);
  const report = el("p", undefined, "small");
  report.append(reportLink("Klopt er iets niet bij dit station? Meld het", `Trapvrij: fout bij station ${st.name} (${st.code})`));
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
    const start = el("button", `Vertrek vanaf ${st.name}`, "primary");
    start.type = "button";
    start.addEventListener("click", () => ctx.onStartHere(st.code));
    parts.push(start);
  }
  body.replaceChildren(...parts);
}
