"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AppShell, { SimpleHeader } from "@/components/AppShell";
import { Card, StatCard } from "@/components/ui";
import { API_URL } from "@/lib/api";

export default function DataQuality() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

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

  const header = (
    <SimpleHeader
      title="Data Quality"
      subtitle="Audit trail — every observation is tracked, never silently dropped"
    />
  );

  return (
    <AppShell header={header}>
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
        <Card>
          <h2 className="font-heading text-lg mb-4">Why observations were flagged or excluded</h2>
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
        </Card>
      )}

      <Card className="!p-0 overflow-hidden">
        <h2 className="font-heading text-lg p-6 pb-4">Quality by Route</h2>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-t border-b border-[var(--border)]">
              <th className="px-4 py-3 lbl text-left">ROUTE</th>
              <th className="px-4 py-3 lbl text-right" style={{ color: statusColor.Valid }}>VALID</th>
              <th className="px-4 py-3 lbl text-right" style={{ color: statusColor.Flagged }}>FLAGGED</th>
              <th className="px-4 py-3 lbl text-right" style={{ color: statusColor.Excluded }}>EXCLUDED</th>
            </tr>
          </thead>
          <tbody>
            {routes.map((route) => (
              <tr key={route} className="border-b border-[var(--border)] last:border-b-0">
                <td className="px-4 py-3 font-medium">{route}</td>
                <td className="px-4 py-3 text-right font-mono-num">{data.by_route[route].Valid || 0}</td>
                <td className="px-4 py-3 text-right font-mono-num">{data.by_route[route].Flagged || 0}</td>
                <td className="px-4 py-3 text-right font-mono-num">{data.by_route[route].Excluded || 0}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </AppShell>
  );
}
