import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowRight, Clock, Loader2, Square } from "lucide-react";
import AgentCard from "../components/AgentCard";
import { getJob, stopAnalysis, streamJob } from "../lib/api";
import { hydrateDebate } from "../lib/debate";
import { AGENT_ORDER, type AgentOutput, type Debate, type JobSnapshot } from "../lib/types";

const LABELS: Record<string, { name: string; tag: string }> = {
  fundamental: { name: "Fundamentals Analyst", tag: "Business quality" },
  valuation: { name: "Valuation Specialist", tag: "Price vs value" },
  quality: { name: "Earnings Quality", tag: "Forensic ratios" },
  growth: { name: "Growth Engine Analyst", tag: "TAM & trajectory" },
  moat: { name: "Competitive Moat Analyst", tag: "Durability" },
  macro: { name: "Macro Strategist", tag: "Rates & cycle" },
  technical: { name: "Technical Analyst", tag: "Trend & momentum" },
  sentiment: { name: "Sentiment & Flows", tag: "Positioning" },
  risk: { name: "Risk Manager", tag: "Downside" },
  esg: { name: "ESG Analyst", tag: "Resilience" },
  devil: { name: "Devil's Advocate", tag: "Bear case" },
};

export default function Live() {
  const { jobId } = useParams();
  const nav = useNavigate();
  const [job, setJob] = useState<JobSnapshot | null>(null);
  const [runningId, setRunningId] = useState<string | null>(null);
  const [round, setRound] = useState(1);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState("");
  const [stopping, setStopping] = useState(false);

  useEffect(() => {
    if (!jobId) return;
    let stop = false;
    const clock = { running: true };
    getJob(jobId)
      .then((snap) => {
        if (stop) return;
        setJob(snap);
        if (snap.status === "done") nav(`/report/${jobId}`, { replace: true });
        if (snap.status === "error" || snap.status === "stopped") {
          clock.running = false;
          setError(snap.error || (snap.status === "stopped" ? "Stopped." : "Analysis failed"));
        }
      })
      .catch(() => setError("Job not found"));

    const unsub = streamJob(jobId, (event) => {
      const type = String(event.type || "");
      if (type === "agent.started") setRunningId(String(event.agent_id));
      if (type === "round2.started") {
        setRound(2);
        setRunningId(null);
      }
      if (type === "round3.started") {
        setRound(3);
        setRunningId(null);
      }
      if (type === "analysis.done") {
        clock.running = false;
        setRunningId(null);
        setJob((prev) =>
          prev
            ? {
                ...prev,
                status: "done",
                report: event.report as JobSnapshot["report"],
                round1: (event.round1 as JobSnapshot["round1"]) || prev.round1,
                round2: (event.round2 as JobSnapshot["round2"]) || prev.round2,
              }
            : prev,
        );
        nav(`/report/${jobId}`);
      }
      if (type === "analysis.error" || type === "analysis.stopped") {
        clock.running = false;
        setError(String(event.error || "Analysis failed"));
        setRunningId(null);
        setStopping(false);
        setJob((prev) =>
          prev ? { ...prev, status: type === "analysis.stopped" ? "stopped" : "error", error: String(event.error || "") } : prev,
        );
      }
      if (type === "analysis.started") {
        setJob((prev) =>
          prev ? { ...prev, status: "running", meta: event as Record<string, unknown> } : prev,
        );
      }
      if (type === "facts.started") {
        setJob((prev) => (prev ? { ...prev, status: "running", meta: { ...prev.meta, gathering_facts: true } } : prev));
      }
      if (type === "filings.started") {
        setJob((prev) =>
          prev ? { ...prev, status: "running", meta: { ...prev.meta, reading_filings: true } } : prev,
        );
      }
      if (type === "filings.ready") {
        setJob((prev) => (prev ? { ...prev, meta: { ...prev.meta, reading_filings: false } } : prev));
      }
      if (type === "facts.ready" || type === "query.normalized") {
        setJob((prev) =>
          prev
            ? {
                ...prev,
                query: (event.query as JobSnapshot["query"]) || prev.query,
                meta: { ...prev.meta, gathering_facts: false, reading_filings: false },
              }
            : prev,
        );
      }
      if (type === "agent.completed") {
        const row = event as unknown as AgentOutput;
        setJob((prev) =>
          prev ? { ...prev, round1: { ...prev.round1, [row.agent_id]: row } } : prev,
        );
        setRunningId(null);
      }
      if (type === "round2.completed" || type === "round2.skipped") {
        setJob((prev) =>
          prev ? { ...prev, round2: event.debate as Debate } : prev,
        );
      }
    });

    const t0 = Date.now();
    const timer = window.setInterval(() => {
      if (clock.running) setElapsed(Math.floor((Date.now() - t0) / 1000));
    }, 1000);
    return () => {
      stop = true;
      unsub();
      window.clearInterval(timer);
    };
  }, [jobId, nav]);

  const ids = useMemo(() => {
    const fromMeta = (job?.meta?.agent_ids as string[] | undefined) || [];
    const known = fromMeta.length ? fromMeta : Object.keys(job?.round1 || {});
    if (!known.length) return [...AGENT_ORDER];
    return AGENT_ORDER.filter((id) => known.includes(id));
  }, [job]);

  const displayIds = ids.length ? ids : [...AGENT_ORDER];
  const debate = hydrateDebate(job?.round2 || null);
  const halted = job?.status === "stopped" || job?.status === "error";
  const speaker = runningId ? LABELS[runningId]?.name || "A specialist" : "";
  const stage = halted
    ? ""
    : job?.meta?.reading_filings
      ? "Reading the filing diff and the earnings release."
      : job?.meta?.gathering_facts
        ? "Gathering the price history, the filings, and the fact sheet."
        : round === 3
          ? "The CIO is writing the verdict."
          : round === 2
            ? "The moderator is writing the debate."
            : speaker
              ? `${speaker} is writing.`
              : "";

  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-[11px] uppercase tracking-[0.22em] text-gold">Live session</p>
          <h1 className="mt-1 font-sans text-5xl font-semibold tracking-tight">
            {job?.query?.ticker || "…"}
            <span className="ml-3 font-sans text-base font-normal not-italic text-mute">
              {job?.query?.company}
            </span>
          </h1>
        </div>
        <div className="flex items-center gap-4 text-sm text-mute">
          <span className="inline-flex items-center gap-2">
            <Clock className="h-4 w-4 text-gold" />
            {elapsed}s
          </span>
          <RoundPills round={round} done={job?.status === "done"} />
          {job && job.status !== "done" && job.status !== "error" && job.status !== "stopped" && (
            <button
              type="button"
              disabled={stopping}
              onClick={() => {
                if (!jobId) return;
                setStopping(true);
                stopAnalysis(jobId).catch(() => {
                  setStopping(false);
                  setError("Could not stop the model.");
                });
              }}
              className="inline-flex cursor-pointer items-center gap-2 rounded-full bg-stop px-3 py-1.5 text-xs font-medium text-foam transition-colors duration-200 hover:bg-stop/80 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <Square className="h-3.5 w-3.5" />
              {stopping ? "Stopping the model…" : "Stop"}
            </button>
          )}
        </div>
      </header>

      {error && (
        <div className="rounded-2xl border border-stop/30 bg-stop/10 px-4 py-3 text-sm text-stop">
          {error}{" "}
          <Link to="/" className="underline">
            Return home
          </Link>
        </div>
      )}

      {stage && (
        <p className="flex items-center gap-2 text-sm text-gold">
          <Loader2 className="h-4 w-4 animate-spin" />
          {stage}
        </p>
      )}

      <section>
        <h2 className="mb-4 font-sans text-xl font-semibold tracking-tight">The council</h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {displayIds.map((id) => {
            const data = job?.round1?.[id] as AgentOutput | undefined;
            const status = data?.error
              ? "error"
              : data
                ? "done"
                : halted
                  ? "stopped"
                  : runningId === id
                    ? "running"
                    : "queued";
            const meta = LABELS[id] || { name: data?.agent_name || id, tag: data?.tag || "" };
            return (
              <AgentCard key={id} name={meta.name} tag={meta.tag} status={status} data={data} />
            );
          })}
        </div>
      </section>

      {debate && (debate.strongest_bull || debate.strongest_bear) && (
        <DebateStrip debate={debate} />
      )}

      {job?.status === "done" && (
        <div className="flex justify-end">
          <button
            type="button"
            onClick={() => nav(`/report/${jobId}`)}
            className="flex cursor-pointer items-center gap-2 rounded-2xl bg-cta px-5 py-3 font-medium text-foam"
          >
            Open CIO report <ArrowRight className="h-4 w-4" />
          </button>
        </div>
      )}
    </div>
  );
}

function RoundPills({ round, done }: { round: number; done: boolean }) {
  return (
    <div className="flex gap-1">
      {["Specialists", "Debate", "CIO"].map((label, i) => {
        const n = i + 1;
        const active = done || round === n;
        const past = done || round > n;
        return (
          <span
            key={label}
            className={`rounded-full px-3 py-1 text-[11px] uppercase tracking-[0.14em] ${
              past || active ? "bg-cta/15 text-gold" : "bg-black/[0.04] text-mute"
            }`}
          >
            {n} {label}
          </span>
        );
      })}
    </div>
  );
}

function DebateStrip({ debate }: { debate: Debate }) {
  return (
    <section className="grid gap-3 lg:grid-cols-2">
      <div className="glass rounded-2xl p-5">
        <p className="text-[11px] uppercase tracking-[0.18em] text-go">Bull thesis</p>
        <p className="mt-3 text-sm leading-relaxed text-mist">{debate.strongest_bull}</p>
      </div>
      <div className="glass rounded-2xl p-5">
        <p className="text-[11px] uppercase tracking-[0.18em] text-stop">Bear thesis</p>
        <p className="mt-3 text-sm leading-relaxed text-mist">{debate.strongest_bear}</p>
      </div>
    </section>
  );
}
