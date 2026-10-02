// GET /api/lifts: the live lift status, which the listener on Daan's home server (lifts/) writes
// to Workers KV. Read-only, our only server-side code (docs/DECISIONS.md, 2026-10-02).
// No data (yet) is a 404; the site then says the lift status is unknown.
export async function onRequestGet({ env }) {
  const body = env.LIFTS ? await env.LIFTS.get("lifts") : null;
  if (!body) {
    return new Response("Geen liftstatus beschikbaar.", {
      status: 404,
      headers: { "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store" },
    });
  }
  return new Response(body, {
    headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "public, max-age=60" },
  });
}
