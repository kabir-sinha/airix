"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_GROUPS = [
  {
    title: "Airfare Index",
    items: [
      { label: "Overview", href: "/", match: (p) => p === "/" },
      {
        label: "Route Index",
        href: "/routes",
        match: (p) => p === "/routes" || p.startsWith("/routes/"),
      },
      { label: "Lead-Time Index", href: "/lead-time", match: (p) => p === "/lead-time" },
    ],
  },
  {
    title: "Data",
    items: [
      { label: "Data Quality", href: "/data-quality", match: (p) => p === "/data-quality" },
      { label: "Model Validation", href: "/validation", match: (p) => p === "/validation" },
    ],
  },
];

/**
 * Shared page shell: left nav sidebar + navy instrument-panel header +
 * light/dark toggle. `header` is arbitrary content rendered inside the
 * navy panel (each page controls its own header — a rich KPI strip on
 * Overview, a simple title on the rest).
 */
export default function AppShell({ header, children }) {
  const pathname = usePathname();
  const [isDark, setIsDark] = useState(false);

  useEffect(() => {
    // Reads the class the beforeInteractive theme script already applied.
    // Deliberately deferred to an effect (rather than a lazy useState
    // initializer) so the client's first render matches the server's
    // theme-less HTML and avoids a hydration mismatch.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setIsDark(document.documentElement.classList.contains("dark"));
  }, []);

  function toggleTheme() {
    const next = !isDark;
    setIsDark(next);
    document.documentElement.classList.toggle("dark", next);
    localStorage.setItem("airix-theme", next ? "dark" : "light");
  }

  return (
    <div className="min-h-screen flex bg-[var(--bg)] text-[var(--text)]">
      <aside className="w-56 shrink-0 border-r border-[var(--border)] hidden md:flex md:flex-col">
        <div className="px-5 py-5 border-b border-[var(--border)]">
          <div className="font-heading text-lg leading-none">AIRIX</div>
          <div className="lbl mt-1.5">SIH26056 · MoSPI</div>
        </div>
        <nav className="flex-1 overflow-y-auto py-3">
          {NAV_GROUPS.map((group) => (
            <div key={group.title} className="mb-2">
              <div className="px-5 pt-3 pb-1 lbl">{group.title}</div>
              {group.items.map((item) => {
                const active = item.match(pathname);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`block px-5 py-2 text-sm border-l-2 transition-colors ${
                      active
                        ? "border-[var(--amber)] text-[var(--text)] bg-[var(--bg)]"
                        : "border-transparent text-[var(--text-muted)] hover:text-[var(--text)] hover:bg-[var(--bg)]"
                    }`}
                  >
                    {item.label}
                  </Link>
                );
              })}
            </div>
          ))}
        </nav>
        <div className="px-5 py-4 border-t border-[var(--border)] lbl">SIH26056 Prototype</div>
      </aside>

      <div className="flex-1 min-w-0 flex flex-col">
        <header className="bg-[var(--panel-navy)] text-[var(--panel-text)] border-b border-[var(--panel-border)]">
          <div className="px-6 sm:px-10 py-6">
            <div className="flex items-start justify-between gap-6">
              <div className="flex-1 min-w-0">{header}</div>
              <button
                onClick={toggleTheme}
                className="shrink-0 text-xs font-medium text-[var(--panel-text-muted)] hover:text-[var(--panel-text)] transition-colors px-3 py-1.5 rounded border border-[var(--panel-border)]"
              >
                {isDark ? "Light" : "Dark"}
              </button>
            </div>
          </div>
        </header>

        <main className="flex-1 px-6 sm:px-10 py-10">
          <div className="max-w-6xl mx-auto space-y-10">{children}</div>
        </main>
      </div>
    </div>
  );
}

export function SimpleHeader({ title, subtitle, backHref = "/", backLabel = "Dashboard" }) {
  return (
    <div>
      <Link
        href={backHref}
        className="text-xs text-[var(--panel-text-muted)] hover:text-[var(--panel-text)] transition-colors"
      >
        ← {backLabel}
      </Link>
      <h1 className="font-heading text-2xl mt-3">{title}</h1>
      {subtitle && <p className="text-sm text-[var(--panel-text-muted)] mt-1">{subtitle}</p>}
    </div>
  );
}
