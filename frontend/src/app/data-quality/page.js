"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

const API_URL = "http://127.0.0.1:8000";

export default function DataQuality() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isDark, setIsDark] = useState(false);

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
        const res = await fetch(`${API_URL}/api/data-quality`);
        if (!res.ok) throw new Error("Could not load data quality report");
        setData(await res.json());
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--bg)] text-[var(--text-muted)] font-mono-num text-sm">
        LOADING DATA QUALITY REPORT...
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--bg)] flex-col gap-4">
        <p className="text-red-500">{error || "No data"}</p>
        <Link href="/" className="text-[var(--amber)] underline text-sm">Back to dashboard</Link>
      </div>
    );
  }

  const statusColor = { Valid: "var(--teal)", Flagged: "var(--amber)", Excluded: "#ef4444" };
  const routes = Object.keys(data.by_route).sort();

  return (
    <div className="min-h-screen bg-[var(--bg)] text-[var(--text)]">
      <header className="bg-[var(--panel-navy)] text-[var(--panel-text)] border-b border-[var(--panel-border)]">
        <div className="max-w-4xl mx-auto px-6 sm:px-10 py-6">
          <div className="flex items-center justify-between mb-4">
            <Link href="/" className="text-xs text-[var(--panel-text-muted)] hover:text-[var(--panel-text)] transition-colors">
              ← Dashboard
            </Link>
            <button
              onClick={toggleTheme}
              className="text-xs font-medium text-[var(--panel-text-muted)] hover:text-[var(--panel-text)] transition-colors px-3 py-1.5 rounded border border-[var(--panel-border)]"
            >
              {isDark ? "Light" : "Dark"}
            </button>
          </div>
          <h1 className="text-2xl font-semibold tracking-tight">Data Quality</h1>
          <p className="text-sm text-[var(--panel-text-muted)] mt-1">
            Audit trail — every observation is tracked, never silently dropped
          </p>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-6 sm:px-10 py-10 space-y-8">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <StatCard label="Total Observations" value={data.total_observations} />
          <StatCard label="Overall Quality" value={`${data.quality_pct}%`} color="var(--teal)" />
          {["Valid", "Flagged", "Excluded"].map((status) => (
            <StatCard
              key={status}
              label={status}
              value={data.by_status[status] || 0}
              color={statusColor[status]}
            />
          ))}
        </div>

        {Object.keys(data.by_reason).length > 0 && (
          <section className="border border-[var(--border)] rounded-lg bg-[var(--surface)] p-6">
            <h2 className="text-sm font-semibold mb-4">Why observations were flagged or excluded</h2>
            <div className="space-y-2">
              {Object.entries(data.by_reason)
                .sort((a, b) => b[1] - a[1])
                .map(([reason, count]) => (
                  <div key={reason} className="flex items-center justify-between text-sm py-2 border-b border-[var(--border)] last:border-b-0">
                    <span>{reason}</span>
                    <span className="font-mono-num text-[var(--text-muted)]">{count}</span>
                  </div>
                ))}
            </div>
          </section>
        )}

        <section className="border border-[var(--border)] rounded-lg bg-[var(--surface)] overflow-hidden">
          <h2 className="text-sm font-semibold p-6 pb-4">Quality by Route</h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-t border-b border-[var(--border)] text-[var(--text-muted)] text-xs">
                <th className="px-6 py-3 text-left font-medium">ROUTE</th>
                <th className="px-6 py-3 text-right font-medium" style={{ color: statusColor.Valid }}>VALID</th>
                <th className="px-6 py-3 text-right font-medium" style={{ color: statusColor.Flagged }}>FLAGGED</th>
                <th className="px-6 py-3 text-right font-medium" style={{ color: statusColor.Excluded }}>EXCLUDED</th>
              </tr>
            </thead>
            <tbody>
              {routes.map((route) => (
                <tr key={route} className="border-b border-[var(--border)] last:border-b-0">
                  <td className="px-6 py-3 font-medium">{route}</td>
                  <td className="px-6 py-3 text-right font-mono-num">{data.by_route[route].Valid || 0}</td>
                  <td className="px-6 py-3 text-right font-mono-num">{data.by_route[route].Flagged || 0}</td>
                  <td className="px-6 py-3 text-right font-mono-num">{data.by_route[route].Excluded || 0}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </main>
    </div>
  );
}

function StatCard({ label, value, color }) {
  return (
    <div className="border border-[var(--border)] rounded-lg bg-[var(--surface)] p-5">
      <p className="text-xs text-[var(--text-muted)] mb-1">{label}</p>
      <p className="font-mono-num text-2xl font-semibold" style={{ color: color || "var(--text)" }}>
        {value}
      </p>
    </div>
  );
}