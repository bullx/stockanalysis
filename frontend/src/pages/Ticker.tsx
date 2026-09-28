import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getTickerHistory } from "../lib/api";
import { formatTime } from "../lib/format";
import type { HorizonScore, ScoredCall } from "../lib/types";

function pct(value: number | null | undefined) {
  if (value == null || Number.isNaN(value)) return "—";
  const points = value * 100;
  return `${points >= 0 ? "+" : ""}${points.toFixed(1)}%`;
}

function horizonLine(row: HorizonScore) {
  if (row.status === "not_due") return `${row.horizon} not due`;
  if (row.status !== "scored") return `${row.horizon} ${row.status.replace(/_/g, " ")}`;
  const inside = row.stayed_inside == null ? "" : row.stayed_inside ? " · inside bear–bull" : " · left the bear–bull range";
  return `${row.horizon} ${pct(row.stock_return)} · vs SPY ${pct(row.excess_spy)} · vs sector ${pct(row.excess_sector)}${inside}`;
}

export default function Ticker() {
  const { ticker = "" } = useParams();
  const [calls, setCalls] = useState<ScoredCall[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getTickerHistory(ticker)
      .then((data) => setCalls(data.calls))
      .catch(() => setError("Could not load this name."));
  }, [ticker]);

  const ordered = [...(calls || [])].sort((a, b) => String(a.generated_at).localeCompare(String(b.generated_at)));

  return (
    <div className="space-y-8">
      <header>
        <p className="text-[11px] uppercase tracking-[0.28em] text-gold">One name</p>
        <h1 className="mt-2 font-sans text-5xl font-semibold tracking-tight">{ticker.toUpperCase()}</h1>
        <p className="mt-3 max-w-2xl text-sm text-mute">
          Every brief stays on the record. A later brief supersedes the earlier one and does not erase it.
        </p>
      </header>
      {error && <p className="text-sm text-stop">{error}</p>}
      {calls === null && !error && <p className="text-sm text-mute">Loading briefs…</p>}
      {calls?.length === 0 && <p className="glass px-5 py-10 text-sm text-mute">No saved brief for this ticker.</p>}
      <div className="space-y-3">
        {ordered.map((call, index) => {
          const previous = ordered[index - 1];
          const changed = previous && previous.verdict !== call.verdict;
          return (
            <article key={call.id} className="glass space-y-3 rounded-2xl p-5">
              <div className="flex flex-wrap items-center gap-3">
                <Link to={`/archive/${call.id}`} className="font-medium text-mist hover:text-gold">
                  {call.title || call.verdict}
                </Link>
                <span className="font-mono text-xs text-gold">{call.verdict}</span>
                {call.kind === "update" && <span className="text-[10px] uppercase tracking-wider text-mute">Delta note</span>}
                {call.superseded_by && <span className="text-[10px] uppercase tracking-wider text-mute">Superseded</span>}
                <span className="ml-auto text-xs text-mute">{formatTime(call.generated_at)}</span>
              </div>
              {changed && (
                <p className="text-sm text-mute">
                  Call changed from {previous.verdict} to {call.verdict}.
                </p>
              )}
              {call.update_note && <p className="text-sm leading-relaxed text-mute">{call.update_note}</p>}
              <ul className="space-y-1 font-mono text-xs text-mute">
                {call.horizons.map((row) => (
                  <li key={row.horizon}>{horizonLine(row)}</li>
                ))}
              </ul>
            </article>
          );
        })}
      </div>
    </div>
  );
}
