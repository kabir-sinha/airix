/**
 * Shared "blueprint" presentational primitives used across every page —
 * kept dumb (no data fetching) so pages stay in control of loading state.
 */

export function Card({ children, className = "" }) {
  return (
    <section className={`bp-card p-6 ${className}`}>
      <i className="bp-corner tl" aria-hidden="true" />
      <i className="bp-corner tr" aria-hidden="true" />
      <i className="bp-corner bl" aria-hidden="true" />
      <i className="bp-corner br" aria-hidden="true" />
      {children}
    </section>
  );
}

export function StatCard({ label, value, note, color }) {
  return (
    <div className="bp-card p-5">
      <i className="bp-corner tl" aria-hidden="true" />
      <i className="bp-corner tr" aria-hidden="true" />
      <i className="bp-corner bl" aria-hidden="true" />
      <i className="bp-corner br" aria-hidden="true" />
      <p className="lbl mb-2">{label}</p>
      <p className="font-mono-num text-2xl font-semibold" style={{ color: color || "var(--text)" }}>
        {value}
      </p>
      {note && <p className="text-xs text-[var(--text-muted)] mt-1">{note}</p>}
    </div>
  );
}

export function SortableHeader({ label, sortKey, currentKey, dir, onClick, align = "left" }) {
  const active = currentKey === sortKey;
  return (
    <th
      onClick={() => onClick(sortKey)}
      className={`px-4 py-3 lbl cursor-pointer select-none hover:text-[var(--text)] transition-colors whitespace-nowrap ${
        align === "right" ? "text-right" : "text-left"
      }`}
    >
      {label} {active && (dir === "asc" ? "▲" : "▼")}
    </th>
  );
}

/** Tiny real-data sparkline — no library, just an SVG polyline. */
export function Sparkline({ values, color = "var(--amber)", width = 96, height = 26 }) {
  const clean = values.filter((v) => v !== null && v !== undefined);
  if (clean.length < 2) return <span className="text-xs text-[var(--text-muted)]">—</span>;
  const min = Math.min(...clean);
  const max = Math.max(...clean);
  const span = max - min || 1;
  const points = values
    .map((v, i) => {
      if (v === null || v === undefined) return null;
      const x = (i / (values.length - 1)) * width;
      const y = height - ((v - min) / span) * height;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .filter(Boolean)
    .join(" ");
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} className="block">
      <polyline points={points} fill="none" stroke={color} strokeWidth="1.6" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}
