import { useEffect, useState } from "react";
import { Link, NavLink } from "react-router-dom";
import { Compass, Eye, History, Scale } from "lucide-react";
import type { ReactNode } from "react";
import { listAlerts, markAlertsSeen } from "../lib/api";
import { BRAND } from "../lib/brand";

const links = [
  { to: "/", label: "Council", icon: Compass, end: true },
  { to: "/scorecard", label: "Scorecard", icon: Scale, end: false },
  { to: "/watch", label: "Watch", icon: Eye, end: false },
  { to: "/history", label: "Archive", icon: History, end: false },
];

export default function Shell({ children }: { children: ReactNode }) {
  const [alerts, setAlerts] = useState<{ id: string; ticker: string; report_id: string; message: string; seen: boolean }[]>([]);

  useEffect(() => {
    let stop = false;
    const pull = () => {
      listAlerts()
        .then((items) => {
          if (stop) return;
          const fresh = items.filter((item) => !item.seen);
          setAlerts(fresh);
          if (!("Notification" in window) || Notification.permission !== "granted") return;
          for (const item of fresh) {
            const key = `aurelia-alert-${item.id}`;
            if (sessionStorage.getItem(key)) continue;
            sessionStorage.setItem(key, "1");
            new Notification(`${item.ticker} changed`, { body: item.message });
          }
        })
        .catch(() => undefined);
    };
    pull();
    const timer = window.setInterval(pull, 60_000);
    return () => {
      stop = true;
      window.clearInterval(timer);
    };
  }, []);

  return (
    <div className="grid-bg min-h-screen text-mist">
      <header className="sticky top-4 z-30 mx-4">
        <div className="glass mx-auto flex h-16 max-w-7xl items-center justify-between gap-3 rounded-2xl px-3 sm:px-5">
          <NavLink to="/" className="group flex min-w-0 items-center gap-3">
            <span className="relative flex h-9 w-9 shrink-0 items-center justify-center overflow-hidden rounded-xl bg-cta text-foam shadow-glow">
              <span className="font-sans text-sm font-semibold leading-none">A</span>
            </span>
            <span className="min-w-0 leading-tight">
              <span className="block font-sans text-lg font-semibold tracking-tight">{BRAND.name}</span>
              <span className="hidden text-[10px] font-medium uppercase tracking-[0.22em] text-gold/80 sm:block">
                {BRAND.desk}
              </span>
            </span>
          </NavLink>
          <nav className="flex shrink-0 items-center gap-1">
            {links.map((l) => (
              <NavLink
                key={l.to}
                to={l.to}
                end={l.end}
                className={({ isActive }) =>
                  `flex cursor-pointer items-center gap-2 rounded-xl px-3 py-2 text-sm transition-colors duration-200 ${
                    isActive ? "bg-cta/15 text-gold" : "text-mute hover:bg-black/[0.04] hover:text-mist"
                  }`
                }
              >
                <l.icon className="h-4 w-4" />
                <span className="hidden sm:inline">{l.label}</span>
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main className="relative mx-auto max-w-7xl px-4 pb-16 pt-28 sm:px-6 lg:px-8">
        {alerts.length > 0 && (
          <div className="mb-6 rounded-2xl border border-line bg-foam px-4 py-3 text-sm text-mist">
            {alerts.slice(0, 3).map((item) => (
              <p key={item.id}>
                <Link to={`/archive/${item.report_id}`} className="font-medium text-gold">
                  {item.ticker}
                </Link>{" "}
                <span className="text-mute">{item.message}</span>
              </p>
            ))}
            <button
              type="button"
              onClick={() => markAlertsSeen().then(() => setAlerts([]))}
              className="mt-2 cursor-pointer text-xs text-mute hover:text-mist"
            >
              Dismiss
            </button>
          </div>
        )}
        {children}
      </main>
    </div>
  );
}
