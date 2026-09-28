import type { Health, HistoryItem, JobSnapshot, ScoredCall } from "./types";

export async function getHealth(): Promise<Health> {
  const r = await fetch("/api/health");
  if (!r.ok) throw new Error("API offline");
  return r.json();
}

export async function startAnalysis(body: {
  query: string;
  company?: string;
  sector?: string;
  provider?: string;
  model?: string;
  lenses?: boolean;
}): Promise<{ job_id: string }> {
  const r = await fetch("/api/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function stopAnalysis(id: string): Promise<void> {
  const r = await fetch(`/api/analyze/${id}/stop`, { method: "POST" });
  if (!r.ok) throw new Error("Could not stop the desk");
}

export async function getJob(id: string): Promise<JobSnapshot> {
  const r = await fetch(`/api/analyze/${id}`);
  if (!r.ok) throw new Error("Job not found");
  return r.json();
}

export function streamJob(id: string, onEvent: (e: Record<string, unknown>) => void): () => void {
  const es = new EventSource(`/api/analyze/${id}/stream`);
  es.onmessage = (msg) => {
    try {
      onEvent(JSON.parse(msg.data) as Record<string, unknown>);
    } catch {
      /* ignore malformed frames */
    }
  };
  return () => es.close();
}

export async function listReports(): Promise<HistoryItem[]> {
  const r = await fetch("/api/reports");
  if (!r.ok) return [];
  const data = await r.json();
  return data.items ?? [];
}

export async function deleteReport(id: string): Promise<void> {
  const r = await fetch(`/api/reports/${encodeURIComponent(id)}`, { method: "DELETE" });
  if (!r.ok) throw new Error("Could not delete this brief");
}

export async function getReport(id: string) {
  const r = await fetch(`/api/reports/${id}`);
  if (!r.ok) throw new Error("Report not found");
  return r.json();
}

export async function getScorecard(): Promise<{ summary: ScoreSummary; calls: ScoredCall[] }> {
  const r = await fetch("/api/scorecard");
  if (!r.ok) throw new Error("Scorecard unavailable");
  return r.json();
}

export async function getTickerHistory(ticker: string): Promise<{ ticker: string; calls: ScoredCall[] }> {
  const r = await fetch(`/api/tickers/${encodeURIComponent(ticker)}`);
  if (!r.ok) throw new Error("Ticker history unavailable");
  return r.json();
}

export async function getReportStatus(id: string): Promise<{
  banner: string;
  watching: boolean;
  price?: number | null;
}> {
  const r = await fetch(`/api/reports/${encodeURIComponent(id)}/status`);
  if (!r.ok) throw new Error("Status unavailable");
  return r.json();
}

export async function updateBrief(id: string): Promise<{ id: string }> {
  const r = await fetch(`/api/reports/${encodeURIComponent(id)}/update`, { method: "POST" });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function watchTicker(ticker: string, reportId: string): Promise<void> {
  const r = await fetch("/api/watch", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ticker, report_id: reportId }),
  });
  if (!r.ok) throw new Error("Could not watch this name");
}

export async function unwatchTicker(ticker: string): Promise<void> {
  const r = await fetch(`/api/watch/${encodeURIComponent(ticker)}`, { method: "DELETE" });
  if (!r.ok) throw new Error("Could not remove the name");
}

export async function watchMoves(): Promise<{ a: string; b: string; correlation: number | null; moves_together: boolean }[]> {
  const r = await fetch("/api/watch/moves");
  if (!r.ok) return [];
  const data = await r.json();
  return data.pairs ?? [];
}

export async function listWatch(): Promise<{ ticker: string; report_id: string; added_at?: string }[]> {
  const r = await fetch("/api/watch");
  if (!r.ok) return [];
  const data = await r.json();
  return data.items ?? [];
}

export async function listAlerts(): Promise<{ id: string; ticker: string; report_id: string; message: string; seen: boolean }[]> {
  const r = await fetch("/api/alerts");
  if (!r.ok) return [];
  const data = await r.json();
  return data.items ?? [];
}

export async function markAlertsSeen(): Promise<void> {
  await fetch("/api/alerts/seen", { method: "POST" });
}

export async function checkWatch(): Promise<void> {
  const r = await fetch("/api/watch/check", { method: "POST" });
  if (!r.ok) throw new Error("Check failed");
}

export type ScoreSummary = {
  by_verdict: { name: string; calls: number; scored_horizons: number; avg_excess_spy: number | null }[];
  by_model: { name: string; calls: number; scored_horizons: number; avg_excess_spy: number | null }[];
  by_seat: { name: string; scored: number; aligned_rate: number | null }[];
  calls: number;
  forward_only: boolean;
};

export async function getQuote(ticker: string): Promise<{
  ticker: string;
  price: number;
  asof: string;
  name?: string;
  change_pct?: number | null;
} | null> {
  const r = await fetch(`/api/quote/${encodeURIComponent(ticker)}`);
  if (!r.ok) return null;
  return r.json();
}
