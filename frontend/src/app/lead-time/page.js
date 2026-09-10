"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import AppShell, { SimpleHeader } from "@/components/AppShell";
import { Card, SortableHeader } from "@/components/ui";
import { fetchAllRouteDetails } from "@/lib/api";

const HORIZONS = ["T+45", "T+30", "T+15", "T+7", "T+1"];

export default function LeadTimeIndex() {
  const router = useRouter();
  const [routeDetails, setRouteDetails] = useState(null);
  const [error, setError] = useState(null);
  const [sortKey, setSortKey] = useState("lead_time_increase_pct");
  const [sortDir, setSortDir] = useState("desc");

  useEffect(() => {
    async function load() {
      try {
        setRouteDetails(await fetchAllRouteDetails());
      } catch (err) {
        setError("Could not load lead-time data. Is the backend running?");
      }
    }
    load();
  }, []);

  const national = useMemo(() => {
    if (!routeDetails || routeDetails.length === 0) return null;
    const curve = HORIZONS.map((h) => {
      const values = routeDetails
        .map((d) => d.fare_by_horizon?.[h])
        .filter((v) => v != null && v > 0);
      const mean = values.length ? values.reduce((a, b) => a + b, 0) / values.length : 0;
      return { horizon: h, fare: Math.round(mean) };
    });
    const meanElasticity =
      routeDetails.reduce((sum, d) => sum + (d.elasticity_pct_per_day ?? 0), 0) / routeDetails.length;
    const meanIncrease =
      routeDetails.reduce((sum, d) => sum + (d.lead_time_increase_pct ?? 0), 0) / routeDetails.length;
    return { curve, meanElasticity: meanElasticity.toFixed(2), meanIncrease: meanIncrease.toFixed(1) };
  }, [routeDetails]);

  const tableData = useMemo(() => {
    if (!routeDetails) return [];
    return [...routeDetails].sort((a, b) => {
      const av = a[sortKey] ?? -Infinity;
      const bv = b[sortKey] ?? -Infinity;
      const diff = av - bv;
      return sortDir === "asc" ? diff : -diff;
    });
  }, [routeDetails, sortKey, sortDir]);

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

  if (!routeDetails || !national) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--bg)] text-[var(--text-muted)] font-mono-num text-sm">
        LOADING LEAD-TIME INDEX...
      </div>
    );
  }

  const maxIncrease = Math.max(...routeDetails.map((d) => d.lead_time_increase_pct ?? 0), 0.01);

  const header = (
    <SimpleHeader
      title="Lead-Time Index"
      subtitle="Fare response to the advance-purchase window, from identical itineraries sampled at five lead times"
    />
  );

  return (
    <AppShell header={header}>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-2">
          <h2 className="font-heading text-lg mb-1">Fare vs advance-purchase window</h2>
          <p className="lbl mb-6">National mean fare across {routeDetails.length} tracked routes</p>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={national.curve}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="horizon" stroke="var(--text-muted)" fontSize={12} />
              <YAxis stroke="var(--text-muted)" fontSize={12} />
              <Tooltip
                formatter={(value) => `₹${value.toLocaleString("en-IN")}`}
                contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", fontSize: 13 }}
              />
              <Line type="monotone" dataKey="fare" stroke="var(--amber)" strokeWidth={2} dot={{ r: 4 }} />
            </LineChart>
          </ResponsiveContainer>
        </Card>

        <Card>
          <h2 className="font-heading text-lg mb-4">Window statistics</h2>
          <div className="space-y-3">
            <div className="flex items-baseline justify-between border-b border-[var(--border)] pb-3">
              <span className="lbl">T+45 mean fare</span>
              <span className="font-mono-num text-lg font-medium">₹{national.curve[0].fare.toLocaleString("en-IN")}</span>
            </div>
            <div className="flex items-baseline justify-between border-b border-[var(--border)] pb-3">
              <span className="lbl">T+1 mean fare</span>
              <span className="font-mono-num text-lg font-medium">₹{national.curve[4].fare.toLocaleString("en-IN")}</span>
            </div>
            <div className="flex items-baseline justify-between border-b border-[var(--border)] pb-3">
              <span className="lbl">Avg full-window increase</span>
              <span className="font-mono-num text-lg font-medium" style={{ color: "var(--amber)" }}>+{national.meanIncrease}%</span>
            </div>
            <div className="flex items-baseline justify-between">
              <span className="lbl">Avg elasticity</span>
              <span className="font-mono-num text-lg font-medium" style={{ color: "var(--teal)" }}>{national.meanElasticity}%/day</span>
            </div>
          </div>
          <p className="text-xs text-[var(--text-muted)] mt-4 leading-relaxed">
            Elasticity and increase figures are the average of each route&apos;s own T+45 → T+1 comparison —
            not the average curve above, which can differ slightly due to route mix.
          </p>
        </Card>
      </div>

      <Card className="!p-0 overflow-hidden">
        <div className="p-6 pb-4">
          <h2 className="font-heading text-lg">Fare by route and lead time</h2>
          <p className="lbl mt-1">All tracked routes · click a row to open route analytics</p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[820px]">
            <thead>
              <tr className="border-t border-b border-[var(--border)]">
                <SortableHeader label="ROUTE" sortKey="route" currentKey={sortKey} dir={sortDir} onClick={toggleSort} />
                {HORIZONS.map((h) => (
                  <th key={h} className="px-4 py-3 lbl text-right">{h}</th>
                ))}
                <SortableHeader label="T+45 → T+1" sortKey="lead_time_increase_pct" currentKey={sortKey} dir={sortDir} onClick={toggleSort} align="right" />
                <th className="px-4 py-3 lbl text-center w-40">ELASTICITY</th>
              </tr>
            </thead>
            <tbody>
              {tableData.map((d) => (
                <tr
                  key={d.route}
                  onClick={() => router.push(`/routes/${d.route}`)}
                  className="border-b border-[var(--border)] last:border-b-0 hover:bg-[var(--bg)] cursor-pointer transition-colors"
                >
                  <td className="px-4 py-3 font-medium font-mono-num">{d.route}</td>
                  {HORIZONS.map((h) => (
                    <td key={h} className="px-4 py-3 text-right font-mono-num">
                      ₹{d.fare_by_horizon?.[h]?.toLocaleString("en-IN") ?? "—"}
                    </td>
                  ))}
                  <td className="px-4 py-3 text-right font-mono-num font-medium" style={{ color: "var(--amber)" }}>
                    +{d.lead_time_increase_pct}%
                  </td>
                  <td className="px-4 py-3">
                    <div className="h-2 rounded-sm bg-[var(--border)] overflow-hidden">
                      <div
                        className="h-2 rounded-sm"
                        style={{
                          width: `${((d.lead_time_increase_pct ?? 0) / maxIncrease) * 100}%`,
                          background: "var(--amber)",
                        }}
                      />
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </AppShell>
  );
}
