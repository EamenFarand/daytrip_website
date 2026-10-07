import { describe, expect, it } from "vitest";

import { StationSearch, editDistance, normalise } from "./search";
import type { Station } from "./types";

const station = (code: string, name: string, trains: number): Station => ({
  code, name, slug: code.toLowerCase(), trains, aliases: [], lat: 52, lon: 5, status: "yes", tracks: {}, source: "EPIAP",
  source_date: null, verified: null, notes: [], uic: null, lifts: [],
});

const STATIONS = [
  station("UT", "Utrecht Centraal", 1342),
  station("UTVR", "Utrecht Vaartsche Rijn", 300),
  station("UTZL", "Utrecht Zuilen", 150),
  station("ASD", "Amsterdam Centraal", 1200),
  station("ASB", "Amsterdam Bijlmer ArenA", 324),
  station("HT", "'s-Hertogenbosch", 498),
  station("HTN", "Houten", 240),
  station("HTNC", "Houten Castellum", 200),
  station("SHL", "Schiphol Airport", 936),
  station("LAA", "Den Haag Laan v NOI", 330),
  station("APN", "Alphen a/d Rijn", 250),
  station("GVC", "Den Haag Centraal", 766),
  station("ZVT", "Zandvoort aan Zee", 60),
];
const search = new StationSearch(STATIONS);
const first = (q: string) => search.search(q)[0]?.code;

describe("station search", () => {
  it.each([
    ["Utrecht CS", "UT"],
    ["utrecht centraal", "UT"],
    ["utrect", "UT"], // typo
    ["Utrecht C", "UT"], // still typing
    ["A'dam", "ASD"],
    ["adam cs", "ASD"],
    ["Den Bosch", "HT"],
    ["s-hertogenbosch", "HT"],
    ["hertogenbosch", "HT"],
    ["houtne castellum", "HTNC"], // swapped letters
    ["houten", "HTN"],
    ["shl", "SHL"], // station code
    ["schiphol", "SHL"],
    ["laan van noi", "LAA"],
    ["alphen aan den rijn", "APN"],
    ["den haag cs", "GVC"],
    ["bijlmer", "ASB"],
    ["zandvoort", "ZVT"],
    ["The Hague", "GVC"], // English names
    ["the hague laan van noi", "LAA"],
    ["Amsterdam Central Station", "ASD"],
    ["utrecht central", "UT"],
  ])("%s -> %s", (query, code) => {
    expect(first(query)).toBe(code);
  });

  it("one letter still being typed is not expanded", () => {
    expect(search.search("a").map((s) => s.code)).toContain("ASD");
  });

  it("finds nothing for nonsense", () => {
    expect(search.search("qqqq")).toEqual([]);
    expect(search.search("  ")).toEqual([]);
  });

  it("normalises accents and punctuation", () => {
    expect(normalise("Liège-Guillemins")).toBe("liege guillemins");
    expect(normalise("A'dam")).toBe("adam");
  });

  it("edit distance counts a swap as one", () => {
    expect(editDistance("houtne", "houten")).toBe(1);
    expect(editDistance("utrect", "utrecht")).toBe(1);
  });
});
