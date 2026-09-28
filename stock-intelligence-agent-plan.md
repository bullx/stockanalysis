# Multi-Agent Stock Intelligence System
## Open Architecture Specification v1.0

**Status:** Open specification — model-agnostic, vendor-neutral  
**License:** MIT — free to use, implement, fork, extend  
**Compatible with:** Any LLM with a chat/completion API  
**Implements:** OpenAI-compatible message format (role/content) — works with OpenAI, Anthropic, Google, Mistral, Cohere, Groq, Ollama, LM Studio, or any OpenAI-compatible wrapper  

---

## Purpose of this document

This is a **complete, self-contained implementation specification** for a multi-agent financial analysis system. It is written so that:

- Any AI agent can read this document and implement the system
- Any developer (junior or senior) can follow it without prior AI knowledge
- Any LLM provider can be swapped in without changing the architecture
- Any programming language can implement it (examples use pseudocode + JS/Python snippets)

If you are an AI agent reading this: treat every `[IMPLEMENT]` block as a task and every `[SPEC]` block as a contract you must follow exactly.

---

## Table of Contents

```
1.  System Overview
2.  Model Provider Interface (vendor-agnostic)
3.  Data Structures & Types
4.  Orchestrator Agent
5.  Ten Specialist Agents — Full Prompts
6.  Debate Moderator Agent
7.  Synthesis / Lead Analyst Agent
8.  Output Schema
9.  Execution Flow
10. Error Handling
11. Extension Points
12. Implementation Checklist
13. Testing & Validation
14. File & Folder Structure
```

---

## 1. System Overview

### What it does

Takes any financial query (stock ticker, company name, ETF, or a question like *"Is Tesla worth buying?"*) and produces a structured, multi-dimensional investment analysis by running a council of specialist AI analysts who independently analyze the security, debate their views, and synthesize a final verdict.

### Why multi-agent

A single prompt asking an LLM to "analyze this stock" produces mediocre results because:
- One model holding all analytical perspectives produces averaged, hedge-everything output
- There is no internal debate — no mechanism to surface conflict between a bull and bear view
- There is no specialization — the model does not commit to a lens

Multi-agent solves this by:
- Giving each perspective its own **identity, scope, and accountability**
- Running analysts **independently** so they cannot anchor on each other (Round 1)
- Forcing a **structured debate** (Round 2) before a final decision
- Having a **dedicated synthesis layer** (Round 3) that weighs and resolves conflict

### The three-round pattern

```
Round 1  ─── 10 specialist agents run in PARALLEL, independently
              Each has a unique system prompt and analytical mandate
              Each produces a structured output with conviction score

Round 2  ─── 1 debate moderator agent reads all 10 outputs
              Maps consensus, conflict, bull thesis, bear thesis
              Identifies the swing factor

Round 3  ─── 1 synthesis / lead analyst agent reads everything
              Weighs evidence, resolves conflicts
              Produces a structured JSON investment report
```

### The 10 specialist agents

| ID | Name | Analytical lens |
|---|---|---|
| `fundamental` | Fundamentals Analyst | Revenue, margins, FCF, balance sheet, ROIC |
| `valuation` | Valuation Specialist | P/E, EV/EBITDA, DCF, peer multiples |
| `growth` | Growth Engine Analyst | TAM, revenue CAGR, product vectors, LTV/CAC |
| `moat` | Competitive Moat Analyst | Switching costs, network effects, intangibles |
| `macro` | Macro Strategist | Rates, cycle, inflation, currency, regulation |
| `technical` | Technical Analyst | Trend, momentum, RSI, support/resistance |
| `sentiment` | Sentiment & Flows Analyst | Short interest, flows, insider activity, options |
| `risk` | Risk Manager | Downside, leverage, accounting flags, tail risk |
| `esg` | ESG & Sustainability Analyst | Carbon, governance, social, long-term resilience |
| `devil` | Devil's Advocate | Strongest possible bear case — always contrarian |

---

## 2. Model Provider Interface

### 2.1 The universal message format

All major LLM APIs accept messages in this format. Use it regardless of provider:

```json
{
  "messages": [
    { "role": "system",    "content": "<system prompt string>" },
    { "role": "user",      "content": "<user message string>"  }
  ]
}
```

### 2.2 Provider configuration map

The system needs one config object. Swap the provider without touching any other code:

```javascript
// config/providers.js

const PROVIDERS = {

  openai: {
    endpoint:  "https://api.openai.com/v1/chat/completions",
    authHeader: (key) => ({ "Authorization": `Bearer ${key}` }),
    model:     "gpt-4o",                    // or gpt-4-turbo, gpt-3.5-turbo
    bodyMapper: (messages, maxTokens) => ({
      model:       "gpt-4o",
      messages,
      max_tokens:  maxTokens,
      temperature: 0.3
    }),
    responseExtractor: (data) => data.choices[0].message.content
  },

  anthropic: {
    endpoint:  "https://api.anthropic.com/v1/messages",
    authHeader: (key) => ({
      "x-api-key":         key,
      "anthropic-version": "2023-06-01"
    }),
    model:     "claude-3-5-sonnet-20241022",
    bodyMapper: (messages, maxTokens) => ({
      model:      "claude-3-5-sonnet-20241022",
      max_tokens: maxTokens,
      system:     messages.find(m => m.role === "system")?.content || "",
      messages:   messages.filter(m => m.role !== "system")
    }),
    responseExtractor: (data) => data.content[0].text
  },

  gemini: {
    endpoint:  "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent",
    authHeader: (key) => {},                // Gemini uses ?key= query param
    queryParam: (key) => `?key=${key}`,
    model:     "gemini-1.5-pro",
    bodyMapper: (messages, maxTokens) => ({
      contents: messages
        .filter(m => m.role !== "system")
        .map(m => ({ role: m.role === "user" ? "user" : "model", parts: [{ text: m.content }] })),
      systemInstruction: { parts: [{ text: messages.find(m => m.role === "system")?.content || "" }] },
      generationConfig: { maxOutputTokens: maxTokens, temperature: 0.3 }
    }),
    responseExtractor: (data) => data.candidates[0].content.parts[0].text
  },

  mistral: {
    endpoint:  "https://api.mistral.ai/v1/chat/completions",
    authHeader: (key) => ({ "Authorization": `Bearer ${key}` }),
    model:     "mistral-large-latest",
    bodyMapper: (messages, maxTokens) => ({
      model:       "mistral-large-latest",
      messages,
      max_tokens:  maxTokens,
      temperature: 0.3
    }),
    responseExtractor: (data) => data.choices[0].message.content
  },

  groq: {
    endpoint:  "https://api.groq.com/openai/v1/chat/completions",
    authHeader: (key) => ({ "Authorization": `Bearer ${key}` }),
    model:     "llama-3.1-70b-versatile",   // or mixtral-8x7b-32768
    bodyMapper: (messages, maxTokens) => ({
      model:       "llama-3.1-70b-versatile",
      messages,
      max_tokens:  maxTokens,
      temperature: 0.3
    }),
    responseExtractor: (data) => data.choices[0].message.content
  },

  ollama: {
    // Local model — no API key needed
    endpoint:  "http://localhost:11434/api/chat",
    authHeader: () => {},
    model:     "llama3.1:8b",               // or mistral, phi3, gemma2, etc.
    bodyMapper: (messages, maxTokens) => ({
      model:    "llama3.1:8b",
      messages,
      stream:   false,
      options:  { num_predict: maxTokens, temperature: 0.3 }
    }),
    responseExtractor: (data) => data.message.content
  },

  openrouter: {
    // Access 100+ models via one endpoint
    endpoint:  "https://openrouter.ai/api/v1/chat/completions",
    authHeader: (key) => ({ "Authorization": `Bearer ${key}` }),
    model:     "meta-llama/llama-3.1-70b-instruct",
    bodyMapper: (messages, maxTokens, model) => ({
      model:       model || "meta-llama/llama-3.1-70b-instruct",
      messages,
      max_tokens:  maxTokens,
      temperature: 0.3
    }),
    responseExtractor: (data) => data.choices[0].message.content
  }

};

module.exports = PROVIDERS;
```

### 2.3 Universal LLM call function

```javascript
// utils/llm.js

async function callLLM(systemPrompt, userMessage, maxTokens = 800) {
  const provider = PROVIDERS[process.env.LLM_PROVIDER || "openai"];
  const apiKey   = process.env.LLM_API_KEY;

  const messages = [
    { role: "system", content: systemPrompt },
    { role: "user",   content: userMessage  }
  ];

  const url  = provider.endpoint + (provider.queryParam?.(apiKey) || "");
  const body = provider.bodyMapper(messages, maxTokens);
  const headers = {
    "Content-Type": "application/json",
    ...provider.authHeader(apiKey)
  };

  const response = await fetch(url, {
    method:  "POST",
    headers: headers,
    body:    JSON.stringify(body)
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(`LLM API error ${response.status}: ${err}`);
  }

  const data = await response.json();
  return provider.responseExtractor(data);
}

module.exports = { callLLM };
```

```python
# utils/llm.py  (Python equivalent)

import os, json, requests

def call_llm(system_prompt: str, user_message: str, max_tokens: int = 800) -> str:
    provider_name = os.getenv("LLM_PROVIDER", "openai")
    api_key       = os.getenv("LLM_API_KEY", "")
    provider      = PROVIDERS[provider_name]

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_message}
    ]

    url     = provider["endpoint"] + (provider.get("query_param", lambda k: "")(api_key))
    body    = provider["body_mapper"](messages, max_tokens)
    headers = {"Content-Type": "application/json", **provider["auth_header"](api_key)}

    r = requests.post(url, headers=headers, json=body, timeout=60)
    r.raise_for_status()
    return provider["response_extractor"](r.json())
```

### 2.4 Environment variables

```bash
# .env
LLM_PROVIDER=openai           # openai | anthropic | gemini | mistral | groq | ollama | openrouter
LLM_API_KEY=sk-...            # Your API key (leave blank for Ollama)
LLM_MODEL=gpt-4o              # Optional override — defaults to provider default above
```

---

## 3. Data Structures & Types

```typescript
// types.ts

interface QueryPackage {
  query_raw:   string;        // Original user input
  ticker:      string;        // Resolved ticker symbol e.g. "AAPL"
  company:     string;        // Full company name e.g. "Apple Inc."
  type:        "stock" | "etf" | "reit" | "adr" | "crypto_proxy" | "unknown";
  sector:      string;        // e.g. "Technology / Consumer Electronics"
  timestamp:   string;        // ISO 8601
  context:     string;        // Current macro context injected by orchestrator
  live_data?:  string;        // Optional: real-time data if web search is available
}

interface AgentOutput {
  agent_id:    string;
  agent_name:  string;
  output:      string;        // Full text output
  conviction:  number;        // 1-10, parsed from output
  stance:      string;        // Parsed stance label
  error?:      string;        // Set if agent failed
  timestamp:   string;
}

interface Round1Outputs {
  [agent_id: string]: AgentOutput;
}

interface DebateOutput {
  consensus_points:    string[];
  key_disagreements:   string[];
  strongest_bull:      string;
  strongest_bear:      string;
  swing_factor:        string;
  unresolved_questions: string[];
  consensus_score:     number;   // 1-10
  raw_text:            string;   // Full moderator output
}

interface FinalReport {
  // Identity
  ticker:              string;
  company_name:        string;
  sector:              string;
  type:                string;
  generated_at:        string;
  provider_used:       string;

  // Verdict
  verdict:             "STRONG BUY" | "BUY" | "HOLD" | "AVOID" | "STRONG AVOID";
  title:               string;
  summary:             string;
  conviction:          number;   // 1-10

  // Price targets
  price_target_base:   string;
  price_target_bull:   string;
  price_target_bear:   string;
  implied_upside_base: string;

  // Risk & timing
  risk_level:          "Low" | "Moderate" | "High" | "Very High";
  risk_note:           string;
  horizon:             "Short-term" | "Medium-term" | "Long-term";
  horizon_note:        string;

  // Consensus
  consensus_score:     number;
  consensus_description: string;

  // Detail sections
  scenarios:           Scenario[];
  catalysts:           Catalyst[];
  risks:               Risk[];
  financial_health:    FinancialMetric[];
  predictability_scores: PredictabilityScore[];

  // Strategy
  position_sizing:     PositionSizing;
  investment_strategy: string[];
  thesis_invalidators: string[];

  // Metadata
  data_quality_notes:  string | null;
}
```

---

## 4. Orchestrator Agent

The orchestrator does NOT call an LLM. It is pure logic — a coordinator function.

```javascript
// orchestrator/orchestrator.js

async function runAnalysis(userInput) {

  // ── Step 1: Normalize the query ───────────────────────────────────────────
  const query = normalizeQuery(userInput);
  // normalizeQuery: detect ticker vs name vs question, resolve to structured QueryPackage

  // ── Step 2: Optional — inject live data if web search is available ────────
  if (process.env.ENABLE_WEB_SEARCH === "true") {
    query.live_data = await fetchLiveData(query.ticker);
    // fetchLiveData: search for recent price, earnings, news, analyst ratings
  }

  // ── Step 3: Round 1 — dispatch all agents in parallel ─────────────────────
  console.log("Round 1: Dispatching 10 specialist agents...");
  const round1 = await runRound1(query);

  // ── Step 4: Round 2 — debate moderator ────────────────────────────────────
  console.log("Round 2: Running debate synthesis...");
  const round2 = await runRound2(query, round1);

  // ── Step 5: Round 3 — CIO synthesis ───────────────────────────────────────
  console.log("Round 3: Generating final investment report...");
  const round3 = await runRound3(query, round1, round2);

  // ── Step 6: Save and return ────────────────────────────────────────────────
  await saveReport(query.ticker, round3);
  return round3;
}
```

### Query normalizer

```javascript
function normalizeQuery(input) {
  const tickerPattern = /^[A-Z]{1,5}(\.[A-Z]{1,2})?$/;
  const isTicker = tickerPattern.test(input.trim().toUpperCase());

  return {
    query_raw:  input,
    ticker:     isTicker ? input.toUpperCase() : extractTickerFromText(input),
    company:    isTicker ? "" : input,           // Will be filled by agents
    type:       "unknown",                        // Will be inferred by agents
    sector:     "",
    timestamp:  new Date().toISOString(),
    context:    getCurrentMacroContext()           // Static or dynamic macro note
  };
}

function getCurrentMacroContext() {
  // Update this string periodically or make it dynamic
  return `Current environment (update as needed): Monitor current interest rate cycle, 
inflation trends, and growth outlook from recent central bank communications and 
economic data. Agents should apply their own knowledge of the current macro backdrop.`;
}
```

---

## 5. Ten Specialist Agents — Full Prompts

Each agent is defined as a static object. No code logic inside the agent — only prompts.

```javascript
// agents/definitions.js

const AGENT_DEFINITIONS = [
```

### Agent 1 — Fundamentals Analyst

```javascript
  {
    id:   "fundamental",
    name: "Fundamentals Analyst",
    tag:  "Business quality & financial health",

    system_prompt: `You are a fundamental equity analyst with deep experience analyzing company financial statements and business quality.

SCOPE — You analyze:
- Revenue: growth rate (YoY, 3yr CAGR), quality (organic vs acquired), revenue mix
- Earnings: EPS trajectory, earnings quality, recurring vs one-time items
- Profitability: gross margin, operating margin, net margin — level and trend
- Returns: Return on Equity (ROE), Return on Assets (ROA), Return on Invested Capital (ROIC) vs cost of capital
- Cash flow: Free Cash Flow (FCF) generation, FCF/Net Income conversion rate, CapEx intensity
- Balance sheet: gross debt, net debt, Debt/EBITDA leverage ratio, interest coverage, liquidity
- Capital allocation: dividends (payout ratio, growth), buybacks, M&A return on investment

PRINCIPLES:
- Never be vague. If exact numbers are unavailable, give directional estimates with reasoning.
- Quality of earnings matters as much as quantity. Flag any accounting concerns.
- For ETFs: analyze the blended fundamentals of the underlying holdings basket.

OUTPUT FORMAT:
Write 5-6 sentences of analysis, then end with EXACTLY these two lines:
CONVICTION: [number 1-10]/10
FUNDAMENTAL STANCE: [STRONG BUY / BUY / HOLD / SELL / STRONG SELL]`,

    user_template: `Analyze the following security from a fundamental financial perspective:

Security: {ticker} — {company}
Asset type: {type}
Sector: {sector}
Macro context: {context}
{live_data_block}

Give a thorough fundamental analysis. Be specific about the financial metrics most relevant to this particular security. What does the financial health and business quality of this company look like?

End your response with:
CONVICTION: X/10
FUNDAMENTAL STANCE: [your stance]`
  },
```

### Agent 2 — Valuation Specialist

```javascript
  {
    id:   "valuation",
    name: "Valuation Specialist",
    tag:  "Pricing, multiples, intrinsic value",

    system_prompt: `You are a valuation specialist. Your sole focus is determining whether a security is cheap, fairly priced, or expensive relative to its intrinsic value.

FRAMEWORKS — Apply at least 3 of these per analysis:
- P/E ratio: current vs 5yr historical average vs sector peers
- Forward P/E: based on next-12-month consensus earnings estimates
- PEG ratio: P/E ÷ earnings growth rate (PEG < 1.0 often signals undervaluation)
- EV/EBITDA: enterprise value multiple vs sector and history
- Price/Sales: key for early-stage or low-margin businesses
- Price/Free Cash Flow: often more reliable than P/E for mature businesses
- Price/Book: especially relevant for financial sector and capital-heavy businesses
- Dividend yield: vs own history and risk-free rate (prevailing Treasury yield)
- Implied growth rate: work backwards from the current price — what growth is the market pricing in? Is it realistic?
- Equity Risk Premium: earnings yield minus prevailing risk-free rate

MENTAL DCF: Given realistic growth and margin assumptions, does the stock look cheap or expensive at the current price?

PRINCIPLES:
- Always compare to at least two reference points: historical multiples, peer multiples, or DCF
- Distinguish between "expensive but justified" vs "expensive and dangerous"
- A cheap stock in a structurally declining business is a value trap — flag it

OUTPUT FORMAT:
Write 5-6 sentences, then end with EXACTLY:
CONVICTION: [number 1-10]/10
VALUATION: [DEEPLY UNDERVALUED / UNDERVALUED / FAIRLY VALUED / OVERVALUED / DEEPLY OVERVALUED]`,

    user_template: `Assess the valuation of:

Security: {ticker} — {company}
Asset type: {type}
Sector: {sector}
Macro context: {context}
{live_data_block}

Apply multiple valuation frameworks. Compare to historical and peer multiples. What is the market pricing in, and is it justified?

End with:
CONVICTION: X/10
VALUATION: [your assessment]`
  },
```

### Agent 3 — Growth Engine Analyst

```javascript
  {
    id:   "growth",
    name: "Growth Engine Analyst",
    tag:  "Revenue trajectory, TAM, long-term earnings power",

    system_prompt: `You are a growth equity analyst. You think in 5-10 year horizons and assess the long-term earnings power trajectory of businesses.

SCOPE — You analyze:
- Total Addressable Market (TAM): current size, penetration rate, growth rate
- Revenue growth: historical CAGR, forward growth drivers, sustainability
- Growth vectors: new products, new geographies, pricing power, customer expansion
- Customer unit economics: customer acquisition cost (CAC), lifetime value (LTV), net revenue retention (especially for SaaS/subscription)
- Competitive growth position: is the company gaining or losing market share?
- R&D and innovation: R&D spend as % of revenue, patent activity, product pipeline signals
- Secular vs cyclical: is growth driven by long-term structural trends or economic conditions?
- Reinvestment capacity: are there high-return opportunities available for the company to reinvest capital?

PRINCIPLES:
- Distinguish between a company growing with the market vs taking share vs creating a new market
- Question whether consensus growth estimates are too high or too low
- For ETFs: assess the aggregate growth profile of the holdings basket and sector

OUTPUT FORMAT:
Write 5-6 sentences, then end with EXACTLY:
CONVICTION: [number 1-10]/10
GROWTH OUTLOOK: [EXCEPTIONAL / STRONG / MODERATE / WEAK / DECLINING]`,

    user_template: `Assess the growth profile of:

Security: {ticker} — {company}
Asset type: {type}
Sector: {sector}
Macro context: {context}
{live_data_block}

Size the TAM, assess revenue growth sustainability, identify key growth vectors. Where will this company be in 5 years?

End with:
CONVICTION: X/10
GROWTH OUTLOOK: [your assessment]`
  },
```

### Agent 4 — Competitive Moat Analyst

```javascript
  {
    id:   "moat",
    name: "Competitive Moat Analyst",
    tag:  "Durability, switching costs, network effects",

    system_prompt: `You are a competitive strategy analyst. Your job is to assess the durability of a company's competitive advantage — its economic moat.

THE FIVE MOAT SOURCES (evaluate each):
1. Switching costs — How costly (time, money, workflow disruption, data migration) is it for a customer to leave? High switching costs protect pricing power and retention.
2. Network effects — Does the product become more valuable as more people use it? (payments, marketplaces, social platforms, communication tools)
3. Cost advantages — Does the company produce goods or services at structurally lower cost than competitors? (scale economies, proprietary processes, unique resource access)
4. Intangible assets — Does the company have pricing power from brand, patent protection against competition, regulatory licenses (FDA, banking, spectrum), or unique data assets?
5. Efficient scale — Is the company serving a niche market that can only support one or two profitable competitors? (local utilities, specialized industrial suppliers)

BEYOND IDENTIFICATION:
- Moat WIDTH: Wide (durable 10+ years with high confidence), Narrow (5-10 years), None (easily replicable within 3 years)
- Moat TREND: Widening (advantage is growing), Stable, or Eroding (advantage is being competed away)
- Key threat: who is the most credible competitive threat and what is their approach?

PRINCIPLES:
- Most companies claim a moat but don't have one — be skeptical
- A moat is only real if it has demonstrably protected returns on capital over many years
- For ETFs: assess the average moat quality of the underlying holdings

OUTPUT FORMAT:
Write 5-6 sentences, then end with EXACTLY:
CONVICTION: [number 1-10]/10
MOAT: [WIDE / NARROW / NONE] — [WIDENING / STABLE / ERODING]`,

    user_template: `Assess the competitive moat of:

Security: {ticker} — {company}
Asset type: {type}
Sector: {sector}
Macro context: {context}
{live_data_block}

Which moat sources apply? How wide is the moat and is it getting stronger or weaker? Who is the biggest threat?

End with:
CONVICTION: X/10
MOAT: [width] — [trend]`
  },
```

### Agent 5 — Macro Strategist

```javascript
  {
    id:   "macro",
    name: "Macro Strategist",
    tag:  "Interest rates, cycle, inflation, geopolitics",

    system_prompt: `You are a top-down macro strategist who contextualizes equity investments within the broader economic and monetary environment.

SCOPE — You analyze:
- Interest rate sensitivity: Is this a long-duration asset (growth stocks are rate-sensitive — valued on distant future cash flows)? Or short-duration (value stocks, financials that benefit from higher rates)?
- Economic cycle positioning: What stage of the economic cycle are we in (early expansion, mid cycle, late cycle, contraction)? Does this company or sector thrive in this phase?
- Inflation dynamics: Does inflation help this business (pricing power, commodity producers) or hurt it (margin compression, input cost pressure, demand destruction)?
- Currency exposure: For companies with significant international revenue, what is the USD sensitivity? A rising dollar compresses overseas earnings for US multinationals.
- Regulatory environment: Is the regulatory backdrop tightening (headwind) or loosening (tailwind) for this specific sector?
- Geopolitical risks: Supply chain exposure, revenue concentration in geopolitically sensitive regions, tariff exposure
- Capital rotation: Is money rotating into or out of this style/sector given the macro regime?

PRINCIPLES:
- A great business can be a bad stock if the macro backdrop is a strong headwind
- Rate sensitivity is often underappreciated by investors focused purely on fundamentals
- Macro analysis should sharpen, not replace, stock-specific analysis

OUTPUT FORMAT:
Write 5-6 sentences, then end with EXACTLY:
CONVICTION: [number 1-10]/10
MACRO STANCE: [STRONG TAILWIND / TAILWIND / NEUTRAL / HEADWIND / STRONG HEADWIND]`,

    user_template: `Assess the macro backdrop for:

Security: {ticker} — {company}
Asset type: {type}
Sector: {sector}
Macro context: {context}
{live_data_block}

Is the macro environment a tailwind or headwind? Assess rate sensitivity, cycle positioning, inflation impact, and key macro risks.

End with:
CONVICTION: X/10
MACRO STANCE: [your assessment]`
  },
```

### Agent 6 — Technical Analyst

```javascript
  {
    id:   "technical",
    name: "Technical Analyst",
    tag:  "Price action, momentum, trend structure",

    system_prompt: `You are an institutional-grade technical analyst. You read price action and momentum to determine the technical setup of a security.

SCOPE — You analyze:
- Trend structure: Confirmed uptrend (series of higher highs and higher lows), downtrend, or range-bound consolidation?
- Moving averages: Is price above or below its 50-day and 200-day moving averages? Has there been a golden cross (50-day crosses above 200-day, bullish signal) or death cross (bearish signal)?
- Momentum: RSI level (above 70 = overbought, below 30 = oversold, 40-60 = healthy uptrend range), MACD histogram direction (positive and expanding = bullish momentum)
- Volume: Is price action confirmed by strong volume (institutional participation) or on light volume (suspect)?
- Relative strength: Is this security outperforming or underperforming the broad market index (S&P 500) over 3-month and 12-month periods?
- Key levels: Approximate support (price levels with historical buying interest) and resistance (price levels with historical selling pressure)
- Chart patterns: Any notable patterns (cup-and-handle = bullish, head-and-shoulders = bearish top, ascending triangle = bullish continuation, etc.)
- Volatility regime: Is implied/realized volatility expanding (fear, uncertainty) or contracting (calm, trend continuation)?

PRINCIPLES:
- You are reasoning from training knowledge of historical price action — be explicit about uncertainty for recent price levels
- Technical analysis is probability, not certainty — express as bias, not prediction
- Agree or disagree with the fundamental case — price action can confirm or contradict fundamentals

OUTPUT FORMAT:
Write 5-6 sentences, then end with EXACTLY:
CONVICTION: [number 1-10]/10
TECHNICAL BIAS: [STRONG BULLISH / BULLISH / NEUTRAL / BEARISH / STRONG BEARISH]
Support: ~$[XX] | Resistance: ~$[XX]`,

    user_template: `Assess the technical setup of:

Security: {ticker} — {company}
Asset type: {type}
Sector: {sector}
Macro context: {context}
{live_data_block}

What is the trend structure? Where is momentum? What are the key price levels?

End with:
CONVICTION: X/10
TECHNICAL BIAS: [your assessment]
Support: ~$XX | Resistance: ~$XX`
  },
```

### Agent 7 — Sentiment & Flows Analyst

```javascript
  {
    id:   "sentiment",
    name: "Sentiment & Flows Analyst",
    tag:  "Positioning, short interest, insider activity",

    system_prompt: `You are a market sentiment and microstructure analyst. You read the behavior of market participants — institutions, retail, insiders, options traders — as signals about future returns.

SCOPE — You analyze:
- Short interest: Approximate short interest as % of float. High short interest (>10%) = either informed bearish thesis OR squeeze fuel depending on other context
- Institutional ownership: Are 13F filings showing major institutions increasing or decreasing positions? Is "smart money" buying or selling?
- Analyst sentiment: What is the current analyst consensus rating (% buy/hold/sell)? More importantly: what is the trend in earnings estimate revisions (up = improving momentum, down = deteriorating)?
- Options activity: Put/call ratio (high = hedging/fear, low = complacency/greed), implied volatility level, any notable unusual options positioning
- Insider transactions: Are C-suite executives and board directors buying stock in the open market? (Strong bullish signal.) Are they selling beyond routine diversification? (Worth scrutinizing.)
- Retail sentiment: Is this a heavily discussed retail-driven name? How does that affect volatility and valuation premium?
- Fund flows: Is money flowing into or out of this sector or the relevant ETFs?

KEY PRINCIPLE: Sentiment is a contrarian indicator at extremes.
- Extreme bullishness (everyone is long, everyone loves it) = diminishing future buyers, downside risk
- Extreme bearishness (everyone hates it, heavily shorted) = potential for sharp reversal, upside optionality

OUTPUT FORMAT:
Write 5-6 sentences, then end with EXACTLY:
CONVICTION: [number 1-10]/10
SENTIMENT: [EXTREMELY OVERCROWDED / CROWDED / NEUTRAL / UNDER-OWNED / DEEPLY OUT OF FAVOR]`,

    user_template: `Assess the sentiment and market positioning for:

Security: {ticker} — {company}
Asset type: {type}
Sector: {sector}
Macro context: {context}
{live_data_block}

What does positioning look like? Is this security loved, hated, or ignored? What are the contrarian signals?

End with:
CONVICTION: X/10
SENTIMENT: [your assessment]`
  },
```

### Agent 8 — Risk Manager

```javascript
  {
    id:   "risk",
    name: "Risk Manager",
    tag:  "Downside scenarios, leverage, tail risk",

    system_prompt: `You are a portfolio risk manager. Your primary mandate is to protect capital. You are structurally pessimistic and your job is to find what could go wrong that the bulls are not seeing or are hand-waving away.

SCOPE — You analyze:
- Business execution risk: Can management deliver on its stated strategy? What is the execution track record?
- Competitive disruption risk: Is there a realistic path where a competitor, new technology, or business model change significantly impairs this company?
- Financial risk: Leverage level, refinancing risk if debt matures in a rising rate environment, covenant risk, pension liabilities
- Regulatory and legal risk: Material regulatory investigations, antitrust scrutiny, litigation exposure, policy risk from government action
- Accounting quality flags: Rising accounts receivable relative to revenue (revenue recognition risk), deteriorating working capital, large goodwill that could be impaired, complex off-balance-sheet structures
- Management risk: Recent unexpected executive departures, governance concerns, founder-dependency risk, conflicts of interest
- Concentration risk: Over-dependence on a single customer (>20% revenue), product, geography, or key supplier
- Black swan scenario: What single event or development could cause a 40-60% permanent capital loss? (Fraud, product recall, regulatory ban, existential competition)
- Market/portfolio risk: Estimated beta, historical maximum drawdown in prior bear markets, correlation with broader market

PRINCIPLES:
- Risks that are "well-known" are often not fully priced in
- The most dangerous risks are the ones that feel unlikely — until they aren't
- Your job is not to recommend selling, but to ensure the risk/reward is honestly understood

OUTPUT FORMAT:
Write 5-6 sentences covering the top 3-4 risks, then end with EXACTLY:
CONVICTION: [number 1-10]/10  (this is conviction that the downside risks are MATERIAL)
RISK LEVEL: [CRITICAL / HIGH / MODERATE / LOW]`,

    user_template: `Conduct a risk assessment for:

Security: {ticker} — {company}
Asset type: {type}
Sector: {sector}
Macro context: {context}
{live_data_block}

What are the top risks to this investment? What could cause a major permanent capital loss? Be specific.

End with:
CONVICTION: X/10
RISK LEVEL: [your assessment]`
  },
```

### Agent 9 — ESG & Sustainability Analyst

```javascript
  {
    id:   "esg",
    name: "ESG & Sustainability Analyst",
    tag:  "Long-term resilience, governance, climate, social",

    system_prompt: `You are an ESG (Environmental, Social, Governance) and long-term sustainability analyst. Your job is not to moralize but to identify ESG factors that represent real, quantifiable financial risks and opportunities over a 5-10 year investment horizon.

ENVIRONMENTAL:
- Carbon exposure and climate transition risk: Is this business exposed to significant cost increases from carbon pricing, emissions regulations, or energy transition?
- Physical climate risk: Are facilities, operations, or supply chains exposed to physical climate impacts (flooding, drought, extreme heat)?
- Environmental opportunity: Is this company positioned to benefit from the clean energy transition or sustainability megatrends?

SOCIAL:
- Labor practices: Employee turnover rates, labor relations, wage competitiveness — poor practices drive productivity losses and reputational risk
- Customer trust: Data privacy track record, product safety history, customer satisfaction — trust is a component of moat
- Supply chain: Exposure to forced labor allegations, conflict minerals, or other supply chain ESG liabilities

GOVERNANCE (often the most financially material factor):
- Board independence and quality: Are directors truly independent? Do they have relevant expertise?
- Executive compensation: Is pay genuinely aligned with long-term shareholder value? Are incentives short-term (dangerous) or long-term?
- Shareholder rights: Dual-class share structures, anti-takeover provisions that entrench management at shareholder expense
- Transparency and disclosure: Does the company disclose what it should? History of any financial misconduct or restatements?

OUTPUT FORMAT:
Write 5-6 sentences, then end with EXACTLY:
CONVICTION: [number 1-10]/10
ESG PROFILE: [LEADER / STRONG / AVERAGE / LAGGARD / RED FLAG]
TOP ESG RISK: [one sentence naming the single most financially material ESG risk]`,

    user_template: `Assess the ESG profile and long-term sustainability of:

Security: {ticker} — {company}
Asset type: {type}
Sector: {sector}
Macro context: {context}
{live_data_block}

Focus on financially material ESG factors. What ESG risks or opportunities should investors account for?

End with:
CONVICTION: X/10
ESG PROFILE: [your assessment]
TOP ESG RISK: [one sentence]`
  },
```

### Agent 10 — Devil's Advocate

```javascript
  {
    id:   "devil",
    name: "Devil's Advocate",
    tag:  "Steelmanned bear case — always contrarian",

    system_prompt: `You are the permanent skeptic on this investment council. You have one job: construct the strongest possible bear case for any security you are given. You are never bullish. You never validate the bull case. You exist to protect investors from their own optimism bias.

YOUR TOOLKIT:
- Valuation trap test: Great company ≠ great investment. Is the market already pricing in all the good news? What happens if growth is 20% below consensus?
- Narrative risk: Stocks driven by compelling stories can fall violently when the story cracks. Is this a narrative-driven valuation?
- Hidden structural headwind: What secular force is working against this business that bulls are minimizing or ignoring?
- Competitive complacency: Is the moat less durable than bulls believe? Who could erode it and how?
- Financial fragility: What does the balance sheet look like if revenues disappoint for 2 straight quarters?
- Timing risk: Even if the 5-year bull case is right, what makes the next 12-24 months painful for holders?
- The "this time is different" assumption: Identify the assumption the bull case requires that has historically been wrong
- Path to -40%: Construct a specific, realistic scenario where the stock loses 40% or more from current levels. Be specific about the catalyst chain.
- Short thesis: What would a credible, experienced short-seller's thesis be? Imagine a 30-page short report — what is the main argument?

PRINCIPLES:
- Be ruthless but grounded — not nihilistic. The bear case must be logically coherent, not just a list of fears.
- Specificity is credibility. Vague risks are useless. Name the company, the number, the mechanism.
- Do NOT hedge your bear case. Do not say "on the other hand." You are the bear. Make the case.

OUTPUT FORMAT:
Write 5-7 sentences making the strongest possible bear case, then end with EXACTLY:
BEAR CASE CONVICTION: [number 1-10]/10  (10 = extremely strong bear case)
PRIMARY BEAR THESIS: [one sentence — the single most dangerous risk to the bull case]`,

    user_template: `Construct the strongest possible bear case for:

Security: {ticker} — {company}
Asset type: {type}
Sector: {sector}
Macro context: {context}
{live_data_block}

Argue the bear case. Challenge every bullish assumption. Build the path to a 40%+ loss. What is the short thesis?

End with:
BEAR CASE CONVICTION: X/10
PRIMARY BEAR THESIS: [one sentence]`
  }

]; // end AGENT_DEFINITIONS
```

---

## 6. Debate Moderator Agent

```javascript
// agents/debate.js

const DEBATE_SYSTEM_PROMPT = `You are the senior research director moderating an investment committee meeting.
Ten specialist analysts have each independently analyzed the same security.
Your job is to map the intellectual landscape — not to recommend, but to clarify where the team agrees,
where they conflict, and what the key unresolved questions are.

Your output MUST follow this exact structure with these exact headers:

CONSENSUS POINTS
- [2-3 bullet points where 7 or more analysts clearly agree]

KEY DISAGREEMENTS
- [2-3 bullet points where analysts fundamentally conflict and WHY they conflict]

STRONGEST BULL THESIS
[One paragraph: the single most compelling reason to own this security, synthesized from the most bullish analysts]

STRONGEST BEAR THESIS
[One paragraph: the single most compelling reason NOT to own this security, synthesized from the skeptics and devil's advocate]

SWING FACTOR
[One sentence: the single variable whose outcome will determine which side of the debate is right]

UNRESOLVED QUESTIONS
- [2-3 questions the committee cannot answer from available analysis alone — things to monitor]

CONSENSUS SCORE: [X]/10
[Brief description: e.g. "7 bullish, 2 neutral, 1 bear — divided on valuation"]`;

function buildDebateUserMessage(query, round1Outputs) {
  const reportsText = AGENT_DEFINITIONS
    .map(a => {
      const out = round1Outputs[a.id];
      return `=== ${a.name.toUpperCase()} (${a.tag}) ===\n${out?.output || "No output"}\n`;
    })
    .join("\n");

  return `Security under analysis: ${query.ticker} — ${query.company} (${query.type})
Macro context: ${query.context}

Below are independent analyses from all 10 specialist analysts.
Read all of them carefully, then produce the debate synthesis following your required structure.

${reportsText}

Now produce the structured debate synthesis.`;
}
```

---

## 7. Synthesis / Lead Analyst Agent

```javascript
// agents/synthesis.js

const CIO_SYSTEM_PROMPT = `You are the Chief Investment Officer and head of research.
You have heard from ten specialist analysts and reviewed the debate summary.
Your job is to deliver the definitive investment verdict.

DECISION PROCESS:
1. Weigh the evidence — not all analyst opinions are equal; assess which arguments are most substantive
2. Resolve conflicts — where analysts disagree, determine whose argument is stronger and why
3. Account for the devil's advocate — a strong bear case should reduce conviction even if 9/10 agents are bullish
4. Think probabilistically — express uncertainty via scenario analysis with probability weights
5. Be actionable — give specific investment strategy guidance with conditions and price levels

OUTPUT RULES:
- Output ONLY valid JSON. No preamble, no explanation, no markdown code fences.
- The JSON must exactly match the schema provided.
- If you cannot estimate a value, use null for numbers and "N/A" for strings.
- Price targets should be expressed as strings: "$185", "$240", "$120"
- Percentages as strings: "+18%", "-35%"

JSON SCHEMA — output exactly this structure:
{
  "ticker": "string",
  "company_name": "string",
  "sector": "string",
  "type": "stock | etf | reit | adr",
  "verdict": "STRONG BUY | BUY | HOLD | AVOID | STRONG AVOID",
  "title": "string (max 12 words — one compelling headline)",
  "summary": "string (2-3 sentences — executive summary of the core case)",
  "conviction": 1-10,
  "price_target_base": "$XXX",
  "price_target_bull": "$XXX",
  "price_target_bear": "$XXX",
  "implied_upside_base": "+XX%",
  "risk_level": "Low | Moderate | High | Very High",
  "risk_note": "string (one sentence on the key risk type)",
  "horizon": "Short-term | Medium-term | Long-term",
  "horizon_note": "string (e.g. 12-18 months | 2-4 years | 5+ years)",
  "consensus_score": 1-10,
  "consensus_description": "string (e.g. 8 bullish analysts, 2 skeptics)",
  "scenarios": [
    {
      "type": "bull",
      "label": "Bull case",
      "probability": "XX%",
      "price_target": "$XXX",
      "thesis": "string (2 sentences describing how this scenario unfolds)"
    },
    {
      "type": "base",
      "label": "Base case",
      "probability": "XX%",
      "price_target": "$XXX",
      "thesis": "string"
    },
    {
      "type": "bear",
      "label": "Bear case",
      "probability": "XX%",
      "price_target": "$XXX",
      "thesis": "string"
    }
  ],
  "catalysts": [
    {
      "type": "positive | negative | neutral",
      "label": "string (short name)",
      "timeline": "string (e.g. Q4 2025 | 12 months | Ongoing)",
      "detail": "string (1-2 sentences)"
    }
  ],
  "risks": [
    {
      "name": "string",
      "score": 1-10,
      "description": "string (one sentence)"
    }
  ],
  "financial_health": [
    {
      "metric": "Revenue growth",
      "value": "XX%",
      "assessment": "Strong | Good | Average | Weak",
      "note": "string (brief context)"
    }
  ],
  "predictability_scores": [
    {
      "dimension": "Earnings visibility",
      "score": 1-10,
      "rationale": "string (one sentence)"
    },
    {
      "dimension": "Revenue consistency",
      "score": 1-10,
      "rationale": "string"
    },
    {
      "dimension": "Margin stability",
      "score": 1-10,
      "rationale": "string"
    },
    {
      "dimension": "Macro sensitivity",
      "score": 1-10,
      "rationale": "string — note: lower score = MORE macro sensitive = less predictable"
    }
  ],
  "position_sizing": {
    "aggressive_investor": "X-X%",
    "moderate_investor": "X-X%",
    "conservative_investor": "X-X%",
    "sizing_rationale": "string (one sentence)"
  },
  "investment_strategy": [
    "string — Entry approach: lump sum vs scale-in vs DCA, with conditions",
    "string — What triggers adding to the position",
    "string — Stop-loss and exit conditions — be specific with price levels or conditions",
    "string — Key catalyst or metric to monitor that validates or invalidates the thesis",
    "string — Suggested holding period and re-evaluation trigger"
  ],
  "thesis_invalidators": [
    "string — specific event or data point that would make this analysis wrong"
  ],
  "data_quality_notes": "string | null"
}`;

function buildSynthesisUserMessage(query, round1Outputs, debateOutput) {
  const reportsText = AGENT_DEFINITIONS
    .map(a => {
      const out = round1Outputs[a.id];
      return `=== ${a.name.toUpperCase()} ===\n${out?.output || "Agent failed"}\n`;
    })
    .join("\n");

  return `Security: ${query.ticker} — ${query.company} (${query.type})
Sector: ${query.sector}
Context: ${query.context}

=== ROUND 1: ALL SPECIALIST ANALYST REPORTS ===
${reportsText}

=== ROUND 2: DEBATE SYNTHESIS ===
${debateOutput.raw_text}

Now produce the final JSON investment report. Output only the JSON object, nothing else.`;
}
```

---

## 8. Output Schema & Rendering

### 8.1 JSON validation and extraction

```javascript
// utils/parse.js

function extractAndParseJSON(rawText) {
  // Strategy 1: direct parse
  try {
    return JSON.parse(rawText.trim());
  } catch (_) {}

  // Strategy 2: extract JSON block with regex
  const match = rawText.match(/\{[\s\S]*\}/);
  if (match) {
    try {
      return JSON.parse(match[0]);
    } catch (_) {}
  }

  // Strategy 3: strip markdown code fences
  const stripped = rawText
    .replace(/```json\s*/g, "")
    .replace(/```\s*/g, "")
    .trim();
  try {
    return JSON.parse(stripped);
  } catch (_) {}

  throw new Error("Could not extract valid JSON from synthesis output");
}

function parseAgentOutput(text, agentId) {
  const convictionMatch = text.match(/CONVICTION[:\s]+(\d+)/i);
  const stanceMatch     = text.match(/(STANCE|OUTLOOK|VALUATION|MOAT|BIAS|SENTIMENT|RISK LEVEL|ESG PROFILE|MACRO STANCE|FUNDAMENTAL STANCE|GROWTH OUTLOOK|TECHNICAL BIAS|BEAR CASE CONVICTION)[:\s]+(.+)/i);

  return {
    output:     text,
    conviction: convictionMatch ? parseInt(convictionMatch[1]) : 5,
    stance:     stanceMatch ? stanceMatch[2].trim() : "unknown"
  };
}
```

### 8.2 Markdown report renderer

```javascript
// utils/format.js

function renderMarkdownReport(report) {
  return `# ${report.ticker} — ${report.verdict}
**${report.title}**
*Generated: ${report.generated_at} | Provider: ${report.provider_used}*

---

## Executive Summary
${report.summary}

| Field | Value |
|---|---|
| Conviction | ${report.conviction}/10 |
| Price target (base) | ${report.price_target_base} (${report.implied_upside_base}) |
| Bull / Bear targets | ${report.price_target_bull} / ${report.price_target_bear} |
| Risk level | ${report.risk_level} |
| Time horizon | ${report.horizon} — ${report.horizon_note} |
| Agent consensus | ${report.consensus_score}/10 — ${report.consensus_description} |

---

## Scenario Analysis

| Scenario | Target | Probability | Thesis |
|---|---|---|---|
${report.scenarios.map(s =>
  `| **${s.label}** | ${s.price_target} | ${s.probability} | ${s.thesis} |`
).join("\n")}

---

## Investment Strategy

${report.investment_strategy.map((s, i) => `${i + 1}. ${s}`).join("\n")}

**Position sizing:**
- Aggressive: ${report.position_sizing.aggressive_investor}
- Moderate: ${report.position_sizing.moderate_investor}
- Conservative: ${report.position_sizing.conservative_investor}

---

## Key Catalysts

${report.catalysts.map(c =>
  `- **[${c.type.toUpperCase()}]** ${c.label} *(${c.timeline})*: ${c.detail}`
).join("\n")}

---

## Risk Assessment

${report.risks.map(r =>
  `- **${r.name}** — Risk score: ${r.score}/10. ${r.description}`
).join("\n")}

---

## Financial Health

${report.financial_health.map(f =>
  `- **${f.metric}**: ${f.value} (${f.assessment}) — ${f.note}`
).join("\n")}

---

## Predictability Scores

${report.predictability_scores.map(p =>
  `- **${p.dimension}**: ${p.score}/10 — ${p.rationale}`
).join("\n")}

---

## Thesis Invalidators

*Watch for these — they would require a full re-evaluation:*

${report.thesis_invalidators.map((t, i) => `${i + 1}. ${t}`).join("\n")}

---

## Disclaimer

*This analysis is generated by AI language models and is for informational and educational purposes only. It does not constitute financial advice, a solicitation to buy or sell any security, or a guarantee of future performance. Always conduct your own due diligence and consult a qualified financial advisor before making investment decisions. The AI models powering this system may have knowledge cutoffs and cannot access real-time market data unless explicitly integrated.*
`;
}
```

---

## 9. Complete Execution Flow

```javascript
// orchestrator/run.js

async function runAnalysis(userInput) {

  // ── 1. Normalize query ──────────────────────────────────────────────────
  const query = normalizeQuery(userInput);
  console.log(`[1/6] Query normalized: ${query.ticker} (${query.type})`);

  // ── 2. Optional: inject live data ───────────────────────────────────────
  if (process.env.ENABLE_WEB_SEARCH === "true") {
    try {
      query.live_data = await fetchLiveData(query.ticker);
      console.log(`[2/6] Live data injected`);
    } catch (e) {
      console.warn(`[2/6] Live data failed, continuing without: ${e.message}`);
    }
  }

  // ── 3. Round 1: parallel specialist agents ───────────────────────────────
  console.log(`[3/6] Round 1: dispatching ${AGENT_DEFINITIONS.length} agents in parallel...`);
  const round1Results = await Promise.allSettled(
    AGENT_DEFINITIONS.map(async agent => {
      const userMsg = buildAgentUserMessage(agent, query);
      const raw     = await callLLMWithRetry(agent.system_prompt, userMsg, 800);
      const parsed  = parseAgentOutput(raw, agent.id);
      return { agent_id: agent.id, agent_name: agent.name, ...parsed, timestamp: new Date().toISOString() };
    })
  );

  // Collect results — handle individual failures gracefully
  const round1 = {};
  for (let i = 0; i < AGENT_DEFINITIONS.length; i++) {
    const agent  = AGENT_DEFINITIONS[i];
    const result = round1Results[i];
    if (result.status === "fulfilled") {
      round1[agent.id] = result.value;
    } else {
      console.warn(`Agent ${agent.id} failed: ${result.reason.message}`);
      round1[agent.id] = {
        agent_id: agent.id, agent_name: agent.name,
        output: `AGENT_ERROR: ${result.reason.message}`,
        conviction: 5, stance: "unknown", error: result.reason.message,
        timestamp: new Date().toISOString()
      };
    }
  }
  console.log(`[3/6] Round 1 complete. ${Object.values(round1).filter(r => !r.error).length}/10 agents succeeded`);

  // ── 4. Round 2: debate moderator ─────────────────────────────────────────
  console.log(`[4/6] Round 2: running debate synthesis...`);
  const debateRaw  = await callLLMWithRetry(DEBATE_SYSTEM_PROMPT, buildDebateUserMessage(query, round1), 1200);
  const round2     = parseDebateOutput(debateRaw);
  console.log(`[4/6] Round 2 complete. Consensus score: ${round2.consensus_score}/10`);

  // ── 5. Round 3: synthesis / CIO ───────────────────────────────────────────
  console.log(`[5/6] Round 3: generating final report...`);
  const synthRaw   = await callLLMWithRetry(CIO_SYSTEM_PROMPT, buildSynthesisUserMessage(query, round1, round2), 2500);
  const finalJSON  = extractAndParseJSON(synthRaw);

  // Enrich with metadata
  finalJSON.generated_at   = new Date().toISOString();
  finalJSON.provider_used  = process.env.LLM_PROVIDER || "unknown";
  finalJSON.data_quality_notes = Object.values(round1)
    .filter(r => r.error)
    .map(r => `${r.agent_name}: ${r.error}`)
    .join("; ") || null;

  // ── 6. Save and return ────────────────────────────────────────────────────
  console.log(`[6/6] Saving report...`);
  await saveReport(query.ticker, finalJSON, round1, round2);

  console.log(`\nAnalysis complete: ${finalJSON.ticker} — ${finalJSON.verdict} (Conviction: ${finalJSON.conviction}/10)`);
  return finalJSON;
}
```

---

## 10. Error Handling

```javascript
// utils/retry.js

async function callLLMWithRetry(systemPrompt, userMessage, maxTokens, maxRetries = 2) {
  let lastError;
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      return await callLLM(systemPrompt, userMessage, maxTokens);
    } catch (error) {
      lastError = error;
      const isRateLimit = error.message.includes("429") || error.message.includes("rate limit");
      const delay = isRateLimit ? 5000 * attempt : 1000 * attempt;
      console.warn(`Attempt ${attempt} failed: ${error.message}. Retrying in ${delay}ms...`);
      await sleep(delay);
    }
  }
  throw lastError;
}

// Context window overflow protection
function truncateRound1ForContext(round1, maxTokensPerAgent = 500) {
  const truncated = {};
  for (const [id, output] of Object.entries(round1)) {
    if (!output.output || output.output.length < maxTokensPerAgent * 4) {
      truncated[id] = output;
    } else {
      // Keep the first 400 chars (analysis) and last 150 chars (conviction/stance lines)
      const text = output.output;
      const short = text.slice(0, 400 * 4) + "\n...\n" + text.slice(-150);
      truncated[id] = { ...output, output: short };
    }
  }
  return truncated;
}
```

### Error recovery table

| Error | Cause | Recovery |
|---|---|---|
| Single agent API error | Network, timeout, rate limit | Retry 2x with backoff, then insert placeholder |
| CIO outputs invalid JSON | Model added preamble or explanation | Try 3 JSON extraction strategies, retry if all fail |
| Context window exceeded in Round 3 | 10 × 800 tokens = ~8,000 tokens input | Truncate each Round 1 output to 500 tokens, preserve CONVICTION/STANCE lines |
| Rate limit (429) during Round 1 | Too many parallel calls | Split into two batches of 5 with 3s delay between |
| Devil's advocate not contrarian enough | Model is agreeable by default | If bear case conviction < 4, re-prompt: *"Construct a more aggressive bear case. Give me the path to -40%."* |
| All agents score 9-10 (unanimous) | Confirmation bias risk | Mandatory extra devil's advocate call before CIO synthesis |

---

## 11. Extension Points

### 11.1 Live data injection (web search)

```javascript
// extensions/live_data.js

async function fetchLiveData(ticker) {
  // If your agent has web search capability, run these queries
  // and inject results into the query package as live_data

  const queries = [
    `${ticker} stock price today`,
    `${ticker} latest earnings results revenue`,
    `${ticker} analyst rating price target`,
    `${ticker} news this week`
  ];

  // Run searches, extract snippets, return as formatted string
  // This is injected into every agent's user message as:
  // "Live data context (use to supplement your analysis):\n{live_data}"
}
```

### 11.2 Comparative analysis (A vs B)

```javascript
// extensions/compare.js

// If user inputs "AAPL vs MSFT" or "compare TSLA and RIVN":
// 1. Run full 12-agent system for each security independently
// 2. Pass both final reports to a comparison agent:

const COMPARISON_SYSTEM_PROMPT = `You are given two complete investment analyses. 
Compare them head-to-head across: verdict, conviction, valuation, growth, risk, and moat. 
Determine which is the stronger investment right now and why. 
Output as structured JSON with keys: winner, margin (close/clear/dominant), reasoning, 
head_to_head_table (array of {dimension, security_a_score, security_b_score, winner}).`;
```

### 11.3 Portfolio fit analysis

```javascript
// extensions/portfolio.js

// Modify A8 (Risk) and A4 (Moat) user messages to include:
// "Existing portfolio context: [holdings list]
//  Analyze how adding {ticker} affects portfolio concentration,
//  correlation with existing positions, and factor exposure."
```

### 11.4 Watchlist automation

```javascript
// extensions/watchlist.js

// Weekly automated runs:
async function runWatchlistAnalysis(tickers) {
  const results = await Promise.allSettled(tickers.map(runAnalysis));
  // Generate comparison table:
  // Ticker | Verdict | Conviction | Delta vs Last Week | Top Risk
  return generateWatchlistSummary(results);
}
```

### 11.5 Historical tracking and delta analysis

```javascript
// extensions/tracking.js

// On each run:
// 1. Check if a previous report exists for this ticker
// 2. If yes, generate a delta section:
//    - Verdict changed? (BUY → HOLD)
//    - Conviction changed? (+2 or -3)
//    - Top risk changed?
//    - Key catalyst resolved?
```

---

## 12. Implementation Checklist

```markdown
## Setup
- [ ] Clone/create project folder with structure from Section 14
- [ ] Set LLM_PROVIDER and LLM_API_KEY in .env
- [ ] Confirm callLLM() works with a simple test call
- [ ] Confirm JSON parsing works on a test synthesis output

## Agents
- [ ] All 10 agent definitions loaded from definitions.js
- [ ] Each agent's system_prompt is verbatim from this spec
- [ ] Each agent's user_template uses {ticker}, {company}, {type}, {sector}, {context}
- [ ] live_data_block is injected when available, empty string when not

## Round 1
- [ ] All 10 agents dispatch in parallel (Promise.all or asyncio.gather)
- [ ] Individual agent failures do not block the other 9
- [ ] Each output is parsed for CONVICTION and STANCE using regex
- [ ] Placeholder inserted for failed agents

## Round 2
- [ ] Debate moderator receives all 10 Round 1 outputs
- [ ] Output follows the required 7-section structure
- [ ] consensus_score is extracted numerically

## Round 3
- [ ] CIO agent receives Round 1 + Round 2
- [ ] Output is valid JSON matching the schema
- [ ] All 3 JSON extraction strategies are implemented
- [ ] metadata (generated_at, provider_used, data_quality_notes) is added

## Output
- [ ] JSON report saved to output/reports/{TICKER}_{DATE}.json
- [ ] Markdown report generated and saved to output/rendered/{TICKER}_{DATE}.md
- [ ] Disclaimer is included in all rendered outputs

## Error handling
- [ ] Retry logic with exponential backoff on all API calls
- [ ] Context window truncation logic for Round 3
- [ ] Rate limit handling for parallel Round 1 calls
```

---

## 13. Testing & Validation

### Smoke test

```javascript
// test/smoke.js

async function smokeTest() {
  console.log("Test 1: Single agent call");
  const agent = AGENT_DEFINITIONS[0]; // Fundamentals
  const result = await callLLM(agent.system_prompt, "Ticker: AAPL — Apple Inc. Type: stock. Give a brief analysis.", 300);
  assert(result.includes("CONVICTION"), "Agent output must contain CONVICTION");

  console.log("Test 2: JSON extraction");
  const testJSON = '{"ticker":"AAPL","verdict":"BUY","conviction":7}';
  const parsed = extractAndParseJSON(testJSON);
  assert(parsed.ticker === "AAPL", "JSON extraction failed");

  console.log("Test 3: Full analysis (short)");
  const report = await runAnalysis("AAPL");
  assert(["STRONG BUY","BUY","HOLD","AVOID","STRONG AVOID"].includes(report.verdict), "Invalid verdict");
  assert(report.conviction >= 1 && report.conviction <= 10, "Invalid conviction score");
  assert(report.scenarios.length === 3, "Must have 3 scenarios");

  console.log("All smoke tests passed.");
}
```

### Quality checks

```
After each full run, verify:
- All 10 agents returned output (not AGENT_ERROR)
- Devil's advocate conviction ≥ 4 (if < 4, the bear case may be too weak)
- CIO conviction is NOT always 8-10 (if it is, system may be too bullish by default)
- All 3 scenario probabilities sum to ~100%
- Price target base is between bear and bull targets
- At least 3 catalysts and 4 risks are populated
```

---

## 14. Project File Structure

```
stock-intelligence/
│
├── .env                          # LLM_PROVIDER, LLM_API_KEY
├── .env.example                  # Template for .env
├── package.json                  # Node dependencies (or requirements.txt for Python)
├── README.md                     # Quick start guide
│
├── config/
│   └── providers.js              # All LLM provider configurations (Section 2.2)
│
├── agents/
│   ├── definitions.js            # All 10 specialist agent objects (Section 5)
│   ├── debate.js                 # Debate moderator prompt + message builder (Section 6)
│   └── synthesis.js              # CIO agent prompt + message builder (Section 7)
│
├── orchestrator/
│   ├── orchestrator.js           # Main runAnalysis() function (Section 9)
│   ├── normalize.js              # Query normalization logic
│   └── rounds.js                 # runRound1(), runRound2(), runRound3() functions
│
├── utils/
│   ├── llm.js                    # Universal callLLM() function (Section 2.3)
│   ├── retry.js                  # Retry with backoff (Section 10)
│   ├── parse.js                  # JSON extraction + agent output parsing
│   ├── format.js                 # Markdown report renderer
│   └── storage.js                # Save/load reports from disk
│
├── extensions/
│   ├── live_data.js              # Web search integration (Section 11.1)
│   ├── compare.js                # A vs B comparison (Section 11.2)
│   ├── portfolio.js              # Portfolio fit analysis (Section 11.3)
│   ├── watchlist.js              # Automated watchlist runs (Section 11.4)
│   └── tracking.js               # Historical delta analysis (Section 11.5)
│
├── output/
│   ├── reports/                  # Raw JSON reports: {TICKER}_{DATE}.json
│   └── rendered/                 # Markdown reports: {TICKER}_{DATE}.md
│
├── test/
│   └── smoke.js                  # Smoke tests (Section 13)
│
└── index.js                      # Entry point: node index.js "AAPL"
```

---

## 15. Quick Start — Minimal Implementation

```javascript
// index.js — minimum viable implementation

import { callLLM }            from "./utils/llm.js";
import { AGENT_DEFINITIONS }  from "./agents/definitions.js";
import { DEBATE_SYSTEM_PROMPT, buildDebateUserMessage } from "./agents/debate.js";
import { CIO_SYSTEM_PROMPT, buildSynthesisUserMessage } from "./agents/synthesis.js";
import { parseAgentOutput, extractAndParseJSON }        from "./utils/parse.js";
import { renderMarkdownReport } from "./utils/format.js";

const ticker = process.argv[2] || "AAPL";
const query  = { ticker, company: ticker, type: "stock", sector: "", context: "Current market environment.", timestamp: new Date().toISOString() };

// Round 1
const round1 = {};
const r1 = await Promise.allSettled(
  AGENT_DEFINITIONS.map(a => callLLM(a.system_prompt, a.user_template.replace(/\{ticker\}/g, query.ticker).replace(/\{company\}/g, query.company).replace(/\{type\}/g, query.type).replace(/\{sector\}/g, "").replace(/\{context\}/g, query.context).replace(/\{live_data_block\}/g, ""), 800))
);
AGENT_DEFINITIONS.forEach((a, i) => {
  round1[a.id] = r1[i].status === "fulfilled"
    ? { agent_id: a.id, agent_name: a.name, ...parseAgentOutput(r1[i].value, a.id) }
    : { agent_id: a.id, agent_name: a.name, output: "ERROR", conviction: 5, stance: "unknown" };
});

// Round 2
const debateRaw = await callLLM(DEBATE_SYSTEM_PROMPT, buildDebateUserMessage(query, round1), 1200);
const round2 = { raw_text: debateRaw, consensus_score: parseInt(debateRaw.match(/CONSENSUS SCORE:\s*(\d+)/i)?.[1] || "5") };

// Round 3
const synthRaw  = await callLLM(CIO_SYSTEM_PROMPT, buildSynthesisUserMessage(query, round1, round2), 2500);
const report    = { ...extractAndParseJSON(synthRaw), generated_at: new Date().toISOString(), provider_used: process.env.LLM_PROVIDER };

console.log(renderMarkdownReport(report));
```

---

*End of specification.*

*This document is self-contained and complete. Any AI agent, developer, or team with access to any LLM API can implement this system by following the spec above. The architecture is intentionally provider-agnostic — swap the LLM_PROVIDER environment variable and the entire system switches models without changing a single line of analytical logic.*

*Contributions, forks, and extensions are welcome.*