export type AgentOutput = {
  agent_id: string;
  agent_name: string;
  tag?: string;
  output: string;
  conviction: number;
  stance: string;
  error?: string;
  timestamp?: string;
};

export type Debate = {
  consensus_points: string[];
  key_disagreements: string[];
  strongest_bull: string;
  strongest_bear: string;
  swing_factor: string;
  unresolved_questions: string[];
  consensus_score: number;
  raw_text: string;
  synthetic?: boolean;
  empty?: boolean;
  fallback?: string;
};

export type Report = {
  ticker: string;
  company_name: string;
  sector: string;
  type: string;
  verdict: string;
  title: string;
  summary: string;
  conviction: number;
  price_target_base: string;
  price_target_bull: string;
  price_target_bear: string;
  implied_upside_base: string;
  risk_level: string;
  risk_note: string;
  horizon: string;
  horizon_note: string;
  consensus_score: number;
  consensus_description: string;
  scenarios: { type: string; label?: string; probability: string; price_target: string; thesis: string }[];
  catalysts: { type: string; label: string; timeline: string; detail: string }[];
  risks: { name: string; score?: number | null; description: string }[];
  financial_health: { metric: string; value: string; assessment: string; note: string }[];
  predictability_scores: { dimension: string; score: number; rationale: string }[];
  position_sizing: {
    aggressive_investor: string;
    moderate_investor: string;
    conservative_investor: string;
    sizing_rationale: string;
  };
  investment_strategy: string[];
  thesis_invalidators: string[];
  sell_if?: SellIf[];
  position_guidance?: { stance?: string; note?: string };
  id?: string;
  kind?: string;
  update_note?: string;
  sector_etf?: string;
  data_quality_notes: string | null;
  last_price?: number | null;
  last_price_asof?: string | null;
  generated_at?: string;
  provider_used?: string;
  total_time_s?: number;
  tier?: string;
  coverage?: string;
  freshness?: {
    built_at?: string;
    last_price?: number | null;
    last_price_asof?: string | null;
    latest_filing_form?: string;
    latest_filing_date?: string;
    council_ran_at?: string;
  };
  priced_in?: {
    discount_rate?: number;
    implied_growth?: number | null;
    scenarios?: Record<string, { growth?: number; price?: number | null }>;
  };
  fact_sheet?: {
    coverage?: string;
    company?: string;
    sic_description?: string;
    sector_etf?: string;
    business?: Record<string, unknown>;
    forensic?: { notes?: string[] };
    valuation?: Record<string, unknown>;
    price?: Record<string, unknown>;
    history?: { date: string; close: number }[];
    sources?: Record<string, string | null>;
    prompt?: string;
    filing_readers?: string;
    latest_filing?: { form?: string; filed?: string };
    peers?: { ticker: string; name?: string; pe?: number | null; ev_ebitda?: number | null; operating_margin?: number | null; fcf_yield?: number | null }[];
    filings?: {
      red_flags?: { phrase: string; source: string; snippet: string }[];
      items_found?: string[];
      insider_90d?: { net?: number; bought?: number; sold?: number; forms?: number };
      earnings_8k?: { filed?: string; accession?: string; items?: string };
      guidance?: string[];
      guidance_note?: string | null;
    };
  };
};

export type JobSnapshot = {
  id: string;
  status: "queued" | "running" | "done" | "error" | "stopped";
  created_at: string;
  query: { ticker: string; company: string; type: string; sector: string } | null;
  round1: Record<string, AgentOutput>;
  round2: Debate | null;
  report: Report | null;
  error: string | null;
  meta: Record<string, unknown>;
};

export type Health = {
  ok: boolean;
  provider: string;
  model: string;
  tier: string;
  agent_count: number;
  is_local: boolean;
  demo: boolean;
  model_ready?: boolean;
};

export type HistoryItem = {
  id: string;
  ticker: string;
  verdict: string;
  conviction: number;
  title: string;
  generated_at: string;
  provider_used: string;
  superseded_by?: string | null;
  kind?: string;
};

export type SellIf = { metric: string; operator: string; threshold: number; label: string };

export type HorizonScore = {
  horizon: string;
  status: string;
  due?: string;
  stock_return?: number | null;
  excess_spy?: number | null;
  excess_sector?: number | null;
  stayed_inside?: boolean | null;
};

export type ScoredCall = {
  id: string;
  ticker: string;
  verdict: string;
  title: string;
  summary?: string;
  conviction?: number;
  generated_at?: string;
  last_price?: number | null;
  provider_used?: string;
  sector_etf?: string | null;
  kind?: string;
  update_note?: string;
  horizons: HorizonScore[];
  superseded_by?: string | null;
  supersedes?: string | null;
};

export const AGENT_ORDER = [
  "fundamental",
  "valuation",
  "quality",
  "devil",
  "growth",
  "moat",
  "macro",
  "technical",
  "sentiment",
  "risk",
  "esg",
] as const;
