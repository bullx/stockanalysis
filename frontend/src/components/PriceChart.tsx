type Point = { date: string; close: number };

export default function PriceChart({ history, source }: { history?: Point[]; source?: string }) {
  if (!history || history.length < 2) {
    return <p className="text-sm text-mute">No price history for this ticker.</p>;
  }
  const values = history.map((p) => p.close);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const w = 640;
  const h = 168;
  const pad = 8;
  const points = history.map((p, i) => {
    const x = pad + (i / (history.length - 1)) * (w - pad * 2);
    const y = h - pad - ((p.close - min) / span) * (h - pad * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  const first = history[0];
  const last = history[history.length - 1];
  return (
    <figure className="glass rounded-2xl p-5">
      <div className="mb-3 flex items-end justify-between">
        <div>
          <p className="text-[11px] uppercase tracking-[0.18em] text-gold">Price history</p>
          <p className="mt-1 font-mono text-sm text-mist">
            ${first.close.toFixed(2)} → ${last.close.toFixed(2)}
          </p>
        </div>
        <p className="text-[11px] text-mute">{source || "Yahoo Finance"} · Fact</p>
      </div>
      <svg viewBox={`0 0 ${w} ${h}`} className="h-40 w-full" role="img" aria-label="Closing price history">
        <polyline fill="none" stroke="#8B5CF6" strokeWidth="2" points={points.join(" ")} />
      </svg>
      <figcaption className="mt-2 flex justify-between text-[11px] text-mute">
        <span>{first.date}</span>
        <span>{last.date}</span>
      </figcaption>
    </figure>
  );
}
