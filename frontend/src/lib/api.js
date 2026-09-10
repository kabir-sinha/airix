export const API_URL = "http://127.0.0.1:8000";

/**
 * Fetches the full detail record (fare, index, elasticity, lead-time curve,
 * contribution, DGCA weight) for every tracked route. Used by pages that
 * need a cross-route view (Route Index, Lead-Time Index) — there is no
 * bulk endpoint for this, so it fans out to /api/routes/{route} once per
 * route. The route count is small (tracked routes, not all city pairs),
 * so this stays cheap.
 */
export async function fetchAllRouteDetails() {
  const routesRes = await fetch(`${API_URL}/api/routes`);
  if (!routesRes.ok) throw new Error("Could not load routes");
  const routesList = await routesRes.json();
  const details = await Promise.all(
    routesList.map((r) =>
      fetch(`${API_URL}/api/routes/${r.route}`).then((res) => (res.ok ? res.json() : null))
    )
  );
  return details.filter(Boolean);
}
