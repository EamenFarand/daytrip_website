import "./style.css";

import { Combobox } from "./combobox";
import { REPORT_EMAIL, reportLink } from "./contact";
import { loadLifts, loadMeta, loadOrigin, loadStations } from "./data";
import { clock, duration, longDate, pageTitle, shortDate } from "./format";
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
    summary.textContent = "De gegevens konden niet worden geladen. Probeer het later opnieuw.";
    console.error(e);
    return;
  }
  const byCode = new Map(stations.map((s) => [s.code, s]));
  const bySlug = new Map(stations.map((s) => [s.slug, s]));
  const known = (code: string) => byCode.has(code);
  const [winStart, winEnd] = meta.window;
  const windowText = `${clock(winStart)} en ${clock(winEnd)}`;
  const dark = window.matchMedia("(prefers-color-scheme: dark)");
  const ramp = () => RAMP[dark.matches ? "dark" : "light"];

  // The origin is the station whose page this is; older links carry it in the hash (#van=HTNC).
  const pageOrigin = () => bySlug.get(stationFromPath(location.pathname) ?? "")?.code ?? null;
  const urlFor = (s: State) => pagePath(s.origin ? (byCode.get(s.origin)?.slug ?? null) : null) + toHash(s);
  let state: State = fromHash(location.hash, known);
  state.origin ??= pageOrigin();
  history.replaceState(null, "", urlFor(state));
  const intro = $("intro"); // a station page's own text, for search engines and visitors without JavaScript
  let doc: OriginDoc | null = null;
  let loading = false;
  let lifts: LiftStatus | null = null;

  $("data-dates").textContent =
    `Bijgewerkt op ${shortDate(meta.built)}. Reistijden volgens de dienstregeling van ${longDate(meta.days.weekday)} en ${longDate(meta.days.saturday)}; ` +
    `toegankelijkheid volgens de gegevens van ${shortDate(meta.epiap_date)}.`;

  // --- controls ---------------------------------------------------------------------------
  const form = $("filters") as HTMLFormElement;
  const range = $("max-time") as HTMLInputElement;
  const rangeOut = $("max-time-out") as HTMLOutputElement;
  range.max = String(MINUTE_STEPS.length - 1);
  const minutesText = (m: number) => (m >= MAX_MINUTES ? "geen grens" : duration(m));

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
    $("filters-summary").textContent = [
      state.profile === "stroller" ? "kinderwagen" : "zonder beperking",
      state.trains === "sprinter" ? "sprinters" : "ook intercity's",
      state.day === "weekday" ? "doordeweeks" : "zaterdag",
      state.maxChanges === 0 ? "geen overstap" : `max. ${state.maxChanges} overstap${state.maxChanges > 1 ? "pen" : ""}`,
      state.maxMinutes >= MAX_MINUTES ? "elke reistijd" : `max. ${duration(state.maxMinutes)}`,
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
  $("report-mail").replaceChildren(reportLink(REPORT_EMAIL, "Trapvrij: fout gezien"));

  // --- state --------------------------------------------------------------------------------
  function setState(patch: Partial<State>): void {
    const originChanged = patch.origin !== undefined && patch.origin !== state.origin;
    state = { ...state, ...patch };
    history.replaceState(null, "", urlFor(state));
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
      history.replaceState(null, "", urlFor(state));
      return;
    }
    const next = fromHash(location.hash, known);
    next.origin ??= pageOrigin();
    const originChanged = next.origin !== state.origin;
    state = next;
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
        dayLabel: state.day === "weekday" ? "doordeweeks" : "op zaterdag",
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
    if (!origin) return "Kies een vertrekstation om te zien waar je naartoe kunt.";
    if (!usable) {
      const why =
        origin.status === "no"
          ? `${origin.name} is niet drempelvrij. Met de kinderwagen kun je hier niet vertrekken.`
          : `Van ${origin.name} weten we niet of het drempelvrij is, dus we rekenen er niet mee.`;
      return `${why} Kies een ander station, of kies "Zonder beperking".`;
    }
    if (loading) return `Reizen vanaf ${origin.name} worden geladen…`;
    if (!doc) return "De reizen vanaf dit station konden niet worden geladen. Probeer het later opnieuw.";
    const time = state.maxMinutes >= MAX_MINUTES ? "" : ` binnen ${duration(state.maxMinutes)}`;
    const ch = state.maxChanges === 0 ? "zonder overstap" : `met hoogstens ${state.maxChanges} overstap${state.maxChanges > 1 ? "pen" : ""}`;
    const trains = state.trains === "sprinter" ? "sprinters en stoptreinen" : "alle treinen";
    const day = state.day === "weekday" ? "doordeweeks" : "op zaterdag";
    return `Vanaf ${origin.name}: ${count} station${count === 1 ? "" : "s"} bereikbaar${time}, ${ch} (${trains}, ${day}).`;
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
