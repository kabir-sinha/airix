"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import AppShell, { SimpleHeader } from "@/components/AppShell";
import { Card, SortableHeader, Sparkline } from "@/components/ui";
import { API_URL, fetchAllRouteDetails } from "@/lib/api";

export default function RouteIndex() {
  const router = useRouter();
  const [rows, setRows] = useState(null);
  const [sparklines, setSparklines] = useState({});
  const [error, setError] = useState(null);
  const [sortKey, setSortKey] = useState("contribution_pp");
  const [sortDir, setSortDir] = useState("desc");
  const [search, setSearch] = useState("");

  useEffect(() => {
    async function load() {
      try {
        const [details, heatmapRes] = await Promise.all([
          fetchAllRouteDetails(),
          fetch(`${API_URL}/api/heatmap?freq=weekly`).then((r) => r.json()),
        ]);
        setRows(
          details.map((d) => ({
            route: d.route,
            current_index: d.current_index,
            own_index_change: d.own_index_change,
            current_average_fare: d.current_average_fare,
            elasticity_pct_per_day: d.elasticity_pct_per_day,
            lead_time_increase_pct: d.lead_time_increase_pct,
            contribution_pp: d.contribution_pp,
            dgca_weight_pct: d.dgca_weight_pct,
          }))
        );
        const sparkMap = {};
        heatmapRes.routes?.forEach((route, i) => {
          sparkMap[route] = heatmapRes.matrix[i];
        });
        setSparklines(sparkMap);
      } catch (err) {
        setError("Could not load the route index. Is the backend running?");
      }
    }
    load();
  }, []);

  const tableData = useMemo(() => {
    if (!rows) return [];
    let out = rows;
    if (search.trim()) {
      const q = search.trim().toUpperCase();
      out = out.filter((r) => r.route.includes(q));
    }
    return [...out].sort((a, b) => {
      const av = a[sortKey] ?? -Infinity;
      const bv = b[sortKey] ?? -Infinity;
      const diff = av - bv;
      return sortDir === "asc" ? diff : -diff;
    });
  }, [rows, search, sortKey, sortDir]);

  function toggleSort(key) {
    if (sortKey === key) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--bg)] text-red-500">
        {error}
      </div>
    );
  }

  if (!rows) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--bg)] text-[var(--text-muted)] font-mono-num text-sm">
        LOADING ROUTE INDEX...
      </div>
    );
  }

  const movers = [...rows].sort((a, b) => Math.abs(b.contribution_pp) - Math.abs(a.contribution_pp)).slice(0, 6);
  const maxMoverAbs = Math.max(...movers.map((m) => Math.abs(m.contribution_pp)), 0.01);

  const header = (
    <SimpleHeader
      title="Route Index"
      subtitle={`Per-corridor index levels and fare movement · ${rows.length} tracked routes`}
    />
  );

  return (
    <AppShell header={header}>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <h2 className="font-heading text-lg mb-1">Largest movers</h2>
          <p className="lbl mb-4">Latest round · ranked by |contribution|</p>
          <div className="space-y-3">
            {movers.map((m) => (
              <div
                key={m.route}
                onClick={() => router.push(`/routes/${m.route}`)}
                className="grid grid-cols-[70px_1fr_60px] items-center gap-3 py-1 cursor-pointer group"
              >
                <span className="font-mono-num text-sm group-hover:text-[var(--amber)] transition-colors">
                  {m.route}
                </span>
                <div className="h-2 rounded-sm bg-[var(--border)] overflow-hidden">
                  <div
                    className="h-2 rounded-sm"
                    style={{
                      width: `${(Math.abs(m.contribution_pp) / maxMoverAbs) * 100}%`,
                      background: m.contribution_pp >= 0 ? "var(--amber)" : "var(--teal)",
                    }}
                  />
                </div>
                <span
                  className="font-mono-num text-sm text-right"
                  style={{ color: m.contribution_pp >= 0 ? "var(--amber)" : "var(--teal)" }}
                >
                  {m.contribution_pp >= 0 ? "+" : ""}
                  {m.contribution_pp}
                </span>
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <h2 className="font-heading text-lg mb-1">Index spread</h2>
          <p className="lbl mb-4">Current index level, high to low</p>
          <div className="space-y-2 text-sm">
            {[...rows]
              .sort((a, b) => b.current_index - a.current_index)
              .slice(0, 6)
              .map((r) => (
                <div key={r.route} className="flex items-center justify-between border-b border-[var(--border)] last:border-b-0 py-1.5">
                  <span className="font-mono-num">{r.route}</span>
                  <span className="font-mono-num font-medium">{r.current_index}</span>
                </div>
              ))}
          </div>
        </Card>
      </div>

      <Card className="!p-0 overflow-hidden">
        <div className="flex items-center justify-between p-6 pb-4">
          <div>
            <h2 className="font-heading text-lg">Route index table</h2>
            <p className="lbl mt-1">Ranked by 30-day contribution</p>
          </div>
          <input
            type="text"
            placeholder="Search route (e.g. DEL)"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="text-sm px-3 py-1.5 rounded border border-[var(--border)] bg-[var(--bg)] text-[var(--text)] placeholder:text-[var(--text-muted)] outline-none focus:border-[var(--amber)] w-48"
          />
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[900px]">
            <thead>
              <tr className="border-t border-b border-[var(--border)]">
                <SortableHeader label="ROUTE" sortKey="route" currentKey={sortKey} dir={sortDir} onClick={toggleSort} />
                <SortableHeader label="AVG FARE" sortKey="current_average_fare" currentKey={sortKey} dir={sortDir} onClick={toggleSort} align="right" />
                <SortableHeader label="INDEX" sortKey="current_index" currentKey={sortKey} dir={sortDir} onClick={toggleSort} align="right" />
                <SortableHeader label="ROUND CHANGE" sortKey="own_index_change" currentKey={sortKey} dir={sortDir} onClick={toggleSort} align="right" />
                <SortableHeader label="LEAD-TIME +%" sortKey="lead_time_increase_pct" currentKey={sortKey} dir={sortDir} onClick={toggleSort} align="right" />
                <SortableHeader label="ELASTICITY %/DAY" sortKey="elasticity_pct_per_day" currentKey={sortKey} dir={sortDir} onClick={toggleSort} align="right" />
                <SortableHeader label="CONTRIB (PP)" sortKey="contribution_pp" currentKey={sortKey} dir={sortDir} onClick={toggleSort} align="right" />
                <SortableHeader label="DGCA WEIGHT" sortKey="dgca_weight_pct" currentKey={sortKey} dir={sortDir} onClick={toggleSort} align="right" />
                <th className="px-4 py-3 lbl text-center">TREND</th>
              </tr>
            </thead>
            <tbody>
              {tableData.map((row) => (
                <tr
                  key={row.route}
                  onClick={() => router.push(`/routes/${row.route}`)}
                  className="border-b border-[var(--border)] last:border-b-0 hover:bg-[var(--bg)] cursor-pointer transition-colors"
                >
                  <td className="px-4 py-3 font-medium font-mono-num">{row.route}</td>
                  <td className="px-4 py-3 text-right font-mono-num">
                    ₹{row.current_average_fare?.toLocaleString("en-IN") ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-right font-mono-num">{row.current_index}</td>
                  <td
                    className="px-4 py-3 text-right font-mono-num"
                    style={{ color: (row.own_index_change ?? 0) >= 0 ? "var(--amber)" : "var(--teal)" }}
                  >
                    {row.own_index_change != null
                      ? `${row.own_index_change >= 0 ? "+" : ""}${row.own_index_change}`
                      : "—"}
                  </td>
                  <td className="px-4 py-3 text-right font-mono-num">
                    {row.lead_time_increase_pct != null ? `+${row.lead_time_increase_pct}%` : "—"}
                  </td>
                  <td className="px-4 py-3 text-right font-mono-num">
                    {row.elasticity_pct_per_day != null ? `${row.elasticity_pct_per_day}%` : "—"}
                  </td>
                  <td
                    className="px-4 py-3 text-right font-mono-num"
                    style={{ color: row.contribution_pp >= 0 ? "var(--amber)" : "var(--teal)" }}
                  >
                    {row.contribution_pp >= 0 ? "+" : ""}
                    {row.contribution_pp}
                  </td>
                  <td className="px-4 py-3 text-right font-mono-num">
                    {row.dgca_weight_pct != null ? `${row.dgca_weight_pct}%` : "—"}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex justify-center">
                      <Sparkline
                        values={sparklines[row.route] ?? []}
                        color={row.contribution_pp >= 0 ? "var(--amber)" : "var(--teal)"}
                      />
                    </div>
                  </td>
                </tr>
              ))}
              {tableData.length === 0 && (
                <tr>
                  <td colSpan={9} className="px-4 py-8 text-center text-[var(--text-muted)] text-sm">
                    No routes match &quot;{search}&quot;
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </AppShell>
  );
}
