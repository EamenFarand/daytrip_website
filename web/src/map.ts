// The map: stations coloured by travel time, other states shown by shape (never by colour alone).
// Base map: OpenFreeMap (free, no key, no cookies). If it fails, the list still works.

import type { FeatureCollection, Point } from "geojson";
import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
// MapLibre looks for its worker next to its own file, which a bundler moves; let Vite bundle it instead.
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";

import { RAMP } from "./colors";
import { ACCESS_TEXT, changes, duration } from "./format";
import type { Verdict } from "./results";

const STYLE = { light: "https://tiles.openfreemap.org/styles/positron", dark: "https://tiles.openfreemap.org/styles/dark" };
const NL_BOUNDS: maplibregl.LngLatBoundsLike = [[3.3, 50.72], [7.25, 53.56]];
const FONT = ["Noto Sans Regular"];

const INK = {
  light: { ink: "#0b0b0b", surface: "#ffffff", muted: "#6b6a66", soft: "#898781" },
  dark: { ink: "#ffffff", surface: "#1a1a19", muted: "#c3c2b7", soft: "#898781" },
};

const LOCALE = {
  "Map.Title": "Kaart met bereikbare stations",
  "NavigationControl.ZoomIn": "Inzoomen",
  "NavigationControl.ZoomOut": "Uitzoomen",
  "NavigationControl.ResetBearing": "Noorden boven",
  "AttributionControl.ToggleAttribution": "Bronvermelding tonen of verbergen",
  "Popup.Close": "Sluiten",
  "CooperativeGesturesHandler.WindowsHelpText": "Houd Ctrl ingedrukt en scroll om in te zoomen",
  "CooperativeGesturesHandler.MacHelpText": "Houd ⌘ ingedrukt en scroll om in te zoomen",
  "CooperativeGesturesHandler.MobileHelpText": "Gebruik twee vingers om de kaart te verplaatsen",
};

type Theme = "light" | "dark";

maplibregl.setWorkerUrl(workerUrl);

/** Draw a marker icon on a canvas (2x for sharp edges). */
function icon(kind: "out" | "no" | "unknown" | "origin" | "idle", theme: Theme): { width: number; height: number; data: Uint8ClampedArray } {
  const c = INK[theme];
  const size = 36; // 18 css px at pixelRatio 2
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = size;
  const g = canvas.getContext("2d")!;
  const mid = size / 2;
  g.lineWidth = 4;
  if (kind === "out") {
    // hollow ring: not reachable within the filters
    g.beginPath();
    g.arc(mid, mid, 8, 0, Math.PI * 2);
    g.fillStyle = c.surface;
    g.fill();
    g.strokeStyle = c.soft;
    g.stroke();
  } else if (kind === "idle") {
    g.beginPath();
    g.arc(mid, mid, 9, 0, Math.PI * 2);
    g.fillStyle = c.muted;
    g.fill();
    g.strokeStyle = c.surface;
    g.stroke();
  } else if (kind === "no") {
    // square with a cross: not step-free
    g.fillStyle = c.muted;
    g.strokeStyle = c.surface;
    g.fillRect(8, 8, 20, 20);
    g.strokeRect(8, 8, 20, 20);
    g.strokeStyle = c.surface;
    g.lineWidth = 3.5;
    g.beginPath();
    g.moveTo(13, 13);
    g.lineTo(23, 23);
    g.moveTo(23, 13);
    g.lineTo(13, 23);
    g.stroke();
  } else if (kind === "unknown") {
    // diamond with a question mark: accessibility unknown
    g.beginPath();
    g.moveTo(mid, 4);
    g.lineTo(size - 4, mid);
    g.lineTo(mid, size - 4);
    g.lineTo(4, mid);
    g.closePath();
    g.fillStyle = c.soft;
    g.fill();
    g.strokeStyle = c.surface;
    g.stroke();
    g.fillStyle = c.surface;
    g.font = "bold 18px system-ui, sans-serif";
    g.textAlign = "center";
    g.textBaseline = "middle";
    g.fillText("?", mid, mid + 1);
  } else {
    // origin: bullseye
    g.beginPath();
    g.arc(mid, mid, 15, 0, Math.PI * 2);
    g.fillStyle = c.surface;
    g.fill();
    g.lineWidth = 4;
    g.strokeStyle = c.ink;
    g.stroke();
    g.beginPath();
    g.arc(mid, mid, 7, 0, Math.PI * 2);
    g.fillStyle = c.ink;
    g.fill();
  }
  const img = g.getImageData(0, 0, size, size);
  return { width: size, height: size, data: img.data };
}

export class StationMap {
  private map: maplibregl.Map | null = null;
  private theme: Theme;
  private data: FeatureCollection = { type: "FeatureCollection", features: [] };
  private selected: string | null = null;
  private hover: maplibregl.Popup | null = null;
  private ready = false;

  constructor(container: HTMLElement, private onPick: (code: string) => void, onFail: (reason: string) => void) {
    const dark = window.matchMedia("(prefers-color-scheme: dark)");
    this.theme = dark.matches ? "dark" : "light";
    try {
      this.map = new maplibregl.Map({
        container,
        style: STYLE[this.theme],
        bounds: NL_BOUNDS,
        fitBoundsOptions: { padding: 16 },
        cooperativeGestures: true,
        locale: LOCALE,
        attributionControl: { compact: true },
        dragRotate: false,
        pitchWithRotate: false,
        touchPitch: false,
      });
    } catch (e) {
      onFail(e instanceof Error ? e.message : String(e));
      return;
    }
    const map = this.map;
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    map.touchZoomRotate.disableRotation();
    map.on("style.load", () => this.install());
    map.on("error", (e) => console.warn("map:", e.error?.message ?? e));
    dark.addEventListener("change", (e) => {
      this.theme = e.matches ? "dark" : "light";
      this.ready = false;
      map.setStyle(STYLE[this.theme]);
    });

    const layers = ["st-reach", "st-other", "st-origin"];
    for (const id of layers) {
      map.on("click", id, (e) => {
        const code = e.features?.[0]?.properties?.code;
        if (code) this.onPick(code);
      });
      map.on("mouseenter", id, (e) => {
        map.getCanvas().style.cursor = "pointer";
        const f = e.features?.[0];
        if (!f || !window.matchMedia("(hover: hover)").matches) return;
        this.hover?.remove();
        const [lon, lat] = (f.geometry as Point).coordinates;
        const div = document.createElement("div");
        const name = document.createElement("strong");
        name.textContent = f.properties?.name;
        const line = document.createElement("div");
        line.textContent = f.properties?.tip;
        div.append(name, line);
        this.hover = new maplibregl.Popup({ closeButton: false, offset: 12, className: "map-tip" })
          .setLngLat([lon, lat])
          .setDOMContent(div)
          .addTo(map);
      });
      map.on("mouseleave", id, () => {
        map.getCanvas().style.cursor = "";
        this.hover?.remove();
      });
    }
  }

  /** (Re-)add our images, source and layers; runs on every style load, including theme switches. */
  private install(): void {
    const map = this.map;
    if (!map) return;
    for (const kind of ["out", "no", "unknown", "origin", "idle"] as const) {
      const name = `icon-${kind}`;
      if (map.hasImage(name)) map.removeImage(name);
      map.addImage(name, icon(kind, this.theme), { pixelRatio: 2 });
    }
    const c = INK[this.theme];
    const ramp = RAMP[this.theme];
    map.addSource("stations", { type: "geojson", data: this.data });
    map.addLayer({
      id: "st-other",
      type: "symbol",
      source: "stations",
      filter: ["in", ["get", "category"], ["literal", ["out-of-reach", "not-step-free", "unknown-access", "idle"]]],
      layout: {
        "icon-image": ["match", ["get", "category"], "not-step-free", "icon-no", "unknown-access", "icon-unknown", "idle", "icon-idle", "icon-out"],
        "icon-allow-overlap": true,
        "icon-size": ["interpolate", ["linear"], ["zoom"], 6, 0.75, 10, 1.1],
        "symbol-sort-key": ["-", 0, ["get", "trains"]],
      },
    });
    map.addLayer({
      id: "st-reach",
      type: "circle",
      source: "stations",
      filter: ["==", ["get", "category"], "reachable"],
      layout: { "circle-sort-key": ["-", 10, ["get", "band"]] }, // quick destinations on top
      paint: {
        "circle-color": ["match", ["get", "band"], 0, ramp[0], 1, ramp[1], 2, ramp[2], 3, ramp[3], ramp[4]],
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 6, 5.5, 10, 9],
        "circle-stroke-width": 2,
        "circle-stroke-color": c.surface,
      },
    });
    map.addLayer({
      id: "st-selected",
      type: "circle",
      source: "stations",
      filter: ["==", ["get", "code"], this.selected ?? ""],
      paint: { "circle-radius": 14, "circle-color": "rgba(0,0,0,0)", "circle-stroke-width": 3, "circle-stroke-color": c.ink },
    });
    map.addLayer({
      id: "st-origin",
      type: "symbol",
      source: "stations",
      filter: ["==", ["get", "category"], "origin"],
      layout: { "icon-image": "icon-origin", "icon-allow-overlap": true, "icon-size": 1.2 },
    });
    const labels = (id: string, categories: string[], minzoom: number): maplibregl.AddLayerObject => ({
      id,
      type: "symbol",
      source: "stations",
      minzoom,
      filter: ["in", ["get", "category"], ["literal", categories]],
      layout: {
        "text-field": ["get", "name"],
        "text-font": FONT,
        "text-size": ["interpolate", ["linear"], ["zoom"], 6, 11, 11, 14],
        "text-offset": [0, 1.1],
        "text-anchor": "top",
        "text-optional": true,
        "symbol-sort-key": ["-", 0, ["get", "trains"]], // busy stations get their label first
      },
      paint: { "text-color": c.ink, "text-halo-color": c.surface, "text-halo-width": 1.5 },
    });
    map.addLayer(labels("st-labels", ["origin", "reachable", "idle"], 0));
    map.addLayer(labels("st-labels-other", ["out-of-reach", "not-step-free", "unknown-access"], 10));
    this.ready = true;
  }

  update(verdicts: Verdict[], selected: string | null): void {
    this.selected = selected;
    this.data = {
      type: "FeatureCollection",
      features: verdicts.map((v) => ({
        type: "Feature",
        geometry: { type: "Point", coordinates: [v.station.lon, v.station.lat] },
        properties: {
          code: v.station.code,
          name: v.station.name,
          category: v.category,
          band: v.band,
          trains: v.station.trains,
          tip: tip(v),
        },
      })),
    };
    if (!this.map || !this.ready) return;
    (this.map.getSource("stations") as maplibregl.GeoJSONSource | undefined)?.setData(this.data);
    this.map.setFilter("st-selected", ["==", ["get", "code"], selected ?? ""]);
  }

  select(code: string | null): void {
    this.selected = code;
    if (this.map && this.ready) this.map.setFilter("st-selected", ["==", ["get", "code"], code ?? ""]);
  }

  focus(lon: number, lat: number): void {
    if (!this.map) return;
    const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const bounds = this.map.getBounds();
    if (bounds.contains([lon, lat])) return;
    if (still) this.map.jumpTo({ center: [lon, lat] });
    else this.map.easeTo({ center: [lon, lat], duration: 600 });
  }
}

function tip(v: Verdict): string {
  switch (v.category) {
    case "origin":
      return "Vertrekstation";
    case "reachable":
      return v.entry ? `${duration(v.entry[0])}, ${changes(v.entry[3])}` : "";
    case "not-step-free":
    case "unknown-access":
      return ACCESS_TEXT[v.station.status];
    case "idle":
      return ACCESS_TEXT[v.station.status];
    default:
      return "Niet bereikbaar binnen je keuzes";
  }
}
