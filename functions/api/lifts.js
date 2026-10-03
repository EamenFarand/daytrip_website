// GET /api/lifts: the live lift status, which the listener on Daan's home server (lifts/) writes
// to Workers KV. Read-only, our only server-side code (docs/DECISIONS.md, 2026-10-02).
// No data (yet) is a 404 and a missing KV binding a 503; the site then says the lift status is unknown.
export async function onRequestGet({ env }) {
  const text = (status, body) =>
    new Response(body, { status, headers: { "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store" } });
  if (!env.LIFTS) return text(503, "Liftstatus is niet ingesteld.");
  const body = await env.LIFTS.get("lifts");
  if (!body) return text(404, "Geen liftstatus beschikbaar.");
  return new Response(body, {
    headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "public, max-age=60" },
  });
}
