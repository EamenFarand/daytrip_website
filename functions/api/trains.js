// GET /api/trains: per day, which train numbers ran with only units NS marks accessible, and which didn't.
// The listener on Daan's home server (lifts/) writes it to Workers KV from NS's journey messages (InfoPlus RIT
// via NDOV Loket, CC0); the build reads it to decide which trains count as without steps (pipeline/stepfree/trains.py,
// docs/DECISIONS.md 2026-10-07). Read-only. No data (yet) is a 404; the build then uses its old rule.
export async function onRequestGet({ env }) {
  const text = (status, body) =>
    new Response(body, { status, headers: { "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store" } });
  if (!env.LIFTS) return text(503, "Treingegevens zijn niet ingesteld.");
  const body = await env.LIFTS.get("trains");
  if (!body) return text(404, "Geen treingegevens beschikbaar.");
  return new Response(body, {
    headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "public, max-age=300" },
  });
}
