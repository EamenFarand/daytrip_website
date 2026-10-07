// The results as a list: the accessible equivalent of the map, and the easiest way to browse on a phone.

import { ACCESS_ICON, accessText, changes, duration, frequency, originText, outOfReach } from "./format";
import { tr } from "./i18n";
import { type StationWarning, warnLine } from "./lifts";
import type { Verdict } from "./results";
import type { Station } from "./types";

const FIRST = 30; // show the quickest ones first, the rest on request

export interface ListContext {
  names: Map<string, Station>;
  windowText: string; // "08:30 en 12:00" (format.windowText)
  windowHours: number;
  ramp: string[];
  waiting: string | null; // why there are no results yet (no origin, loading...), or null once they're in
  warnings: (v: Verdict) => StationWarning[]; // lifts out along the journey
  onPick: (code: string) => void;
}

function item(v: Verdict, ctx: ListContext): HTMLLIElement {
  const li = document.createElement("li");
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "result";
  btn.dataset.code = v.station.code;
  btn.addEventListener("click", () => ctx.onPick(v.station.code));

  const mark = document.createElement("span");
  mark.className = `mark mark-${v.category}`;
  mark.setAttribute("aria-hidden", "true");
  if (v.category === "reachable") mark.style.background = ctx.ramp[v.band];

  const text = document.createElement("span");
  text.className = "result-text";
  const name = document.createElement("span");
  name.className = "result-name";
  name.textContent = v.station.name;
  const meta = document.createElement("span");
  meta.className = "result-meta";
  if (v.entry) {
    const [median, , perHour, n, via] = v.entry;
    const viaNames = via ? via.split("|").map((c) => ctx.names.get(c)?.name ?? c) : [];
    meta.textContent = [duration(median), changes(n), frequency(perHour, ctx.windowHours, ctx.windowText)].join(" · ");
    text.append(name, meta);
    if (viaNames.length) {
      const viaEl = document.createElement("span");
      viaEl.className = "result-via";
      viaEl.textContent = `via ${viaNames.join(", ")}`;
      text.append(viaEl);
    }
    const warnings = ctx.warnings(v);
    if (warnings.length) {
      const warn = document.createElement("span");
      warn.className = "result-warn";
      warn.textContent = warnLine(warnings);
      text.append(warn);
    }
  } else {
    meta.textContent = `${ACCESS_ICON[v.station.status]} ${accessText(v.station.status)}`;
    text.append(name, meta);
  }
  btn.append(mark, text);
  li.append(btn);
  return li;
}

function section(title: string, verdicts: Verdict[], ctx: ListContext, open: boolean): HTMLElement {
  const details = document.createElement("details");
  details.open = open;
  const summary = document.createElement("summary");
  summary.textContent = `${title} (${verdicts.length})`;
  const ul = document.createElement("ul");
  ul.className = "results";
  ul.append(...verdicts.map((v) => item(v, ctx)));
  details.append(summary, ul);
  return details;
}

export function renderList(container: HTMLElement, verdicts: Verdict[], ctx: ListContext, stroller: boolean): void {
  const reachable = verdicts
    .filter((v) => v.category === "reachable")
    .sort((a, b) => a.entry![0] - b.entry![0] || a.station.name.localeCompare(b.station.name, "nl"));
  const blocked = verdicts.filter((v) => v.category === "not-step-free" || v.category === "unknown-access");
  const outside = verdicts.filter((v) => v.category === "out-of-reach");
  const byName = (a: Verdict, b: Verdict) => a.station.name.localeCompare(b.station.name, "nl");

  const parts: HTMLElement[] = [];
  const heading = document.createElement("h2");
  heading.id = "results-heading";
  const title = tr({ nl: "Bereikbare stations", en: "Reachable stations" });
  heading.textContent = ctx.waiting ? title : `${title} (${reachable.length})`;
  parts.push(heading);

  if (reachable.length === 0) {
    const p = document.createElement("p");
    p.textContent =
      ctx.waiting ??
      tr({ nl: "Geen stations binnen je keuzes. Probeer meer overstappen of een langere reistijd.", en: "No stations within your choices. Try more changes or a longer travel time." });
    parts.push(p);
  } else {
    let shown = 0;
    const ul = document.createElement("ul");
    ul.className = "results";
    for (const v of reachable) {
      const li = item(v, ctx);
      if (shown >= FIRST) li.hidden = true;
      ul.append(li);
      shown++;
    }
    parts.push(ul);
    if (reachable.length > FIRST) {
      const more = document.createElement("button");
      more.type = "button";
      more.className = "more";
      more.textContent = tr({ nl: `Toon alle ${reachable.length} stations`, en: `Show all ${reachable.length} stations` });
      more.addEventListener("click", () => {
        const first = ul.querySelector<HTMLElement>("li[hidden] button");
        ul.querySelectorAll("li[hidden]").forEach((li) => ((li as HTMLElement).hidden = false));
        more.remove();
        first?.focus();
      });
      parts.push(more);
    }
  }
  if (stroller && blocked.length) parts.push(section(tr({ nl: "Niet drempelvrij of onbekend", en: "Not step-free or unknown" }), blocked.sort(byName), ctx, false));
  if (outside.length) parts.push(section(outOfReach(), outside.sort(byName), ctx, false));
  container.replaceChildren(...parts);
}

/** The travel-time bands of results.BANDS. */
function bandLabels(): string[] {
  return [tr({ nl: "tot 30 min", en: "up to 30 min" }), "31–60 min", "61–90 min", "91–120 min", tr({ nl: "meer dan 2 uur", en: "over 2 hours" })];
}

/** Legend: travel-time bands (colour + text) and marker shapes (shape + text). */
export function renderLegend(
  container: HTMLElement,
  ramp: string[],
  o: { maxMinutes: number; stroller: boolean; waiting: boolean; origin: boolean },
): void {
  const items: [string, string, string?][] = [];
  if (o.waiting) {
    items.push(["mark mark-idle", o.stroller ? tr({ nl: "Drempelvrij (of deels)", en: "Step-free (or partly)" }) : "Station"]);
  } else {
    bandLabels().forEach((label, i) => {
      const lower = [0, 30, 60, 90, 120][i];
      if (lower < o.maxMinutes) items.push(["mark mark-reachable", label, ramp[i]]);
    });
  }
  if (o.origin) items.push(["mark mark-origin", originText()]);
  if (!o.waiting) items.push(["mark mark-out-of-reach", outOfReach()]);
  if (o.stroller) {
    items.push(["mark mark-not-step-free", accessText("no")]);
    items.push(["mark mark-unknown-access", accessText("unknown")]);
  }
  const ul = document.createElement("ul");
  for (const [cls, label, color] of items) {
    const li = document.createElement("li");
    const m = document.createElement("span");
    m.className = cls;
    m.setAttribute("aria-hidden", "true");
    if (color) m.style.background = color;
    li.append(m, document.createTextNode(label));
    ul.append(li);
  }
  container.replaceChildren(ul);
}
