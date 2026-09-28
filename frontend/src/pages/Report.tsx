import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { AlertTriangle, Scale } from "lucide-react";
import DecisionDesk from "../components/DecisionDesk";
import PriceChart from "../components/PriceChart";
import VerdictMark from "../components/VerdictMark";
import { getJob, getQuote, getReport, getReportStatus, updateBrief, watchTicker } from "../lib/api";
import { debateHasStructure, hydrateDebate } from "../lib/debate";
import { formatTime, verdictTone } from "../lib/format";
import { seatCall, toneClass } from "../lib/stance";
import type { AgentOutput, Debate, Report } from "../lib/types";

function parseMoney(value?: string | number | null): number | null {
  if (value == null || value === "") return null;
  const n = Number(String(value).replace(/[^0-9.]/g, ""));
  return Number.isFinite(n) && n > 0 ? n : null;
}

function councilIsHollow(round1: Record<string, AgentOutput>) {
  const items = Object.values(round1);
  if (!items.length) return true;
  return items.every((a) => !(a.output || "").trim());
}

export default function ReportPage({ archived = false }: { archived?: boolean }) {
  const { jobId, reportId } = useParams();
  const [report, setReport] = useState<Report | null>(null);
  const [round1, setRound1] = useState<Record<string, AgentOutput>>({});
  const [round2, setRound2] = useState<Debate | null>(null);
  const [tab, setTab] = useState<"brief" | "facts" | "council" | "debate">("brief");
  const [error, setError] = useState("");
  const [spot, setSpot] = useState<{ price: number; asof: string; change_pct?: number | null } | null>(null);
  const [banner, setBanner] = useState("");
  const [updating, setUpdating] = useState(false);
  const nav = useNavigate();
  const savedId = archived ? reportId : report?.id;

  useEffect(() => {
    const load = async () => {
      try {
        if (archived && reportId) {
          const data = await getReport(reportId);
          setReport(data.report);
          setRound1(data.round1 || {});
          setRound2(hydrateDebate(data.round2));
          if (data.report?.ticker) setSpot(await getQuote(data.report.ticker));
        } else if (jobId) {
          const job = await getJob(jobId);
          if (!job.report) {
            setError("Report is not ready yet.");
            return;
          }
          setReport(job.report);
          setRound1(job.round1 || {});
          setRound2(hydrateDebate(job.round2));
          if (job.report.ticker) setSpot(await getQuote(job.report.ticker));
        }
      } catch {
        setError("Could not load report.");
      }
    };
    load();
  }, [archived, jobId, reportId]);

  useEffect(() => {
    if (!savedId) return;
    getReportStatus(savedId)
      .then((status) => setBanner(status.banner || ""))
      .catch(() => setBanner(""));
  }, [savedId]);

  const debate = useMemo(() => hydrateDebate(round2), [round2]);

  if (error) {
    return (
      <p className="text-stop">
        {error}{" "}
        <Link className="underline" to="/">
          Home
        </Link>
      </p>
    );
  }
  if (!report) {
    return <p className="text-mute">Loading brief…</p>;
  }

  const last = report.last_price ?? spot?.price ?? null;
  const base = parseMoney(report.price_target_base);
  const gap = last && base ? ((base - last) / last) * 100 : null;
  const incomplete = Object.values(round1).filter((a) => seatCall(a).tone === "incomplete" || seatCall(a).tone === "empty").length;

  return (
    <article className="space-y-6">
      {banner && savedId && (
        <div className="rounded-2xl border border-line bg-foam px-4 py-3 text-sm text-mist">
          <p>{banner}</p>
          <div className="mt-3 flex flex-wrap gap-3">
            <button
              type="button"
              disabled={updating}
              onClick={() => {
                setUpdating(true);
                updateBrief(savedId)
                  .then((saved) => nav(`/archive/${saved.id}`))
                  .catch(() => setUpdating(false));
              }}
              className="cursor-pointer rounded-full bg-cta px-3 py-1.5 text-xs font-medium text-foam disabled:opacity-60"
            >
              {updating ? "Writing the delta note…" : "Write a delta note"}
            </button>
            <button
              type="button"
              onClick={() => watchTicker(report.ticker, savedId).catch(() => undefined)}
              className="cursor-pointer rounded-full bg-page px-3 py-1.5 text-xs text-mist ring-1 ring-line"
            >
              Watch this name
            </button>
          </div>
        </div>
      )}
      <header className="glass space-y-4 rounded-2xl p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-3">
            <Link to={`/ticker/${report.ticker}`} className="font-mono text-sm font-medium text-gold">
              {report.ticker}
            </Link>
            <VerdictMark verdict={report.verdict} large />
            <span className="rounded-full bg-page px-2 py-0.5 text-[11px] font-medium text-mute">{report.horizon}</span>
          </div>
          <p className="text-[11px] text-mute">
            {report.provider_used} · {formatTime(report.generated_at)}
          </p>
        </div>
        <h1 className={`max-w-4xl font-sans text-3xl font-semibold leading-tight tracking-tight sm:text-4xl ${verdictTone(report.verdict)}`}>
          {report.title}
        </h1>
        <p className="max-w-3xl text-sm leading-relaxed text-mute">{report.summary}</p>
        <FreshnessStamp report={report} />
        <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Stat label="Last price" kind="Fact" value={last != null ? `$${last.toFixed(2)}` : "No quote"} hint={spot ? spot.asof : report.last_price_asof || undefined} />
          <Stat label="Base target" kind="Council" value={report.price_target_base || "—"} hint={gap != null ? `${gap >= 0 ? "+" : ""}${gap.toFixed(1)}% vs last` : undefined} />
          <Stat label="Conviction" kind="CIO" value={`${report.conviction}/10`} />
          <Stat label="Risk" kind="CIO" value={report.risk_level || "—"} hint={incomplete ? `${incomplete} seat${incomplete === 1 ? "" : "s"} incomplete` : "All seats called"} />
        </dl>
        <QualityBanner report={report} round1={round1} debate={debate} spot={spot} />
      </header>

      <div className="glass flex gap-1 rounded-2xl p-1">
        {(
          [
            ["brief", "Decision"],
            ["facts", "Fact sheet"],
            ["council", "Council notes"],
            ["debate", "Debate"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            onClick={() => setTab(id)}
            className={`flex-1 cursor-pointer rounded-xl py-2.5 text-sm transition-colors duration-200 ${
              tab === id ? "bg-cta text-foam" : "text-mute hover:text-mist"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "brief" && (
        <Brief
          report={report}
          round1={round1}
          spot={report.last_price ?? spot?.price ?? null}
          swing={debate?.swing_factor}
          onOpenCouncil={() => setTab("council")}
        />
      )}
      {tab === "facts" && <FactsPanel report={report} />}
      {tab === "council" && <CouncilNotes round1={round1} />}
      {tab === "debate" && <DebateView debate={debate} />}

      <p className="text-xs leading-relaxed text-mute">
        Informational only. Not financial advice. Models may be stale and do not replace due diligence.
      </p>
    </article>
  );
}

function FreshnessStamp({ report }: { report: Report }) {
  const f = report.freshness;
  const coverage =
    report.coverage === "us"
      ? "US filer · full facts"
      : report.coverage === "etf"
        ? "ETF · price only"
        : report.coverage === "non_us"
          ? "Non-US · price only"
          : null;
  return (
    <p className="text-[11px] leading-relaxed text-mute">
      {coverage && <span className="mr-2 rounded-full bg-page px-2 py-0.5 font-medium text-gold">{coverage}</span>}
      As of {f?.last_price_asof || report.last_price_asof || "n/a"}
      {f?.last_price != null ? ` · last $${Number(f.last_price).toFixed(2)}` : ""}
      {f?.latest_filing_form ? ` · latest filing ${f.latest_filing_form} ${f.latest_filing_date || ""}` : ""}
      {f?.council_ran_at ? ` · council ${formatTime(f.council_ran_at)}` : ""}
    </p>
  );
}

function PricedIn({ report }: { report: Report }) {
  const dcf = report.priced_in;
  if (!dcf || dcf.implied_growth == null) return null;
  const hist = (report.fact_sheet?.business as { revenue_cagr_5y?: number } | undefined)?.revenue_cagr_5y;
  return (
    <section className="rounded-2xl bg-gradient-to-r from-cta/15 via-gold/10 to-transparent p-6 ring-1 ring-cta/25">
      <p className="text-[11px] uppercase tracking-[0.2em] text-gold">What the price implies · Fact + math</p>
      <p className="mt-3 font-sans text-xl font-semibold leading-snug tracking-tight">
        Last price is consistent with about {(dcf.implied_growth * 100).toFixed(1)}% near-term FCF growth
        {hist != null ? `, vs a 5-year revenue CAGR of ${(hist * 100).toFixed(1)}%` : ""}.
      </p>
      <p className="mt-2 text-sm text-mute">
        Reverse DCF in code, discount {(dcf.discount_rate ? dcf.discount_rate * 100 : 9).toFixed(1)}%, fading to 3% over
        five years. The council should say whether it believes that path — this is not a forecast.
      </p>
    </section>
  );
}

function fmtNum(value?: number | null) {
  if (value == null || Number.isNaN(value)) return "—";
  return value.toFixed(1);
}

function fmtPct(value?: number | null) {
  if (value == null || Number.isNaN(value)) return "—";
  return `${(value * 100).toFixed(1)}%`;
}

function FactsPanel({ report }: { report: Report }) {
  const sheet = report.fact_sheet;
  if (!sheet) {
    return <p className="text-mute">No fact sheet was saved with this brief.</p>;
  }
  const flags = sheet.filings?.red_flags || [];
  return (
    <div className="space-y-6">
      <PriceChart history={sheet.history} source={sheet.sources?.price || "Yahoo Finance"} />
      {sheet.peers && sheet.peers.length > 1 && (
        <section className="glass rounded-2xl p-6">
          <p className="text-[11px] uppercase tracking-[0.18em] text-gold">Same-industry peers</p>
          <p className="mt-2 text-sm text-mute">Multiples are computed from SEC facts and a Yahoo price. They are not a model guess.</p>
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-[11px] uppercase tracking-[0.14em] text-mute">
                <tr>
                  <th className="py-2 pr-3">Ticker</th>
                  <th className="py-2 pr-3">P/E</th>
                  <th className="py-2 pr-3">EV/EBITDA</th>
                  <th className="py-2 pr-3">Operating margin</th>
                  <th className="py-2">FCF yield</th>
                </tr>
              </thead>
              <tbody>
                {sheet.peers.map((row) => (
                  <tr key={row.ticker} className="border-t border-line">
                    <td className="py-2 pr-3 font-mono text-gold">{row.ticker}</td>
                    <td className="py-2 pr-3 font-mono">{fmtNum(row.pe)}</td>
                    <td className="py-2 pr-3 font-mono">{fmtNum(row.ev_ebitda)}</td>
                    <td className="py-2 pr-3 font-mono">{fmtPct(row.operating_margin)}</td>
                    <td className="py-2 font-mono">{fmtPct(row.fcf_yield)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
      {sheet.prompt && (
        <section className="glass rounded-2xl p-6">
          <p className="text-[11px] uppercase tracking-[0.18em] text-gold">Sourced numbers handed to the council</p>
          <p className="mt-2 text-sm text-mute">
            Yahoo, SEC, and FRED lines are code. A Filings reader or Earnings reader block, when present, is the model summarizing that diff only.
          </p>
          <pre className="mt-4 whitespace-pre-wrap font-mono text-xs leading-relaxed text-mute">{sheet.prompt}</pre>
        </section>
      )}
      {flags.length > 0 && (
        <section className="glass rounded-2xl p-6">
          <p className="text-[11px] uppercase tracking-[0.18em] text-stop">Red-flag scan</p>
          <ul className="mt-3 space-y-2 text-sm text-mute">
            {flags.map((f) => (
              <li key={`${f.source}-${f.phrase}`}>
                <span className="font-medium text-mist">{f.phrase}</span> · {f.source}
                <p className="text-xs">{f.snippet}</p>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function Stat({ label, value, hint, kind }: { label: string; value: string; hint?: string; kind?: string }) {
  return (
    <div className="rounded-2xl bg-foam px-4 py-3 ring-1 ring-line">
      <div className="flex items-center justify-between gap-2">
        <dt className="text-[10px] font-medium uppercase tracking-[0.16em] text-mute">{label}</dt>
        {kind && <span className="text-[10px] font-medium uppercase tracking-[0.14em] text-gold">{kind}</span>}
      </div>
      <dd className="mt-1 font-mono text-lg font-medium tracking-tight text-mist">{value}</dd>
      {hint && <p className="mt-1 text-[11px] text-mute">{hint}</p>}
    </div>
  );
}

function QualityBanner({
  report,
  round1,
  debate,
  spot,
}: {
  report: Report;
  round1: Record<string, AgentOutput>;
  debate: Debate | null;
  spot: { price: number; asof: string } | null;
}) {
  const notes: string[] = [];
  if (councilIsHollow(round1)) {
    notes.push(
      "Council notes were not captured. Specialists returned empty text. The CIO brief was written without those notes.",
    );
  }
  if (!debateHasStructure(debate) && !(debate?.raw_text || "").trim()) {
    notes.push("Debate is empty because there were no specialist notes to moderate.");
  }
  const incomplete = Object.values(round1).filter((a) => {
    const tone = seatCall(a).tone;
    return tone === "incomplete" || tone === "empty";
  }).length;
  if (incomplete) {
    notes.push(`${incomplete} of ${Object.keys(round1).length} seats stopped before a verdict. Those chips are not votes.`);
  }
  const last = report.last_price ?? spot?.price ?? null;
  const target = parseMoney(report.price_target_base);
  if (last && target && (target / last < 0.4 || target / last > 2.5)) {
    notes.push(
      `Base target ${report.price_target_base} is far from the last quote $${last.toFixed(2)}. The model likely used a stale price from training data.`,
    );
  }
  if (report.coverage && report.coverage !== "us") {
    notes.push("Fundamentals and filings are unavailable for this security. Price history is real; other figures in the notes may be the model's memory.");
  }
  if (report.data_quality_notes) notes.push(report.data_quality_notes);
  if (!notes.length) return null;
  return (
    <div className="mt-6 rounded-2xl border border-warn/25 bg-warn/5 p-4 text-sm leading-relaxed">
      <p className="flex items-center gap-2 font-medium text-warn">
        <AlertTriangle className="h-4 w-4" />
        How this brief was processed
      </p>
      <ul className="mt-2 list-disc space-y-1 pl-5 text-mute">
        {notes.map((n) => (
          <li key={n}>{n}</li>
        ))}
      </ul>
    </div>
  );
}

function Brief({
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
  return (
    <div className="space-y-8">
      <PricedIn report={report} />
      <DecisionDesk report={report} round1={round1} spot={spot} swing={swing} onOpenCouncil={onOpenCouncil} />
      <PriceChart
        history={report.fact_sheet?.history}
        source={report.fact_sheet?.sources?.price || "Yahoo Finance"}
      />

      <section className="grid gap-4 lg:grid-cols-2">
        <div className="glass space-y-4 rounded-2xl p-6">
          <h2 className="font-sans text-2xl font-semibold tracking-tight">Why this could fail</h2>
          <ul className="space-y-3">
            {(report.risks || []).map((r) => {
              const same = (r.description || "").trim().toLowerCase() === (r.name || "").trim().toLowerCase();
              const scored = r.score != null && r.score > 0 && !same;
              return (
                <li key={r.name} className="rounded-xl bg-page px-4 py-3 ring-1 ring-line">
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-sm font-medium">{r.name}</span>
                    {scored && <span className="font-mono text-xs text-stop">{r.score}/10</span>}
                  </div>
                  {r.description && !same && <p className="mt-1 text-sm leading-relaxed text-mute">{r.description}</p>}
                </li>
              );
            })}
          </ul>
          {(report.sell_if?.length || report.thesis_invalidators?.length) ? (
            <div>
              <p className="mb-2 flex items-center gap-2 text-sm font-medium text-warn">
                <AlertTriangle className="h-4 w-4" />
                Sell if
              </p>
              <ol className="list-decimal space-y-2 pl-5 text-sm leading-relaxed text-mute">
                {(report.sell_if || []).map((item) => (
                  <li key={item.label}>{item.label}</li>
                ))}
                {(report.thesis_invalidators || [])
                  .filter((line) => !(report.sell_if || []).some((item) => item.label === line))
                  .map((line) => (
                    <li key={line}>{line}</li>
                  ))}
              </ol>
            </div>
          ) : null}
        </div>
        <div className="glass space-y-4 rounded-2xl p-6">
          <h2 className="font-sans text-2xl font-semibold tracking-tight">How to hold it</h2>
          <ol className="space-y-3">
            {(report.investment_strategy || []).map((s, i) => (
              <li key={i} className="flex gap-3 text-sm leading-relaxed">
                <span className="font-mono text-gold">{String(i + 1).padStart(2, "0")}</span>
                {s}
              </li>
            ))}
          </ol>
          <div className="rounded-xl bg-page px-4 py-3 text-sm leading-relaxed text-mute">
            <p className="text-[11px] uppercase tracking-[0.14em] text-gold">How to think about size</p>
            <p className="mt-2">
              {report.position_guidance?.note ||
                "Size is your decision. This brief does not recommend a portfolio weight."}
            </p>
            {report.position_guidance?.stance && <p className="mt-2 text-mist">{report.position_guidance.stance}</p>}
          </div>
          <p className="text-xs leading-relaxed text-mute">
            Figures inside the specialist notes, other than the last price, are the model’s opinion.
          </p>
        </div>
      </section>

      {report.catalysts?.length > 0 && (
        <section className="glass rounded-2xl p-6">
          <h2 className="mb-4 font-sans text-2xl font-semibold tracking-tight">Catalysts</h2>
          <div className="space-y-2">
            {report.catalysts.map((c) => (
              <div key={c.label} className="flex gap-4 rounded-xl bg-foam/80 px-4 py-3 ring-1 ring-line">
                <span className="w-20 shrink-0 text-[10px] uppercase tracking-[0.14em] text-gold">{c.type}</span>
                <div>
                  <p className="text-sm">
                    {c.label} <span className="text-mute">· {c.timeline}</span>
                  </p>
                  <p className="text-sm text-mute">{c.detail}</p>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

    </div>
  );
}

function CouncilNotes({ round1 }: { round1: Record<string, AgentOutput> }) {
  const items = Object.values(round1);
  if (!items.length) return <p className="text-mute">No specialist notes.</p>;
  return (
    <div className="space-y-4">
      {items.map((a) => {
        const call = seatCall(a);
        return (
          <section key={a.agent_id} className="glass rounded-2xl p-6">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-[10px] uppercase tracking-[0.2em] text-gold/70">{a.tag}</p>
                <h3 className="font-sans text-xl font-semibold tracking-tight">{a.agent_name}</h3>
              </div>
              <div className="text-right">
                <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ring-1 ${toneClass(call.tone)}`}>
                  {call.label}
                </span>
                <p className="mt-1 font-mono text-[11px] text-mute">{call.score != null ? `${call.score}/10` : "No score"}</p>
              </div>
            </div>
            {call.detail && <p className="mt-3 text-sm text-warn">{call.detail}</p>}
            <p className="mt-4 whitespace-pre-wrap text-sm leading-relaxed text-mute">
              {call.tone === "empty"
                ? a.error || "This seat returned no specialist text, so it is not counted as a vote."
                : a.output}
            </p>
          </section>
        );
      })}
    </div>
  );
}

function DebateView({ debate }: { debate: Debate | null }) {
  const filled = debateHasStructure(debate);
  if (!debate || (!filled && !(debate.raw_text || "").trim())) {
    return (
      <p className="text-mute">
        No debate was produced. The moderator had empty council notes, so there was nothing to synthesize.
      </p>
    );
  }
  if (!filled) {
    return (
      <div className="glass rounded-2xl p-6">
        <p className="text-[11px] uppercase tracking-[0.18em] text-gold">Moderator transcript</p>
        <p className="mt-4 whitespace-pre-wrap text-sm leading-relaxed text-mute">{debate.raw_text}</p>
      </div>
    );
  }
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="font-sans text-2xl font-semibold tracking-tight">The chamber</h2>
        <div className="flex items-center gap-2 rounded-full bg-cta/15 px-3 py-1 text-sm text-gold">
          <Scale className="h-4 w-4" />
          Consensus {debate.consensus_score}/10
          {debate.synthetic ? " · synthetic" : ""}
        </div>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="glass rounded-2xl p-6 ring-1 ring-go/20">
          <p className="text-[11px] uppercase tracking-[0.2em] text-go">Strongest bull</p>
          <p className="mt-4 font-sans text-lg font-medium leading-relaxed">{debate.strongest_bull}</p>
        </div>
        <div className="glass rounded-2xl p-6 ring-1 ring-stop/20">
          <p className="text-[11px] uppercase tracking-[0.2em] text-stop">Strongest bear</p>
          <p className="mt-4 font-sans text-lg font-medium leading-relaxed">{debate.strongest_bear}</p>
        </div>
      </div>
      {debate.swing_factor && (
        <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-cta/20 via-gold/10 to-transparent p-6 ring-1 ring-cta/30">
          <p className="text-[11px] uppercase tracking-[0.22em] text-gold">Swing factor</p>
          <p className="mt-3 font-sans text-xl font-semibold tracking-tight leading-snug">{debate.swing_factor}</p>
        </div>
      )}
      <div className="grid gap-4 lg:grid-cols-2">
        <Block title="Where they agree" items={debate.consensus_points} />
        <Block title="Where they split" items={debate.key_disagreements} />
      </div>
      <Block title="Still unresolved" items={debate.unresolved_questions} />
    </div>
  );
}

function Block({ title, items }: { title: string; items?: string[] }) {
  if (!items?.length) return null;
  return (
    <div className="glass rounded-2xl p-6">
      <h3 className="text-[11px] uppercase tracking-[0.16em] text-gold/80">{title}</h3>
      <ul className="mt-4 space-y-3 text-sm leading-relaxed">
        {items.map((i) => (
          <li key={i} className="border-l border-cta/40 pl-4 text-mute">
            {i}
          </li>
        ))}
      </ul>
    </div>
  );
}
