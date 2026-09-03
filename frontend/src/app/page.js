"use client";

import { useEffect, useState, useMemo } from "react";
import { useRouter } from "next/navigation";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  BarChart, Bar, Cell,
} from "recharts";

const API_URL = "http://127.0.0.1:8000";

export default function Home() {
  const router = useRouter();
  const [summary, setSummary] = useState(null);
  const [history, setHistory] = useState([]);
  const [contributions, setContributions] = useState([]);
  const [routes, setRoutes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isDark, setIsDark] = useState(false);
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState("contribution_pp");
  const [sortDir, setSortDir] = useState("desc");
  const [freq, setFreq] = useState("weekly");

  useEffect(() => {
    setIsDark(document.documentElement.classList.contains("dark"));
  }, []);

  function toggleTheme() {
    const next = !isDark;
    setIsDark(next);
    document.documentElement.classList.toggle("dark", next);
    localStorage.setItem("airix-theme", next ? "dark" : "light");
  }

  useEffect(() => {
    async function loadData() {
      try {
        const [summaryRes, contribRes, routesRes] = await Promise.all([
          fetch(`${API_URL}/api/summary`),
          fetch(`${API_URL}/api/contributions`),
          fetch(`${API_URL}/api/routes`),
        ]);
        setSummary(await summaryRes.json());
        setContributions(await contribRes.json());
        setRoutes(await routesRes.json());
      } catch (err) {
        setError("Could not connect to the AIRIX API. Is the backend running?");
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  useEffect(() => {
    async function loadHistory() {
      try {
        const res = await fetch(`${API_URL}/api/index/history?freq=${freq}`);
        setHistory(await res.json());
      } catch (err) {
        // Trend panel stays empty; the page-level error state already
        // covers a fully unreachable backend.
      }
    }
    loadHistory();
  }, [freq]);

  const tableData = useMemo(() => {
    const contribMap = Object.fromEntries(contributions.map((c) => [c.route, c.contribution_pp]));
    let rows = routes.map((r) => ({
      route: r.route,
      current_index: r.current_index,
      contribution_pp: contribMap[r.route] ?? 0,
    }));
    if (search.trim()) {
      const q = search.trim().toUpperCase();
      rows = rows.filter((r) => r.route.includes(q));
    }
    rows.sort((a, b) => {
      const diff = a[sortKey] - b[sortKey];
      return sortDir === "asc" ? diff : -diff;
    });
    return rows;
  }, [routes, contributions, search, sortKey, sortDir]);

  function toggleSort(key) {
    if (sortKey === key) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  }

  const goToRoute = (route) => router.push(`/routes/${route}`);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--bg)] text-[var(--text-muted)] font-mono-num text-sm">
        LOADING AIRIX...
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--bg)] text-red-500">
        {error}
      </div>
    );
  }

  const changeUp = summary.change_vs_previous > 0;
  const changeFlat = summary.change_vs_previous === 0;
  const signalColor = changeFlat ? "var(--text-muted)" : changeUp ? "var(--amber)" : "var(--teal)";

  return (
    <div className="min-h-screen bg-[var(--bg)] text-[var(--text)]">
      {/* Instrument bar — always dark chrome, like a physical panel */}
      <header className="bg-[var(--panel-navy)] text-[var(--panel-text)] border-b border-[var(--panel-border)]">
        <div className="max-w-6xl mx-auto px-6 sm:px-10 py-6">
          <div className="flex items-start justify-between flex-wrap gap-6">
            <div>
              <div className="flex items-baseline gap-3">
                <h1 className="text-2xl font-semibold tracking-tight">AIRIX</h1>
                <span className="text-[11px] text-[var(--panel-text-muted)]">SIH26056 · MoSPI</span>
              </div>
              <p className="text-sm text-[var(--panel-text-muted)] mt-1">
                Airfare Intelligence &amp; Price Index Engine
              </p>
            </div>
            <div className="flex items-center gap-4">
              <nav className="flex items-center gap-4 text-sm text-[var(--panel-text-muted)]">
                <span className="text-[var(--panel-text)] border-b border-[var(--amber)] pb-0.5">Dashboard</span>
                <a href="/data-quality" className="hover:text-[var(--panel-text)] transition-colors">
                  Data Quality
                </a>
                <a href="/validation" className="hover:text-[var(--panel-text)] transition-colors">
                  Model Validation
                </a>
              </nav>
              <button
                onClick={toggleTheme}
                className="text-xs font-medium text-[var(--panel-text-muted)] hover:text-[var(--panel-text)] transition-colors px-3 py-1.5 rounded border border-[var(--panel-border)]"
              >
                {isDark ? "Light" : "Dark"}
              </button>
            </div>
          </div>

          <div className="mt-8 flex items-end gap-10 flex-wrap">
            <div>
              <p className="text-[11px] text-[var(--panel-text-muted)] mb-1">CURRENT AIRIX</p>
              <div className="flex items-baseline gap-3">
                <span className="font-mono-num text-6xl font-semibold leading-none" style={{ color: signalColor }}>
                  {summary.current_airix}
                </span>
                <span className="font-mono-num text-sm" style={{ color: signalColor }}>
                  {changeUp ? "▲" : changeFlat ? "—" : "▼"} {Math.abs(summary.change_vs_previous)}%
                </span>
              </div>
            </div>
            <div className="flex gap-8 pb-1">
              <MiniStat label="ROUTES" value={summary.routes_tracked} />
              <MiniStat label="OBSERVATIONS" value={summary.observations} />
              <MiniStat label="DATA QUALITY" value={`${summary.data_quality_pct}%`} />
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 sm:px-10 py-10 space-y-10">
        {/* Trend panel */}
        <section className="border border-[var(--border)] rounded-lg bg-[var(--surface)] p-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-sm font-semibold">AIRIX Trend</h2>
            <div className="flex gap-1">
              {["daily", "weekly", "monthly"].map((f) => (
                <button
                  key={f}
                  onClick={() => setFreq(f)}
                  className={`text-xs px-3 py-1 rounded border transition-colors ${
                    freq === f
                      ? "border-[var(--amber)] text-[var(--amber)]"
                      : "border-[var(--border)] text-[var(--text-muted)] hover:text-[var(--text)]"
                  }`}
                >
                  {f[0].toUpperCase() + f.slice(1)}
                </button>
              ))}
            </div>
          </div>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={history}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="date" stroke="var(--text-muted)" fontSize={12} />
              <YAxis domain={["dataMin - 3", "dataMax + 3"]} stroke="var(--text-muted)" fontSize={12} />
              <Tooltip
                contentStyle={{
                  background: "var(--surface)",
                  border: "1px solid var(--border)",
                  fontSize: 13,
                }}
                formatter={(value) => [value, "AIRIX"]}
              />
              <Line type="monotone" dataKey="airix" stroke="var(--amber)" strokeWidth={2} dot={{ r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </section>

        <Heatmap apiUrl={API_URL} />

        {/* Contributions panel */}
        <section className="border border-[var(--border)] rounded-lg bg-[var(--surface)] p-6">
          <div className="flex items-center justify-between mb-1">
            <h2 className="text-sm font-semibold text-[var(--text)]">
              Route Contributions to Latest Movement
            </h2>
          </div>
          <div className="flex items-center gap-4 mb-4">
            <p className="text-xs text-[var(--text-muted)]">Click a bar to open the route</p>
            <span className="flex items-center gap-1.5 text-xs text-[var(--text-muted)]">
              <span className="w-2.5 h-2.5 rounded-sm inline-block" style={{ background: "var(--amber)" }} />
              Pushing AIRIX up
            </span>
            <span className="flex items-center gap-1.5 text-xs text-[var(--text-muted)]">
              <span className="w-2.5 h-2.5 rounded-sm inline-block" style={{ background: "var(--teal)" }} />
              Pulling AIRIX down
            </span>
          </div>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={contributions} layout="vertical" margin={{ left: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis type="number" stroke="var(--text-muted)" fontSize={12} />
              <YAxis type="category" dataKey="route" width={80} stroke="var(--text-muted)" fontSize={12} />
              <Tooltip
                contentStyle={{
                  background: "var(--surface)",
                  border: "1px solid var(--border)",
                  fontSize: 13,
                }}
                formatter={(value) => [`${value >= 0 ? "+" : ""}${value} pp`, "Contribution"]}
              />
              <Bar dataKey="contribution_pp" radius={[0, 3, 3, 0]} onClick={(d) => goToRoute(d.route)} cursor="pointer">
                {contributions.map((entry, i) => (
                  <Cell key={i} fill={entry.contribution_pp >= 0 ? "var(--amber)" : "var(--teal)"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </section>

        {/* Sortable / searchable route table */}
        <section className="border border-[var(--border)] rounded-lg bg-[var(--surface)] overflow-hidden">
          <div className="flex items-center justify-between p-6 pb-4">
            <h2 className="text-sm font-semibold">All Routes</h2>
            <input
              type="text"
              placeholder="Search route (e.g. DEL)"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="text-sm px-3 py-1.5 rounded border border-[var(--border)] bg-[var(--bg)] text-[var(--text)] placeholder:text-[var(--text-muted)] outline-none focus:border-[var(--amber)] w-48"
            />
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-t border-b border-[var(--border)] text-[var(--text-muted)] text-xs">
                <SortableHeader label="ROUTE" sortKey="route" currentKey={sortKey} dir={sortDir} onClick={toggleSort} />
                <SortableHeader label="INDEX" sortKey="current_index" currentKey={sortKey} dir={sortDir} onClick={toggleSort} align="right" />
                <SortableHeader label="CONTRIBUTION (PP)" sortKey="contribution_pp" currentKey={sortKey} dir={sortDir} onClick={toggleSort} align="right" />
              </tr>
            </thead>
            <tbody>
              {tableData.map((row) => (
                <tr
                  key={row.route}
                  onClick={() => goToRoute(row.route)}
                  className="border-b border-[var(--border)] last:border-b-0 hover:bg-[var(--bg)] cursor-pointer transition-colors"
                >
                  <td className="px-6 py-3 font-medium">{row.route}</td>
                  <td className="px-6 py-3 text-right font-mono-num">{row.current_index}</td>
                  <td
                    className="px-6 py-3 text-right font-mono-num"
                    style={{ color: row.contribution_pp >= 0 ? "var(--amber)" : "var(--teal)" }}
                  >
                    {row.contribution_pp >= 0 ? "+" : ""}
                    {row.contribution_pp}
                  </td>
                </tr>
              ))}
              {tableData.length === 0 && (
                <tr>
                  <td colSpan={3} className="px-6 py-8 text-center text-[var(--text-muted)] text-sm">
                    No routes match "{search}"
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </section>
      </main>
    </div>
  );
}

function MiniStat({ label, value }) {
  return (
    <div>
      <p className="text-[11px] text-[var(--panel-text-muted)]">{label}</p>
      <p className="font-mono-num text-lg font-medium">{value}</p>
    </div>
  );
}

function SortableHeader({ label, sortKey, currentKey, dir, onClick, align = "left" }) {
  const active = currentKey === sortKey;
  return (
    <th
      onClick={() => onClick(sortKey)}
      className={`px-6 py-3 font-medium cursor-pointer select-none hover:text-[var(--text)] transition-colors ${
        align === "right" ? "text-right" : "text-left"
      }`}
    >
      {label} {active && (dir === "asc" ? "▲" : "▼")}
    </th>
  );
}

function Heatmap({ apiUrl }) {
  const [data, setData] = useState(null);

  useEffect(() => {
    fetch(`${apiUrl}/api/heatmap?freq=weekly`)
      .then((res) => res.json())
      .then(setData)
      .catch(() => setData(null));
  }, [apiUrl]);

  if (!data || data.routes.length === 0) return null;

  const allValues = data.matrix.flat().filter((v) => v !== null);
  const min = Math.min(...allValues);
  const max = Math.max(...allValues);

  function colorFor(value) {
    if (value === null) return "var(--border)";
    const t = max === min ? 0.5 : (value - min) / (max - min);
    const teal = [20, 184, 166];
    const amber = [217, 119, 6];
    const rgb = teal.map((c, i) => Math.round(c + (amber[i] - c) * t));
    return `rgb(${rgb.join(",")})`;
  }

  return (
    <section className="border border-[var(--border)] rounded-lg bg-[var(--surface)] p-6 overflow-x-auto">
      <h2 className="text-sm font-semibold mb-6">Sector-Wise Fare Index Heatmap (Weekly)</h2>
      <table className="text-xs border-separate" style={{ borderSpacing: 2 }}>
        <thead>
          <tr>
            <th className="text-left pr-3 pb-1 text-[var(--text-muted)] font-medium">ROUTE</th>
            {data.periods.map((p) => (
              <th key={p} className="px-2 pb-1 text-[var(--text-muted)] font-medium font-mono-num">{p}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.routes.map((route, ri) => (
            <tr key={route}>
              <td className="pr-3 py-1 font-medium">{route}</td>
              {data.matrix[ri].map((value, ci) => (
                <td
                  key={ci}
                  title={value === null ? "no data" : `${route} — ${data.periods[ci]}: ${value}`}
                  className="w-14 h-8 text-center font-mono-num rounded"
                  style={{ background: colorFor(value), color: "#fff" }}
                >
                  {value === null ? "" : value}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}