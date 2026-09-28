import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getScorecard, type ScoreSummary } from "../lib/api";
import type { ScoredCall } from "../lib/types";

function pct(value: number | null | undefined) {
  if (value == null || Number.isNaN(value)) return "—";
  const points = value * 100;
  return `${points >= 0 ? "+" : ""}${points.toFixed(1)}%`;
}

export default function Scorecard() {
  const [summary, setSummary] = useState<ScoreSummary | null>(null);
  const [calls, setCalls] = useState<ScoredCall[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    getScorecard()
      .then((data) => {
        setSummary(data.summary);
        setCalls(data.calls);
      })
      .catch(() => setError("The scorecard could not be loaded."));
  }, []);

  return (
    <div className="space-y-8">
      <header>
        <p className="text-[11px] uppercase tracking-[0.28em] text-gold">Forward record</p>
        <h1 className="mt-2 font-sans text-5xl font-semibold tracking-tight">Scorecard</h1>
        <p className="mt-3 max-w-2xl text-sm leading-relaxed text-mute">
          Each horizon is blank until that many months have passed since the brief. Returns use the price stored on the
          brief as the start, then later closes, against SPY and the sector ETF. This is not a backtest.
        </p>
      </header>
      {error && <p className="text-sm text-stop">{error}</p>}
      {!summary && !error && <p className="text-sm text-mute">Loading the record…</p>}
      {summary && summary.calls === 0 && (
        <p className="glass px-5 py-10 text-sm text-mute">No briefs yet. The first numbers appear one month after a call.</p>
      )}
      {summary && summary.calls > 0 && (
        <div className="grid gap-4 lg:grid-cols-3">
          <Bucket title="By verdict" rows={summary.by_verdict} />
          <Bucket title="By model" rows={summary.by_model} />
          <section className="glass rounded-2xl p-5">
            <h2 className="font-sans text-xl font-semibold">By seat</h2>
            <p className="mt-1 text-xs text-mute">Whether the seat pointed the same way as the later return.</p>
            <ul className="mt-4 space-y-2 text-sm">
              {summary.by_seat.length === 0 && <li className="text-mute">No seat has a due horizon yet.</li>}
              {summary.by_seat.map((row) => (
                <li key={row.name} className="flex items-center justify-between gap-3">
                  <span>{row.name}</span>
                  <span className="font-mono text-xs text-mute">
                    {row.aligned_rate == null ? "—" : pct(row.aligned_rate)} · {row.scored}
                  </span>
                </li>
              ))}
            </ul>
          </section>
        </div>
      )}
      {calls.length > 0 && (
        <section className="space-y-3">
          <h2 className="font-sans text-2xl font-semibold">Calls on the record</h2>
          {calls.map((call) => (
            <Link
              key={call.id}
              to={`/ticker/${call.ticker}`}
              className="glass flex flex-wrap items-center gap-3 px-5 py-4"
            >
              <span className="w-16 font-mono text-sm text-gold">{call.ticker}</span>
              <span className="text-sm">{call.verdict}</span>
              <span className="min-w-0 flex-1 truncate text-sm text-mute">{call.title}</span>
              {call.superseded_by && <span className="text-[10px] uppercase tracking-wider text-mute">Superseded</span>}
              <span className="font-mono text-xs text-mute">{call.horizons.filter((h) => h.status === "scored").length}/4 scored</span>
            </Link>
          ))}
        </section>
      )}
    </div>
  );
}

function Bucket({
  title,
  rows,
}: {
  title: string;
  rows: { name: string; calls: number; scored_horizons: number; avg_excess_spy: number | null }[];
}) {
  return (
    <section className="glass rounded-2xl p-5">
      <h2 className="font-sans text-xl font-semibold">{title}</h2>
      <ul className="mt-4 space-y-2 text-sm">
        {rows.map((row) => (
          <li key={row.name} className="flex items-center justify-between gap-3">
            <span className="min-w-0 truncate">{row.name}</span>
            <span className="shrink-0 font-mono text-xs text-mute">
              {row.calls} calls · {pct(row.avg_excess_spy)} vs SPY
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
