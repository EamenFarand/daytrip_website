// Station search box following the WAI-ARIA 1.2 combobox pattern (list autocomplete, no automatic selection).

import { ACCESS_ICON, ACCESS_TEXT } from "./format";
import type { StationSearch } from "./search";
import type { Station } from "./types";

export class Combobox {
  private options: Station[] = [];
  private active = -1;

  constructor(
    private input: HTMLInputElement,
    private listbox: HTMLUListElement,
    private status: HTMLElement,
    private search: StationSearch,
    private onSelect: (station: Station) => void,
  ) {
    input.setAttribute("role", "combobox");
    input.setAttribute("aria-autocomplete", "list");
    input.setAttribute("aria-expanded", "false");
    input.setAttribute("aria-controls", listbox.id);
    listbox.setAttribute("role", "listbox");
    input.addEventListener("input", () => this.update());
    input.addEventListener("keydown", (e) => this.key(e));
    input.addEventListener("blur", () => setTimeout(() => this.close(), 150));
    input.addEventListener("focus", () => input.value && this.update());
    listbox.addEventListener("mousedown", (e) => e.preventDefault()); // keep focus in the input
    listbox.addEventListener("click", (e) => {
      const li = (e.target as HTMLElement).closest("li[data-index]");
      if (li) this.choose(Number(li.getAttribute("data-index")));
    });
  }

  setValue(text: string): void {
    this.input.value = text;
  }

  private update(): void {
    this.options = this.search.search(this.input.value);
    this.active = -1;
    this.render();
    const n = this.options.length;
    this.status.textContent = this.input.value.trim() === "" ? "" : n === 0 ? "Geen station gevonden" : `${n} station${n === 1 ? "" : "s"} gevonden, gebruik pijltjestoetsen om te kiezen`;
  }

  private render(): void {
    this.listbox.replaceChildren(
      ...this.options.map((st, i) => {
        const li = document.createElement("li");
        li.id = `${this.listbox.id}-${i}`;
        li.setAttribute("role", "option");
        li.dataset.index = String(i);
        li.setAttribute("aria-selected", String(i === this.active));
        const name = document.createElement("span");
        name.className = "opt-name";
        name.textContent = st.name;
        const status = document.createElement("span");
        status.className = `opt-status access-${st.status}`;
        status.textContent = `${ACCESS_ICON[st.status]} ${ACCESS_TEXT[st.status]}`;
        li.append(name, status);
        return li;
      }),
    );
    const open = this.options.length > 0;
    this.listbox.hidden = !open;
    this.input.setAttribute("aria-expanded", String(open));
    if (this.active >= 0) {
      this.input.setAttribute("aria-activedescendant", `${this.listbox.id}-${this.active}`);
      document.getElementById(`${this.listbox.id}-${this.active}`)?.scrollIntoView({ block: "nearest" });
    } else {
      this.input.removeAttribute("aria-activedescendant");
    }
  }

  private key(e: KeyboardEvent): void {
    const n = this.options.length;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (n === 0) return this.update();
      this.active = (this.active + 1) % n;
      this.render();
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      if (n === 0) return;
      this.active = this.active <= 0 ? n - 1 : this.active - 1;
      this.render();
    } else if (e.key === "Enter") {
      if (n > 0) {
        e.preventDefault();
        this.choose(this.active >= 0 ? this.active : 0);
      }
    } else if (e.key === "Escape") {
      if (!this.listbox.hidden) {
        e.preventDefault();
        this.close();
      } else if (this.input.value) {
        e.preventDefault();
        this.input.value = "";
        this.status.textContent = "";
      }
    }
  }

  private choose(i: number): void {
    const st = this.options[i];
    if (!st) return;
    this.input.value = st.name;
    this.close();
    this.onSelect(st);
  }

  private close(): void {
    this.options = [];
    this.active = -1;
    this.render();
  }
}
