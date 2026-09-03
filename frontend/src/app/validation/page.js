"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from "recharts";

const API_URL = "http://127.0.0.1:8000";

export default function Validation() {
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
        const res = await fetch(`${API_URL}/api/backtest`);
        if (!res.ok) throw new Error("No backtest results found. Run backtest_index.py first.");
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
        LOADING BACKTEST...
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

  const { summary, series } = data;
  const isProxy = summary.data_source.includes("synthetic");

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
          <h1 className="text-2xl font-semibold tracking-tight">Model Validation</h1>
          <p className="text-sm text-[var(--panel-text-muted)] mt-1">
            {summary.periods_compared}-period back-test of the computed index against a reference series
          </p>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-6 sm:px-10 py-10 space-y-8">
        {isProxy && (
          <div className="border border-[var(--amber)] rounded-lg bg-[var(--surface)] p-4 text-sm">
            <strong>Synthetic proxy backtest.</strong> No real DGCA monthly average-fare
            dataset is wired in yet, so this validates AIRIX against the known
            ground-truth index used to generate the synthetic data, not real
            market data. Run <code>backtest_index.py --reference &lt;dgca_file.csv&gt; --label real_dgca</code> once
            a real dataset is available to replace this.
          </div>
        )}

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <StatCard label="Periods Compared" value={summary.periods_compared} />
          <StatCard label="MAE" value={summary.mae} />
          <StatCard label="RMSE" value={summary.rmse} />
          <StatCard label="MAPE" value={`${summary.mape_pct}%`} color="var(--amber)" />
        </div>

        <section className="border border-[var(--border)] rounded-lg bg-[var(--surface)] p-6">
          <h2 className="text-sm font-semibold mb-6">Computed AIRIX vs. Reference Index</h2>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={series}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="collection_round" stroke="var(--text-muted)" fontSize={12} />
              <YAxis stroke="var(--text-muted)" fontSize={12} />
              <Tooltip
                contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", fontSize: 13 }}
              />
              <Legend />
              <Line type="monotone" dataKey="computed_airix" name="Computed AIRIX" stroke="var(--amber)" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="reference_airix" name="Reference" stroke="var(--teal)" strokeWidth={2} strokeDasharray="4 4" dot={false} />
            </LineChart>
          </ResponsiveContainer>
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
