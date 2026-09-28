import { seatCall, toneClass } from "../lib/stance";
import type { AgentOutput, Report } from "../lib/types";

type Mark = {
  id: string;
  label: string;
  price: number | null;
  probability: string | null;
  thesis: string;
};

function parseMoney(value?: string | number | null): number | null {
  if (value == null || value === "") return null;
  const n = Number(String(value).replace(/[^0-9.]/g, ""));
  return Number.isFinite(n) && n > 0 ? n : null;
}

function money(n: number) {
  return `$${n.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

function readScenario(report: Report, type: "bear" | "base" | "bull", fallback: string): Mark {
  const row = (report.scenarios || []).find((s) => (s.type || "").toLowerCase() === type);
  const probRaw = (row?.probability || "").trim();
  const priceRaw = (row?.price_target || "").trim();
  const probIsMoney = probRaw.startsWith("$");
  const fromField = type === "base" ? report.price_target_base : type === "bull" ? report.price_target_bull : report.price_target_bear;
  const price = parseMoney(priceRaw) ?? (probIsMoney ? parseMoney(probRaw) : null) ?? parseMoney(fromField || fallback);
  const probability = !probRaw || probIsMoney || probRaw.toUpperCase() === "N/A" ? null : probRaw;
  return {
    id: type,
    label: row?.label || `${type[0].toUpperCase()}${type.slice(1)} case`,
    price,
    probability,
    thesis: row?.thesis || "",
  };
}

export default function DecisionDesk({
  report,
  round1,
  spot,
  swing,
  onOpenCouncil,
}: {
  report: Report;
  round1: Record<string, AgentOutput>;
  spot: number | null;
  swing?: string;
  onOpenCouncil: () => void;
}) {
  const marks = [
    readScenario(report, "bear", report.price_target_bear),
    readScenario(report, "base", report.price_target_base),
    readScenario(report, "bull", report.price_target_bull),
  ];
  const seats = Object.values(round1);

  return (
    <div className="space-y-6">
      <section className="glass rounded-[1.6rem] p-6 sm:p-8">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="text-[10px] uppercase tracking-[0.2em] text-gold">Decision range</p>
            <h2 className="mt-1 font-sans text-2xl font-semibold tracking-tight">Where price can go</h2>
          </div>
          <p className="max-w-xs text-right text-xs leading-relaxed text-mute">
            Council scenarios, not a statistical forecast. The dot is the live quote.
          </p>
        </div>
        <PriceRail spot={spot} marks={marks} />
        {swing && (
          <p className="mt-6 border-t border-line pt-4 text-sm leading-relaxed text-mute">
            <span className="font-medium text-mist">What decides the path. </span>
            {swing}
          </p>
        )}
      </section>

      {seats.length > 0 && (
        <section>
          <div className="mb-3 flex items-end justify-between gap-3">
            <h2 className="font-sans text-2xl font-semibold tracking-tight">Council</h2>
            <button
              type="button"
              onClick={onOpenCouncil}
              className="cursor-pointer text-sm text-gold transition-colors duration-200 hover:text-mist"
            >
              Read the notes
            </button>
          </div>
          <div className="flex gap-2 overflow-x-auto pb-1">
            {seats.map((agent) => (
              <SeatPill key={agent.agent_id} agent={agent} />
            ))}
          </div>
        </section>
      )}

      <div className="grid gap-3 md:grid-cols-3">
        {marks.map((mark) => (
          <ScenarioCard key={mark.id} mark={mark} spot={spot} />
        ))}
      </div>
    </div>
  );
}

function SeatPill({ agent }: { agent: AgentOutput }) {
  const call = seatCall(agent);
  return (
    <div className="glass min-w-[10.5rem] shrink-0 rounded-2xl px-3 py-3">
      <p className="truncate text-[10px] uppercase tracking-[0.16em] text-mute" title={agent.agent_name}>
        {agent.agent_name.replace(" Analyst", "").replace(" Specialist", "")}
      </p>
      <p className={`mt-2 inline-flex whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ring-1 ${toneClass(call.tone)}`}>
        {call.label}
      </p>
      <p className="mt-2 font-mono text-[11px] text-mute">{call.score != null ? `${call.score}/10` : "No score"}</p>
    </div>
  );
}

function ScenarioCard({ mark, spot }: { mark: Mark; spot: number | null }) {
  const upside = mark.price && spot ? ((mark.price - spot) / spot) * 100 : null;
  const tone = mark.id === "bull" ? "text-go" : mark.id === "bear" ? "text-stop" : "text-gold";
  return (
    <article className="glass rounded-2xl p-5">
      <div className="flex items-center justify-between gap-2">
        <p className={`text-[11px] uppercase tracking-[0.16em] ${tone}`}>{mark.label}</p>
        <span className="font-mono text-xs text-mute">{mark.probability ?? "Probability unset"}</span>
      </div>
      <p className="mt-3 font-mono text-3xl font-medium tracking-tight">{mark.price != null ? money(mark.price) : "—"}</p>
      {upside != null && (
        <p className={`mt-1 font-mono text-xs ${upside >= 0 ? "text-go" : "text-stop"}`}>
          {upside >= 0 ? "+" : ""}
          {upside.toFixed(1)}% vs last
        </p>
      )}
      {mark.thesis && <p className="mt-3 text-sm leading-relaxed text-mute">{mark.thesis}</p>}
    </article>
  );
}

function PriceRail({ spot, marks }: { spot: number | null; marks: Mark[] }) {
  const priced = marks.filter((m): m is Mark & { price: number } => m.price != null);
  const values = [...priced.map((m) => m.price), ...(spot != null ? [spot] : [])];
  if (values.length < 2) {
    return <p className="mt-6 text-sm text-mute">Not enough prices to draw a range.</p>;
  }
  const min = Math.min(...values);
  const max = Math.max(...values);
  const pad = Math.max((max - min) * 0.14, max * 0.02);
  const lo = min - pad;
  const hi = max + pad;
  const x = (v: number) => 36 + ((v - lo) / (hi - lo)) * 568;
  const bear = priced.find((m) => m.id === "bear");
  const bull = priced.find((m) => m.id === "bull");
  const color = (id: string) => (id === "bull" ? "#1B6B4A" : id === "bear" ? "#A61F3A" : "#8B6914");

  return (
    <div className="mt-6">
      <svg viewBox="0 0 640 132" className="w-full" role="img" aria-label={railLabel(spot, priced)}>
        <line x1="36" y1="58" x2="604" y2="58" stroke="rgba(44,36,28,0.12)" strokeWidth="8" strokeLinecap="round" />
        {bear && bull && (
          <line
            x1={x(Math.min(bear.price, bull.price))}
            y1="58"
            x2={x(Math.max(bear.price, bull.price))}
            y2="58"
            stroke="url(#range)"
            strokeWidth="8"
            strokeLinecap="round"
          />
        )}
        <defs>
          <linearGradient id="range" x1="0" x2="1">
            <stop offset="0" stopColor="#A61F3A" stopOpacity="0.55" />
            <stop offset="0.5" stopColor="#8B6914" stopOpacity="0.7" />
            <stop offset="1" stopColor="#1B6B4A" stopOpacity="0.6" />
          </linearGradient>
        </defs>
        {priced.map((mark) => (
          <g key={mark.id}>
            <line x1={x(mark.price)} y1="50" x2={x(mark.price)} y2="74" stroke={color(mark.id)} strokeWidth="1.5" />
            <text x={x(mark.price)} y="96" textAnchor="middle" fill="#2C241C" fontSize="13" fontFamily="IBM Plex Mono, ui-monospace, monospace">
              {money(mark.price)}
            </text>
            <text x={x(mark.price)} y="114" textAnchor="middle" fill="#5C5148" fontSize="10" fontFamily="IBM Plex Sans, sans-serif" letterSpacing="1.2">
              {mark.id.toUpperCase()}
            </text>
          </g>
        ))}
        {spot != null && (
          <g>
            <text x={x(spot)} y="22" textAnchor="middle" fill="#2C241C" fontSize="13" fontFamily="IBM Plex Mono, ui-monospace, monospace">
              {money(spot)}
            </text>
            <text x={x(spot)} y="36" textAnchor="middle" fill="#8B6914" fontSize="10" fontFamily="IBM Plex Sans, sans-serif" letterSpacing="1.4">
              LAST
            </text>
            <circle cx={x(spot)} cy="58" r="7" fill="#2C241C" />
            <circle cx={x(spot)} cy="58" r="11" fill="none" stroke="#FBF6EC" strokeWidth="3" />
          </g>
        )}
      </svg>
      <table className="mt-2 w-full text-left text-xs text-mute">
        <caption className="sr-only">Council price scenarios versus the last quote</caption>
        <thead>
          <tr className="text-[10px] uppercase tracking-[0.14em]">
            <th className="py-1 font-medium">Case</th>
            <th className="py-1 font-medium">Price</th>
            <th className="py-1 font-medium">Chance</th>
            <th className="py-1 font-medium">Vs last</th>
          </tr>
        </thead>
        <tbody>
          {marks.map((mark) => {
            const upside = mark.price && spot ? ((mark.price - spot) / spot) * 100 : null;
            return (
              <tr key={mark.id} className="border-t border-line">
                <td className="py-1.5 text-mist">{mark.label}</td>
                <td className="py-1.5 font-mono">{mark.price != null ? money(mark.price) : "—"}</td>
                <td className="py-1.5">{mark.probability ?? "—"}</td>
                <td className="py-1.5 font-mono">
                  {upside == null ? "—" : `${upside >= 0 ? "+" : ""}${upside.toFixed(1)}%`}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function railLabel(spot: number | null, marks: { label: string; price: number }[]) {
  const parts = marks.map((m) => `${m.label} ${money(m.price)}`);
  if (spot != null) parts.unshift(`last ${money(spot)}`);
  return parts.join(", ");
}
