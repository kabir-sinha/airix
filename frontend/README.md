# AIRIX dashboard (frontend)

The Next.js dashboard for [AIRIX](../README.md). It reads everything from the AIRIX FastAPI backend and draws the index, route and lead-time views.

## Run it

Start the backend first (see the [main README](../README.md#running-locally)), then:

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:3000>. The backend must be running on port 8000.

## Pages

| Route | What it shows |
|---|---|
| `/` | Overview: headline index, trend, route network map and what drove the latest movement |
| `/routes` | Every route's index: largest movers, spread and the full table |
| `/routes/[route]` | One route, e.g. `/routes/DEL-BOM`: fare by booking horizon, fare breakdown, explanation of movement |
| `/lead-time` | How fares change as departure approaches |
| `/data-quality` | Cleaning audit trail: what was excluded or flagged, and why |
| `/validation` | Back-test results and the synthetic-proxy disclosure |

## Stack

Next.js 16 (App Router), React 19, Tailwind CSS 4, Recharts. Shared layout and UI pieces are in `src/components/`, API calls in `src/lib/api.js`.

## Scripts

| Command | Does |
|---|---|
| `npm run dev` | Development server with hot reload |
| `npm run build` | Production build |
| `npm run start` | Serve the production build |
| `npm run lint` | ESLint |
