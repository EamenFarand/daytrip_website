// Where visitors report errors (Daan's address for now; see docs/NEEDS_DAAN.md).
export const REPORT_EMAIL = "deonw_W@hotmail.com";

/** A mailto link with the subject filled in, so reports are easy to recognise and filter. */
export function reportLink(text: string, subject: string): HTMLAnchorElement {
  const a = document.createElement("a");
  a.href = `mailto:${REPORT_EMAIL}?subject=${encodeURIComponent(subject)}`;
  a.textContent = text;
  return a;
}
