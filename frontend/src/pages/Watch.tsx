import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { checkWatch, listWatch, unwatchTicker, watchMoves } from "../lib/api";

export default function Watch() {
  const [items, setItems] = useState<{ ticker: string; report_id: string }[] | null>(null);
  const [pairs, setPairs] = useState<{ a: string; b: string; correlation: number | null; moves_together: boolean }[]>([]);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  function reload() {
    listWatch().then(setItems);
    watchMoves().then(setPairs).catch(() => setPairs([]));
  }

  useEffect(() => {
    reload();
  }, []);

  return (
    <div className="space-y-8">
      <header>
        <p className="text-[11px] uppercase tracking-[0.28em] text-gold">While the app is open</p>
        <h1 className="mt-2 font-sans text-5xl font-semibold tracking-tight">Watchlist</h1>
        <p className="mt-3 max-w-2xl text-sm leading-relaxed text-mute">
          A daily check looks for a price move, a new filing, or a sell-if line that is now true. It does not call the
          model. There is no email.
        </p>
      </header>
      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          disabled={busy}
          onClick={() => {
            setBusy(true);
            checkWatch()
              .then(() => setNote("Checked. New changes show in the bar at the top."))
              .catch(() => setNote("The check did not finish."))
              .finally(() => setBusy(false));
          }}
          className="cursor-pointer rounded-full bg-cta px-4 py-2 text-sm font-medium text-foam disabled:opacity-60"
        >
          {busy ? "Checking…" : "Check now"}
        </button>
        <button
          type="button"
          onClick={() => {
            if (!("Notification" in window)) {
              setNote("This browser does not show desktop notifications.");
              return;
            }
            Notification.requestPermission().then((permission) => {
              setNote(permission === "granted" ? "Desktop notifications are on." : "Notifications stay off.");
            });
          }}
          className="cursor-pointer rounded-full bg-page px-4 py-2 text-sm text-mist ring-1 ring-line"
        >
          Allow desktop notifications
        </button>
      </div>
      {note && <p className="text-sm text-mute">{note}</p>}
      {items === null && <p className="text-sm text-mute">Loading names…</p>}
      {items?.length === 0 && <p className="glass px-5 py-10 text-sm text-mute">No names on the watchlist yet. Add one from a brief.</p>}
      {pairs.length > 0 && (
        <section className="glass rounded-2xl p-5">
          <h2 className="font-sans text-xl font-semibold">These move together</h2>
          <p className="mt-1 text-sm text-mute">Price correlation only. It is not a customer or supplier relationship.</p>
          <ul className="mt-4 space-y-2 text-sm">
            {pairs.map((pair) => (
              <li key={`${pair.a}-${pair.b}`} className="flex justify-between gap-3">
                <span className="font-mono text-gold">
                  {pair.a} · {pair.b}
                </span>
                <span className="text-mute">
                  {pair.correlation == null ? "not enough days" : pair.correlation.toFixed(2)}
                  {pair.moves_together ? " · move together" : ""}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
      <div className="space-y-3">
        {(items || []).map((item) => (
          <div key={item.ticker} className="glass flex flex-wrap items-center gap-3 px-5 py-4">
            <Link to={`/ticker/${item.ticker}`} className="w-16 font-mono text-sm text-gold">
              {item.ticker}
            </Link>
            <Link to={`/archive/${item.report_id}`} className="text-sm text-mute">
              Open the brief
            </Link>
            <button
              type="button"
              onClick={() => unwatchTicker(item.ticker).then(reload)}
              className="ml-auto cursor-pointer text-xs text-mute hover:text-stop"
            >
              Remove
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
