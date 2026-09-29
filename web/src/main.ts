import "./style.css";

import { Combobox } from "./combobox";
import { loadLifts, loadMeta, loadOrigin, loadStations } from "./data";
import { clock, duration, longDate, shortDate } from "./format";
import { renderLegend, renderList } from "./list";
import { RAMP } from "./colors";
import type { StationMap } from "./map";
import { renderPanel } from "./panel";
import { originUsable, verdicts } from "./results";
import { StationSearch } from "./search";
import { DEFAULTS, MAX_MINUTES, MINUTE_STEPS, fromHash, stationFromPath, toHash, type State } from "./state";
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
  const known = (code: string) => byCode.has(code);
  const [winStart, winEnd] = meta.window;
  const windowText = `${clock(winStart)} en ${clock(winEnd)}`;
  const dark = window.matchMedia("(prefers-color-scheme: dark)");
  const ramp = () => RAMP[dark.matches ? "dark" : "light"];

  let state: State = fromHash(location.hash, known);
  const fromPath = stationFromPath(location.pathname);
  if (fromPath && known(fromPath)) state.selected = fromPath;
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

  // --- state --------------------------------------------------------------------------------
  function setState(patch: Partial<State>): void {
    const originChanged = patch.origin !== undefined && patch.origin !== state.origin;
    state = { ...state, ...patch };
    history.replaceState(null, "", `/${toHash(state)}`);
    if (originChanged) void refresh();
    else if (Object.keys(patch).every((k) => k === "selected")) renderSelection(); // keep the list (and focus) intact
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

  window.addEventListener("hashchange", () => {
    const next = fromHash(location.hash, known);
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
    const usable = originUsable(origin, state);
    current = verdicts(stations, usable ? doc : null, state);
    const stroller = state.profile === "stroller";

    map?.update(current, state.selected);
    renderLegend($("legend"), ramp(), state.maxMinutes, stroller);
    renderList($("results"), current, { names: byCode, windowText, windowHours: (winEnd - winStart) / 60, ramp: ramp(), onPick: (code) => setState({ selected: code }) }, stroller);
    summary.textContent = describe(origin, usable, current.filter((v) => v.category === "reachable").length);
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
      return `${origin.name} is niet drempelvrij, of dat is onbekend. Met de kinderwagen kun je hier niet instappen. Kies een ander station, of kies "Zonder beperking".`;
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
  void loadLifts().then((l) => {
    lifts = l;
    if (l) render();
  });
  if (!location.hash && !fromPath) state = { ...DEFAULTS };
  await refresh();
}

void start();
