import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, Cpu, Loader2, Sparkles } from "lucide-react";
import { getHealth, listReports, startAnalysis } from "../lib/api";
import { BRAND } from "../lib/brand";
import { formatTime, verdictBg } from "../lib/format";
import type { Health, HistoryItem } from "../lib/types";

export default function Home() {
  const nav = useNavigate();
  const [query, setQuery] = useState("");
  const [company, setCompany] = useState("");
  const [provider, setProvider] = useState("");
  const [model, setModel] = useState("");
  const [shortDesk, setShortDesk] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [health, setHealth] = useState<Health | null>(null);
  const [recent, setRecent] = useState<HistoryItem[]>([]);

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch(() => setHealth(null));
    listReports()
      .then(setRecent)
      .catch(() => setRecent([]));
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim() || busy) return;
    setBusy(true);
    setError("");
    try {
      const { job_id } = await startAnalysis({
        query: query.trim(),
        company: company.trim() || undefined,
        provider: provider.trim() || undefined,
        model: model.trim() || undefined,
        lenses: !shortDesk,
      });
      nav(`/run/${job_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start");
      setBusy(false);
    }
  }

  return (
    <div className="space-y-10">
      <section className="grid items-stretch gap-4 lg:grid-cols-5">
        <div className="glass relative overflow-hidden rounded-[1.75rem] p-8 sm:p-10 lg:col-span-2">
          <p className="inline-flex items-center gap-2 text-[11px] font-medium uppercase tracking-[0.22em] text-gold">
            <Sparkles className="h-3.5 w-3.5" />
            {BRAND.legal}
          </p>
          <h1 className="mt-6 font-sans text-5xl font-semibold leading-[1.02] tracking-tight sm:text-6xl">
            The desk that debates before it decides.
          </h1>
          <p className="mt-5 max-w-sm text-sm leading-relaxed text-mute">
            The specialists write alone. A moderator forces the split. Then a CIO puts a verdict on the page.
          </p>
          {health && (
            <div className="mt-8 space-y-3">
              <div className="inline-flex items-center gap-2 rounded-full border border-line bg-foam/80 px-3 py-1.5 text-xs text-mute">
                <Cpu className="h-3.5 w-3.5 text-cta" />
                {health.demo ? "Demo engine" : health.provider} · {health.model} · {health.tier} · {health.agent_count} seats
              </div>
              {health.model_ready === false && (
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => {
                    setBusy(true);
                    startAnalysis({ query: query.trim() || "AAPL", provider: "mock", model: "mock" })
                      .then(({ job_id }) => nav(`/run/${job_id}`))
                      .catch(() => setBusy(false));
                  }}
                  className="block cursor-pointer text-left text-sm text-gold"
                >
                  No model is installed. Preview the desk with the demo engine.
                </button>
              )}
            </div>
          )}
        </div>
        <form onSubmit={submit} className="glass rounded-[1.75rem] p-6 sm:p-8 lg:col-span-3">
            <label htmlFor="ticker" className="text-[11px] uppercase tracking-[0.2em] text-mute">
              Ticker or question
            </label>
            <div className="mt-3 flex flex-col gap-3 sm:flex-row">
              <input
                id="ticker"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="VTI · AAPL · Is Tesla worth buying?"
                className="h-14 flex-1 rounded-2xl border border-line bg-foam px-5 font-mono text-lg tracking-wide text-mist outline-none transition-colors duration-200 placeholder:text-mute/50 focus:border-cta"
                autoComplete="off"
              />
              <button
                type="submit"
                disabled={busy || !query.trim()}
                className="flex h-14 cursor-pointer items-center justify-center gap-2 rounded-2xl bg-cta px-6 font-medium text-foam shadow-glow transition-colors duration-200 ease-out hover:bg-[#7C3AED] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRight className="h-4 w-4" />}
                Convene the desk
              </button>
            </div>
            <div className="mt-5 grid gap-3 sm:grid-cols-3">
              <Field label="Company" id="company" value={company} onChange={setCompany} placeholder="Optional" />
              <Field label="Provider" id="provider" value={provider} onChange={setProvider} placeholder="ollama · openai" mono />
              <Field label="Model" id="model" value={model} onChange={setModel} placeholder="llama3.1:8b" mono />
            </div>
            <label className="mt-4 flex cursor-pointer items-start gap-2 text-sm text-mute">
              <input
                type="checkbox"
                checked={shortDesk}
                onChange={(e) => setShortDesk(e.target.checked)}
                className="mt-1"
              />
              <span>
                Short desk only: fundamentals, valuation, earnings quality, and the bear case. Leave this off for the
                full council.
              </span>
            </label>
            {error && <p className="mt-3 text-sm text-stop">{error}</p>}
        </form>
      </section>

      {recent.length > 0 && (
        <section>
          <div className="mb-5 flex items-end justify-between">
            <div>
              <p className="text-[11px] uppercase tracking-[0.22em] text-gold">The library</p>
              <h2 className="font-sans text-3xl font-semibold tracking-tight">Recent briefs</h2>
            </div>
            <button
              type="button"
              onClick={() => nav("/history")}
              className="cursor-pointer text-xs uppercase tracking-[0.16em] text-mute transition-colors hover:text-gold"
            >
              Open archive
            </button>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {recent.slice(0, 6).map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => nav(`/archive/${item.id}`)}
                className="glass cursor-pointer rounded-2xl p-5 text-left transition-shadow duration-200 ease-out hover:shadow-lift"
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-sm text-gold">{item.ticker}</span>
                  <span className={`rounded-full px-2 py-0.5 text-[10px] uppercase tracking-wider ${verdictBg(item.verdict)}`}>
                    {item.verdict}
                  </span>
                </div>
                <p className="mt-3 line-clamp-2 text-lg font-medium leading-snug tracking-tight">{item.title}</p>
                <p className="mt-4 text-[11px] text-mute">
                  {item.conviction}/10 · {formatTime(item.generated_at)}
                </p>
              </button>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function Field({
  label,
  id,
  value,
  onChange,
  placeholder,
  mono,
}: {
  label: string;
  id: string;
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
  mono?: boolean;
}) {
  return (
    <div>
      <label htmlFor={id} className="text-[11px] uppercase tracking-[0.18em] text-mute">
        {label}
      </label>
      <input
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className={`mt-2 h-11 w-full rounded-xl border border-line bg-foam px-3 text-sm outline-none transition-colors duration-200 placeholder:text-mute/40 focus:border-cta ${
          mono ? "font-mono" : ""
        }`}
      />
    </div>
  );
}
