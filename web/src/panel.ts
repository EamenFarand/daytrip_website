// Station details in a dialog: step-free status with source and date, the journey, lifts, and links to check.

import { ACCESS_ICON, ACCESS_TEXT, TRACK_TEXT, changes, clock, duration, frequency, longDate, shortDate } from "./format";
import type { Verdict } from "./results";
import type { LiftStatus, Meta, Station } from "./types";

export interface PanelContext {
  meta: Meta;
  names: Map<string, Station>;
  origin: Station | null;
  dayLabel: string; // "doordeweeks" / "op zaterdag"
  dayIso: string;
  lifts: LiftStatus | null;
  stroller: boolean;
  onStartHere: (code: string) => void;
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
    const dl = el("dl", undefined, "facts");
    const add = (term: string, value: string) => dl.append(el("dt", term), el("dd", value));
    add("Reistijd", median === fastest ? duration(median) : `meestal ${duration(median)} (snelste ${duration(fastest)})`);
    add("Overstappen", changes(n));
    if (via) {
      const names = via.split("|").map((c) => {
        const s = ctx.names.get(c);
        return s ? `${s.name} (${ACCESS_TEXT[s.status].toLowerCase()})` : c;
      });
      add("Overstappen in", names.join(", "));
    }
    add("Hoe vaak", frequency(perHour, (end - start) / 60, windowText));
    box.append(dl);
    box.append(el("p", `Gebaseerd op de dienstregeling van ${longDate(ctx.dayIso)}, vertrek tussen ${windowText}.`, "small"));
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
  const out = new Map((ctx.lifts?.out ?? []).map((o) => [o.id, o]));
  const broken = st.lifts.filter((l) => out.has(l.id)).length;
  const ul = el("ul", undefined, "lifts");
  for (const lift of st.lifts) {
    const where = lift.tracks.length ? `spoor ${lift.tracks.join("/")}` : "hal of ingang";
    const li = el("li", `${lift.code ?? lift.id} (${where})`);
    const o = out.get(lift.id);
    if (o) {
      const warn = el("strong", ` ⚠ Buiten gebruik${o.since ? ` sinds ${shortDate(o.since)}` : ""}`, "warn");
      li.append(warn);
    }
    ul.append(li);
  }
  // a short list is shown as is; a long one folds away unless a lift is out of order
  if (st.lifts.length <= 4) {
    box.append(ul);
  } else {
    const details = el("details");
    details.open = broken > 0;
    details.append(el("summary", `${st.lifts.length} liften${broken ? `, ${broken} buiten gebruik` : ""}`), ul);
    box.append(details);
  }
  box.append(
    el("p", ctx.lifts ? `Liftstatus bijgewerkt: ${new Date(ctx.lifts.updated).toLocaleString("nl-NL")}.` : "Actuele liftstoringen tonen we binnenkort. Controleer ze vóór vertrek.", "small"),
  );
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
