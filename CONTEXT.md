# Agent handoff — Aurelia Investments

Read this before changing the repo. Brand: Aurelia Investments, a private investment council. Not financial advice. Spec: `stock-intelligence-agent-plan.md`. User-facing explanation: `README.md`.

Windows, PowerShell. API: `uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload` from the repo root. UI: `npm run dev` inside `frontend`, then http://localhost:5173. Vite proxies `/api` to port 8000. Restart the API after any `.env` change. `get_settings()` is cached, and uvicorn reload does not re-read `.env`.

Current `.env` (do not commit): Ollama, `qwen3.6:27b` (tier 1), `LLM_PROVIDER_TYPE=local`, empty `LLM_API_KEY`, `LOCAL_CONTEXT_WINDOW=32768`, `ENABLE_WEB_SEARCH=false`. No `SEC_USER_AGENT` — the user does not want a personal email in the file. Settings then send `Aurelia Investments research@example.com`. Restart the API after any `.env` change.

## Product

One ticker or question becomes three rounds. The default desk is the full council: fundamentals, valuation, growth, moat, macro, technical, sentiment, risk, ESG, earnings quality, and the bear case (11). **Short desk only** on the home form, or a tier-3 model, sits four: fundamentals, valuation, quality, devil. The form sends `lenses: false` for the short desk. The default request sends `lenses: true`. A moderator writes the debate, then a CIO writes the verdict. The investor-facing page is a decision, not an essay. First screen: call, live price vs base target, council chips, price rail, then why the thesis fails. Notes and debate are the audit trail on later tabs.

The live page names the current writer, including the moderator and the CIO. Stop freezes the timer and marks unspoken seats **Stopped**.

The user rejected a dark UI more than once. Keep a light studio. Do not switch the canvas to night mode.

## What data the model actually has

Before any seat writes, `build_fact_sheet` in `backend/app/data/facts.py` gathers:

- Yahoo quote + up to 10 years of daily closes (`data/prices.py`)
- SEC ticker→CIK, `companyfacts` financials, `submissions` (`data/sec.py`)
- Code filings digest: Item split, Risk/MD&A diff, red-flag scan, Form 4 net, 8-K item codes, Exhibit 99.1 guidance excerpts, customer-concentration sentences (`data/filings.py`). `GET /api/facts/{ticker}` stays code-only
- Same-SIC peers with P/E, EV/EBITDA, operating margin, and FCF yield (`data/peers.py`). The SEC atom feed lists `<cik>` tags. A peer is kept only when that CIK maps to a ticker
- After the fact sheet, on a US filing, Round 0 readers in `agents/filings.py` summarize the diff and the guidance excerpts only. They do not receive the full 10-K. Notes are cached under `output/cache/filings_reader/` by accession, model, and a hash of the packet. Tier 3 skips the filings reader and only summarizes guidance when excerpts exist
- FRED macro: 10-year, fed funds, CPI, unemployment (`data/macro.py`)
- Computed metrics, forensic ratios, reverse DCF (`data/metrics.py`, `data/dcf.py`)

The fact-sheet text is pasted into every seat and the CIO. Coverage is `us` (full), `non_us` or `etf` (price only). Numbers without a source stay labelled as the model's opinion. Do not chart invented fundamentals. Last price is Fact; DCF prices are Council math.

Yahoo short names can arrive truncated ("Taiwan Semiconductor Manufactur"). SEC User-Agent is the settings default unless `SEC_USER_AGENT` is set. Cache lives under `output/cache/` (gitignored).

`GET /api/facts/{ticker}` builds the same sheet without running the council.

## How a run works

1. `POST /api/analyze`. Optional body: `company`, `provider`, `model`, `api_key`, `lenses` (default true). Empty provider and model use `.env`. The home form sends company, provider, model, and `lenses`. It does not send a key. Company blank means the quote lookup fills the name. Provider and model blank mean `.env`.
2. Ticker normalize, Yahoo quote, then fact sheet (prices, SEC, FRED, filings digest, peers).
3. Round 1. Local providers run seats one at a time. Cloud providers (`LLM_PROVIDER_TYPE=cloud`, and the provider is not ollama/lmstudio/etc.) can run together. Full desk unless `lenses` is false or the model is tier 3.
4. Round 2 debate, unless tier 3.
5. Round 3 CIO JSON: verdict, targets, risks, size.
6. Job saved to `output/jobs/{id}.json`. Brief saved to `output/reports/`.

SSE: `GET /api/analyze/{id}/stream`. Stop: `POST /api/analyze/{id}/stop`. `LlmGate` in `backend/app/utils/llm.py` closes the in-flight HTTP client so Ollama aborts. Connection errors, timeouts, and HTTP 5xx also stop the rest of the council. Do not continue to the next seat after those.

Seats are told to put the conviction line and the stance line first (`build_agent_user_message`). `frontend/src/lib/stance.ts` shows a score only when the note contains one. A missing call is **Incomplete**, not "unknown", and a default 5/10 is not shown. Ollama calls send `think: false`.

## Models and keys

`detect_tier` in `backend/app/config/model_tiers.py` matches a fixed name list. Unknown names become tier 2. `openai`, `anthropic`, and `gemini` are forced to tier 1 in `run.py`.

| Tier | Seats | Debate | Prompts | Output cap |
|---|---|---|---|---|
| 1 | 11, the full desk | yes | full `definitions.py` | ~1400 tokens |
| 2 | 11, the full desk | yes | `simplified.py` | ~1000 tokens |
| 3 | 4: fundamental, valuation, quality, devil | skipped | simplified, system text injected into the user message | ~400 tokens |

`qwen3.6:27b` is on the tier 1 list. A new `27b` or `70b` tag that is not listed still gets the tier 2 budget. The code does not parse parameter size from the name. Call context length is `LOCAL_CONTEXT_WINDOW` (32768 in the current `.env`), not the unused `context_window` field on the tier. A fact sheet plus a tier-1 prompt does not fit in 8192.

Cloud: set `LLM_PROVIDER`, `LLM_MODEL`, `LLM_PROVIDER_TYPE=cloud`, and `LLM_API_KEY`, then restart the API. Providers that exist: openai, anthropic, gemini, mistral, groq, openrouter, ollama, lmstudio, llamacpp, jan, llamafile, mock. Cursor is not a provider. A Cursor dashboard key starts Cursor cloud agents. It is not a chat-completions key and must not be sent as `LLM_API_KEY`. Grok (xAI) is not wired. `groq` in this repo is Groq, a different company. OpenRouter is the existing way to name many models with one key, including Grok ids such as `x-ai/grok-2`.

## UI

Light studio, not dark. Tokens in `frontend/tailwind.config.js` and `frontend/src/index.css`: page `#E7E8EC`, cards `#FFFFFF`, text `#0F172A`, mute `#475569`, border `#E2E8F0`, CTA `#8B5CF6`, gold text `#B45309`. Fira Sans and Fira Code. Router pages: `Home`, `Live` (`/run/:id`), `Report` (`/report/:id`, `/archive/:id`), `History` (`/history`), `Scorecard` (`/scorecard`), `Watch` (`/watch`), `Ticker` (`/ticker/:ticker`).

The report header shows last price (Fact), base target (Council) with percent versus last, conviction, and risk, plus a freshness line (coverage, price date, latest filing, when the council ran). The Decision tab leads with the reverse-DCF line when FCF exists, then `DecisionDesk`, then a real Yahoo price chart (`PriceChart.tsx`). A **Fact sheet** tab shows the prompt the seats received and, when peers exist, the same-SIC table. Incomplete seats are counted and called out. Dollar amounts that landed in `probability` are treated as the price, and the chance is shown as unset. Size is general guidance. Portfolio percentages are not shown. Archive **Delete** calls `DELETE /api/reports/{id}` and removes that local file. It also drops a watchlist row that pointed at it.

## Still open

The ordered plan and the done/not-done table are in `ROADMAP.md` under **Progress**. Do not rebuild the fact sheet.

The default desk is the full council, including earnings quality. Short desk is a checkbox and sends `lenses: false`. Same-SIC peers and customer-concentration sentences are computed in code. Scorecard horizons stay blank until the month has passed. Archive delete is local only. The app listens on `127.0.0.1` and has no login. Git has no remote. Do not commit `.env` or `output/`.

Still open: the optional hosted weekly scorecard; parse `8b` / `27b` / `70b` from unknown model names; optional xAI provider; no portfolio and no A-vs-B. The number check against the fact sheet is still a coarse scan. A filing header can still be missed. Do not chart model-invented financials. The chart on the brief is Yahoo closes only.

## Paths

- `backend/app/orchestrator/run.py`, `rounds.py` — the three rounds
- `backend/app/utils/llm.py` — HTTP and cancel
- `backend/app/utils/parse.py` — stance, debate, report normalize
- `backend/app/data/` — fact sheet, SEC, filings, peers, scorecard, watch
- `backend/app/agents/filings.py` — diff readers
- `backend/app/agents/update.py` — delta note
- `frontend/src/pages/History.tsx` — archive and delete
- `frontend/src/pages/Scorecard.tsx`, `Watch.tsx`, `Ticker.tsx`
- `scripts/start.ps1`, `scripts/start.sh` — one process on port 8000
- `backend/app/utils/market.py` — quote + ticker search
- `backend/app/config/providers.py`, `model_tiers.py`
- `frontend/src/pages/Report.tsx` — decision header
- `frontend/src/components/DecisionDesk.tsx` — rail and council chips
- `frontend/src/lib/stance.ts` — Incomplete vs a real call
