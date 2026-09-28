import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { deleteReport, listReports } from "../lib/api";
import { formatTime, verdictBg } from "../lib/format";
import type { HistoryItem } from "../lib/types";

export default function History() {
  const nav = useNavigate();
  const [items, setItems] = useState<HistoryItem[] | null>(null);

  useEffect(() => {
    listReports().then(setItems);
  }, []);

  return (
    <div>
      <p className="text-[11px] uppercase tracking-[0.28em] text-gold">The vault</p>
      <h1 className="mt-2 font-sans text-5xl font-semibold tracking-tight">Archive</h1>
      <p className="mt-3 max-w-xl text-sm text-mute">
        Every CIO brief saved on this computer. Delete removes that file only.
      </p>
      <div className="mt-8 overflow-hidden rounded-3xl">
        {items === null && <p className="glass px-5 py-10 text-sm text-mute">Loading archive…</p>}
        {items?.length === 0 && <p className="glass px-5 py-10 text-sm text-mute">No reports yet.</p>}
        <div className="grid gap-3">
          {(items || []).map((item) => (
            <div
              key={item.id}
              className="glass flex w-full flex-wrap items-center gap-3 px-5 py-4"
            >
              <button
                type="button"
                onClick={() => nav(`/archive/${item.id}`)}
                className="flex min-w-0 flex-1 cursor-pointer flex-wrap items-center gap-3 text-left"
              >
                <span className="w-16 shrink-0 font-mono text-sm text-gold">{item.ticker}</span>
                {item.superseded_by && (
                  <span className="text-[10px] uppercase tracking-wider text-mute">Superseded</span>
                )}
                <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] uppercase tracking-wider ${verdictBg(item.verdict)}`}>
                  {item.verdict}
                </span>
                <span className="min-w-0 flex-1 truncate text-base font-medium">{item.title}</span>
                <span className="shrink-0 font-mono text-xs text-mute">{item.conviction}/10</span>
                <span className="hidden shrink-0 text-xs text-mute xl:inline">{formatTime(item.generated_at)}</span>
              </button>
              <button
                type="button"
                onClick={() => {
                  if (!window.confirm(`Delete the ${item.ticker} brief from this computer?`)) return;
                  deleteReport(item.id)
                    .then(() => setItems((prev) => (prev || []).filter((row) => row.id !== item.id)))
                    .catch(() => window.alert("Could not delete that brief."));
                }}
                className="cursor-pointer text-xs text-mute hover:text-stop"
              >
                Delete
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
