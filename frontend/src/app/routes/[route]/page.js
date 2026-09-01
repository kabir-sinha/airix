"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";

const API_URL = "http://127.0.0.1:8000";

export default function RouteDetail() {
  const params = useParams();
  const route = params.route;

  const [detail, setDetail] = useState(null);
  const [showExplain, setShowExplain] = useState(false);
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
        const res = await fetch(`${API_URL}/api/routes/${route}`);
        if (!res.ok) throw new Error("Route not found");
        setDetail(await res.json());
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, [route]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--bg)] text-[var(--text-muted)] font-mono-num text-sm">
        LOADING ROUTE...
      </div>
    );
  }

  if (error || !detail) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--bg)] flex-col gap-4">
        <p className="text-red-500">{error || "Route not found"}</p>
        <Link href="/" className="text-[var(--amber)] underline text-sm">Back to dashboard</Link>
      </div>
    );
  }

  const chartData = ["T+45", "T+30", "T+15", "T+7", "T+1"].map((h) => ({
    horizon: h,
    fare: detail.fare_by_horizon[h],
  }));

  const contribUp = detail.contribution_pp >= 0;
  const contribColor = contribUp ? "var(--amber)" : "var(--teal)";
  const ownChangeUp = (detail.own_index_change ?? 0) >= 0;

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
          <h1 className="text-3xl font-semibold tracking-tight font-mono-num">{detail.route}</h1>
          <p className="text-sm text-[var(--panel-text-muted)] mt-1">Route detail &amp; lead-time analysis</p>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-6 sm:px-10 py-10 space-y-8">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <StatCard label="Current Route Index" value={detail.current_index} />
          <StatCard label="Current Average Fare" value={`₹${detail.current_average_fare.toLocaleString("en-IN")}`} />
          <StatCard label="Lead-Time Increase" value={`+${detail.lead_time_increase_pct}%`} color="var(--amber)" />
        </div>

        <section className="border border-[var(--border)] rounded-lg bg-[var(--surface)] p-6">
          <h2 className="text-sm font-semibold mb-6">Fare by Booking Horizon (T+45 → T+1)</h2>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="horizon" stroke="var(--text-muted)" fontSize={12} />
              <YAxis stroke="var(--text-muted)" fontSize={12} />
              <Tooltip
                formatter={(value) => `₹${value.toLocaleString("en-IN")}`}
                contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", fontSize: 13 }}
              />
              <Line type="monotone" dataKey="fare" stroke="var(--amber)" strokeWidth={2} dot={{ r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </section>

        <section className="border border-[var(--border)] rounded-lg bg-[var(--surface)] p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold">Explain Movement</h2>
            <button
              onClick={() => setShowExplain(!showExplain)}
              className="text-xs font-medium px-4 py-2 rounded border border-[var(--border)] hover:border-[var(--amber)] transition-colors"
            >
              {showExplain ? "Hide" : "Explain Movement"}
            </button>
          </div>

          {showExplain && (
            <>
              <ul className="space-y-3 text-sm leading-relaxed">
                <li className="flex gap-3">
                  <span className="font-mono-num" style={{ color: ownChangeUp ? "var(--amber)" : "var(--teal)" }}>
                    {detail.own_index_change != null
                      ? `${ownChangeUp ? "+" : ""}${detail.own_index_change}`
                      : "—"}
                  </span>
                  <span>
                    points — this route's own index moved from the previous collection round to{" "}
                    <strong className="font-mono-num">{detail.current_index}</strong> this round.
                  </span>
                </li>
                <li className="flex gap-3">
                  <span className="font-mono-num" style={{ color: contribColor }}>
                    {contribUp ? "+" : ""}
                    {detail.contribution_pp}
                  </span>
                  <span>
                    percentage points contributed to the overall AIRIX movement — scaled by this route's real{" "}
                    <strong className="font-mono-num">{detail.dgca_weight_pct}%</strong> share of DGCA-reported
                    domestic passenger traffic.
                  </span>
                </li>
                <li className="flex gap-3">
                  <span className="font-mono-num text-[var(--text-muted)]">
                    #{detail.contribution_rank}/{detail.total_routes}
                  </span>
                  <span>
                    ranked driver of AIRIX movement this round — {detail.contribution_rank === 1
                      ? "the single largest mover, positive or negative, of all tracked routes."
                      : `out of ${detail.total_routes} tracked routes, ordered by contribution size.`}
                  </span>
                </li>
                <li className="flex gap-3">
                  <span className="font-mono-num" style={{ color: "var(--amber)" }}>
                    +{detail.lead_time_increase_pct}%
                  </span>
                  <span>
                    lead-time increase — fares on this route rose this much between the T+45 and T+1 booking
                    windows, independent of the calendar-time AIRIX trend above.
                  </span>
                </li>
              </ul>

              <div className="mt-5 pt-4 border-t border-[var(--border)] text-sm">
                <span className="text-[var(--text-muted)]">Summary — </span>
                <span>
                  <strong className="font-mono-num">{detail.route}</strong> was the{" "}
                  <strong>
                    {detail.contribution_rank === 1
                      ? "#1 driver"
                      : `#${detail.contribution_rank} of ${detail.total_routes} drivers`}
                  </strong>{" "}
                  of this round's AIRIX movement, {contribUp ? "pushing it up" : "pulling it down"} by{" "}
                  <strong className="font-mono-num" style={{ color: contribColor }}>
                    {Math.abs(detail.contribution_pp)}pp
                  </strong>
                  , and booking near departure costs{" "}
                  <strong className="font-mono-num">{detail.lead_time_increase_pct}%</strong> more than
                  booking 45 days out.
                </span>
              </div>
            </>
          )}
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