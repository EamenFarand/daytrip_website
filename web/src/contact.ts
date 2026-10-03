// Where visitors report errors. Cloudflare Email Routing forwards it to Daan (docs/NEEDS_DAAN.md, answered).
export const REPORT_EMAIL = "meld@trapvrij.nl";

/** A mailto link with the subject filled in, so reports are easy to recognise and filter. */
export function reportLink(text: string, subject: string): HTMLAnchorElement {
  const a = document.createElement("a");
  a.href = `mailto:${REPORT_EMAIL}?subject=${encodeURIComponent(subject)}`;
  a.textContent = text;
  return a;
}
