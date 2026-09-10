"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from "recharts";
import AppShell, { SimpleHeader } from "@/components/AppShell";
import { Card, StatCard } from "@/components/ui";
import { API_URL } from "@/lib/api";

export default function Validation() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

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

  const header = (
    <SimpleHeader
      title="Model Validation"
      subtitle={`${summary.periods_compared}-period back-test of the computed index against a reference series`}
    />
  );

  return (
    <AppShell header={header}>
      {isProxy && (
        <div className="bp-card border-[var(--amber)] p-4 text-sm">
          <i className="bp-corner tl" aria-hidden="true" />
          <i className="bp-corner tr" aria-hidden="true" />
          <i className="bp-corner bl" aria-hidden="true" />
          <i className="bp-corner br" aria-hidden="true" />
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

      <Card>
        <h2 className="font-heading text-lg mb-6">Computed AIRIX vs. Reference Index</h2>
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
      </Card>
    </AppShell>
  );
}
