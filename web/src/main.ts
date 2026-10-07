import "./style.css";

import { Combobox } from "./combobox";
import { REPORT_EMAIL, reportLink } from "./contact";
import { loadLifts, loadMeta, loadOrigin, loadStations } from "./data";
import { duration, longDate, pageTitle, shortDate, windowText as windowWords } from "./format";
import { inLang, lang, other, tr } from "./i18n";
import { freshness, journeyWarnings } from "./lifts";
import { renderLegend, renderList } from "./list";
import { RAMP } from "./colors";
import type { StationMap } from "./map";
import { renderPanel } from "./panel";
import { originUsable, verdicts, type Verdict } from "./results";
import { StationSearch } from "./search";
import { MAX_MINUTES, MINUTE_STEPS, fromHash, pagePath, stationFromPath, toHash, type State } from "./state";
import type { LiftStatus, Meta, OriginDoc, Station } from "./types";

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;

async function start(): Promise<void> {
  const summary = $("summary");
  let meta: Meta, stations: Station[];
  try {
    [meta, stations] = await Promise.all([loadMeta(), loadStations()]);
  } catch (e) {
    summary.textContent = tr({ nl: "De gegevens konden niet worden geladen. Probeer het later opnieuw.", en: "The data could not be loaded. Please try again later." });
    console.error(e);
    return;
  }
  const byCode = new Map(stations.map((s) => [s.code, s]));
  const bySlug = new Map(stations.map((s) => [s.slug, s]));
  const known = (code: string) => byCode.has(code);
  const [winStart, winEnd] = meta.window;
  const windowText = windowWords(winStart, winEnd);
  const dark = window.matchMedia("(prefers-color-scheme: dark)");
  const ramp = () => RAMP[dark.matches ? "dark" : "light"];

  // The origin is the station whose page this is; older links carry it in the hash (#van=HTNC).
  const pageOrigin = () => bySlug.get(stationFromPath(location.pathname) ?? "")?.code ?? null;
  const urlFor = (s: State) => pagePath(s.origin ? (byCode.get(s.origin)?.slug ?? null) : null) + toHash(s);
  let state: State = fromHash(location.hash, known);
  state.origin ??= pageOrigin();
  // The language switch leads to the same page and view in the other language.
  const langSwitch = document.getElementById("lang-switch") as HTMLAnchorElement | null;
  const switchTo = (url: string) => {
    if (langSwitch) langSwitch.href = inLang(url, other(lang));
  };
  const showUrl = () => {
    const url = urlFor(state);
    history.replaceState(null, "", url);
    switchTo(url);
  };
  showUrl();
  const intro = $("intro"); // a station page's own text, for search engines and visitors without JavaScript
  let doc: OriginDoc | null = null;
  let loading = false;
  let lifts: LiftStatus | null = null;

  const [built, weekday, saturday, epiap] = [shortDate(meta.built), longDate(meta.days.weekday), longDate(meta.days.saturday), shortDate(meta.epiap_date)];
  $("data-dates").textContent = tr({
    nl: `Bijgewerkt op ${built}. Reistijden volgens de dienstregeling van ${weekday} en ${saturday}; toegankelijkheid volgens de gegevens van ${epiap}.`,
    en: `Updated on ${built}. Travel times from the timetable for ${weekday} and ${saturday}; accessibility from the data of ${epiap}.`,
  });

  // --- controls ---------------------------------------------------------------------------
  const form = $("filters") as HTMLFormElement;
  const range = $("max-time") as HTMLInputElement;
  const rangeOut = $("max-time-out") as HTMLOutputElement;
  range.max = String(MINUTE_STEPS.length - 1);
  const minutesText = (m: number) => (m >= MAX_MINUTES ? tr({ nl: "geen grens", en: "no limit" }) : duration(m));

  form.addEventListener("change", (e) => {
    const t = e.target as HTMLInputElement;
    if (t.name === "profile") setState({ profile: t.value as State["profile"] });
    if (t.name === "trains") setState({ trains: t.value as State["trains"] });
    if (t.name === "day") setState({ day: t.value as State["day"] });
    if (t.name === "changes") setState({ maxChanges: Number(t.value) as State["maxChanges"] });
  });
  range.addEventListener("input", () => setState({ maxMinutes: MINUTE_STEPS[Number(range.value)] }));
  form.addEventListener("submit", (e) => e.preventDefault());

  // filters are folded on phones (one line summary), open on wide screens
  const filtersBox = $("filters-box") as HTMLDetailsElement;
  filtersBox.open = window.matchMedia("(min-width: 900px)").matches;

  function syncControls(): void {
    const check = (name: string, value: string) => {
      const input = form.querySelector<HTMLInputElement>(`input[name="${name}"][value="${value}"]`);
      if (input) input.checked = true;
    };
    check("profile", state.profile);
    check("trains", state.trains);
    check("day", state.day);
    check("changes", String(state.maxChanges));
    range.value = String(Math.max(0, MINUTE_STEPS.indexOf(state.maxMinutes)));
    rangeOut.value = minutesText(state.maxMinutes);
    range.setAttribute("aria-valuetext", minutesText(state.maxMinutes));
    const n = state.maxChanges;
    $("filters-summary").textContent = [
      state.profile === "stroller" ? tr({ nl: "kinderwagen", en: "pram" }) : tr({ nl: "zonder beperking", en: "without a pram" }),
      state.trains === "sprinter" ? "sprinters" : tr({ nl: "ook intercity's", en: "intercity too" }),
      state.day === "weekday" ? tr({ nl: "doordeweeks", en: "weekday" }) : tr({ nl: "zaterdag", en: "Saturday" }),
      n === 0 ? tr({ nl: "geen overstap", en: "no changes" }) : tr({ nl: `max. ${n} overstap${n > 1 ? "pen" : ""}`, en: `max. ${n} change${n > 1 ? "s" : ""}` }),
      state.maxMinutes >= MAX_MINUTES ? tr({ nl: "elke reistijd", en: "any travel time" }) : `max. ${duration(state.maxMinutes)}`,
    ].join(" · ");
  }

  // --- search -------------------------------------------------------------------------------
  const combo = new Combobox($("origin"), $("origin-list"), $("origin-status"), new StationSearch(stations), (st) =>
    setState({ origin: st.code, selected: null }),
  );

  // --- map: loaded after the page so the list is usable at once (the map library is ~300 KB) ---
  let map: StationMap | null = null;
  const mapFailed = (reason: string) => {
    console.warn("map unavailable:", reason);
    $("map").hidden = true;
    $("map-fallback").hidden = false;
  };
  import("./map")
    .then(({ StationMap }) => {
      map = new StationMap($("map"), (code) => setState({ selected: code }), mapFailed);
      render();
    })
    .catch((e) => mapFailed(String(e)));

  // --- dialogs ------------------------------------------------------------------------------
  const stationDialog = $("station") as HTMLDialogElement;
  const aboutDialog = $("about") as HTMLDialogElement;
  // Closing the station panel clears the selection directly; the "close" event is only a fallback
  // (browsers don't fire it for a tab in the background).
  const closeStation = () => setState({ selected: null });
  const closers = new Map<HTMLDialogElement, () => void>([
    [stationDialog, closeStation],
    [aboutDialog, () => aboutDialog.close()],
  ]);
  for (const [d, close] of closers) {
    d.querySelector("[data-close]")?.addEventListener("click", close);
    d.addEventListener("click", (e) => e.target === d && close()); // click on the backdrop
    d.addEventListener("cancel", (e) => {
      e.preventDefault(); // Escape: close our way, so state and URL follow
      close();
    });
  }
  stationDialog.addEventListener("close", () => state.selected && closeStation());
  $("about-open").addEventListener("click", () => aboutDialog.showModal());
  $("report-mail").replaceChildren(reportLink(REPORT_EMAIL, tr({ nl: "Trapvrij: fout gezien", en: "Trapvrij: error spotted" })));

  // --- state --------------------------------------------------------------------------------
  function setState(patch: Partial<State>): void {
    const originChanged = patch.origin !== undefined && patch.origin !== state.origin;
    state = { ...state, ...patch };
    showUrl();
    if (originChanged) {
      const origin = state.origin ? byCode.get(state.origin) : undefined;
      if (origin) map?.reveal(origin.lon, origin.lat);
      void refresh();
    } else if (Object.keys(patch).every((k) => k === "selected")) renderSelection(); // keep the list (and focus) intact
    else render();
  }

  async function refresh(): Promise<void> {
    doc = null;
    if (state.origin) {
      loading = true;
      render();
      try {
        doc = await loadOrigin(state.origin);
      } catch (e) {
        console.error(e);
      }
      loading = false;
    }
    render();
  }

  // The skip link moves focus without touching the hash, which holds the state.
  document.querySelector(".skip")?.addEventListener("click", (e) => {
    e.preventDefault();
    $("results").focus();
  });

  window.addEventListener("hashchange", () => {
    if (location.hash && !location.hash.includes("=")) {
      // an in-page link such as #results, not a new state: put the state back in the URL
      showUrl();
      return;
    }
    const next = fromHash(location.hash, known);
    next.origin ??= pageOrigin();
    const originChanged = next.origin !== state.origin;
    state = next;
    switchTo(urlFor(state));
    if (originChanged) void refresh();
    else render();
  });

  let current: ReturnType<typeof verdicts> = [];

  function render(): void {
    syncControls();
    const origin = state.origin ? byCode.get(state.origin) : undefined;
    if (origin && document.activeElement !== $("origin")) combo.setValue(origin.name);
    document.title = pageTitle(origin?.name);
    if (intro.dataset.station) intro.hidden = intro.dataset.station !== state.origin;
    const usable = originUsable(origin, state);
    current = verdicts(stations, usable ? doc : null, state);
    const stroller = state.profile === "stroller";

    const text = describe(origin, usable, current.filter((v) => v.category === "reachable").length);
    summary.textContent = text;
    const waiting = !usable || loading || !doc ? text : null; // the list then says why it's empty

    const fresh = freshness(lifts, new Date());
    const warnings = (v: Verdict) => journeyWarnings(v.entry, usable ? origin : undefined, v.station, byCode, lifts, fresh);

    map?.update(current, state.selected);
    renderLegend($("legend"), ramp(), { maxMinutes: state.maxMinutes, stroller, waiting: waiting !== null, origin: !!origin });
    renderList($("results"), current, { names: byCode, windowText, windowHours: (winEnd - winStart) / 60, ramp: ramp(), waiting, warnings, onPick: (code) => setState({ selected: code }) }, stroller);
    renderSelection();
  }

  function renderSelection(): void {
    map?.select(state.selected);
    const origin = state.origin ? byCode.get(state.origin) : undefined;
    const usable = originUsable(origin, state);
    const stroller = state.profile === "stroller";
    const selected = state.selected ? current.find((v) => v.station.code === state.selected) : undefined;
    if (selected) {
      renderPanel($("station-body"), $("station-title"), selected, {
        meta,
        names: byCode,
        origin: usable ? (origin ?? null) : null,
        dayIso: meta.days[state.day],
        lifts,
        fresh: freshness(lifts, new Date()),
        stroller,
        onStartHere: (code) => {
          stationDialog.close();
          setState({ origin: code, selected: null });
        },
      });
      if (!stationDialog.open) stationDialog.showModal();
    } else if (stationDialog.open) {
      stationDialog.close();
    }
  }

  function describe(origin: Station | undefined, usable: boolean, count: number): string {
    if (!origin) return tr({ nl: "Kies een vertrekstation om te zien waar je naartoe kunt.", en: "Choose a starting station to see where you can go." });
    const name = origin.name;
    if (!usable) {
      const why =
        origin.status === "no"
          ? tr({ nl: `${name} is niet drempelvrij. Met de kinderwagen kun je hier niet vertrekken.`, en: `${name} is not step-free, so you can't start here with a pram.` })
          : tr({ nl: `Van ${name} weten we niet of het drempelvrij is, dus we rekenen er niet mee.`, en: `We don't know whether ${name} is step-free, so we don't count it.` });
      return `${why} ${tr({ nl: 'Kies een ander station, of kies "Zonder beperking".', en: 'Choose another station, or choose "Without a pram".' })}`;
    }
    if (loading) return tr({ nl: `Reizen vanaf ${name} worden geladen…`, en: `Loading journeys from ${name}…` });
    if (!doc) {
      return tr({
        nl: "De reizen vanaf dit station konden niet worden geladen. Probeer het later opnieuw.",
        en: "The journeys from this station could not be loaded. Please try again later.",
      });
    }
    const limit = state.maxMinutes >= MAX_MINUTES ? null : duration(state.maxMinutes);
    const n = state.maxChanges;
    const s = count === 1 ? "" : "s";
    const sprinters = state.trains === "sprinter";
    const weekday = state.day === "weekday";
    return tr({
      nl:
        `Vanaf ${name}: ${count} station${s} bereikbaar${limit ? ` binnen ${limit}` : ""}, ` +
        `${n === 0 ? "zonder overstap" : `met hoogstens ${n} overstap${n > 1 ? "pen" : ""}`} ` +
        `(${sprinters ? "sprinters en stoptreinen" : "alle treinen"}, ${weekday ? "doordeweeks" : "op zaterdag"}).`,
      en:
        `From ${name}: ${count} station${s} you can reach${limit ? ` within ${limit}` : ""}, ` +
        `${n === 0 ? "without changing" : `with at most ${n} change${n > 1 ? "s" : ""}`} ` +
        `(${sprinters ? "sprinters and stopping trains" : "all trains"}, ${weekday ? "on a weekday" : "on Saturday"}).`,
    });
  }

  dark.addEventListener("change", () => render());
  // lift status changes during the day: fetch it now and every 5 minutes while the page is open
  const updateLifts = () =>
    loadLifts().then((l) => {
      const changed = JSON.stringify(l) !== JSON.stringify(lifts);
      lifts = l;
      if (changed) render();
    });
  void updateLifts();
  setInterval(() => void updateLifts(), 5 * 60_000);
  await refresh();
}

void start();
