# Roadmap — from opinion desk to research analyst

Goal: a free, open-source, local-first AI research analyst that helps a person make a better investment decision. It gathers the facts, does the math, argues both sides, remembers what it said, and keeps score. The person decides.

Informational only. Not financial advice.

## How to use this doc

- **Read `CONTEXT.md` and `README.md` first** for the current code layout and how to run the app. This doc is the forward plan; those describe what exists today.
- **Work one phase at a time, in order.** Each phase has a **Done when** line — treat it as the acceptance test before moving on. Do not build later phases on an unverified earlier one.
- **Check progress from git history** (`git log`) and from the snapshot below. The snapshot is the handoff; commits are the proof.
- When starting a phase, expand it into task-level steps first, and verify each against real data before the next.

## Progress (2026-09-27)

Git is local only. Remote later. Current model in `.env`: Ollama `qwen3.6:27b` (tier 1, sequential). Tests: `python -m pytest` from the repo root (36 passing as of this snapshot).

| Phase | Status | What exists | Still open |
|---|---|---|---|
| 0 Groundwork | Done | Git, MIT `LICENSE`, ticker search (`Is Tesla worth buying?` → TSLA), form provider controls sequential/timeout, parser tests | — |
| 1 Fact sheet | Built, not yet judged by a live council | `backend/app/data/`: Yahoo history, SEC facts, FRED, cache, metrics, freshness stamp, coverage, price chart, `GET /api/facts/{ticker}` | User must confirm a brief's Fact sheet tab matches SEC. As-filed keeps first and latest value; live numbers use the latest filing |
| 2 Filings | Diff readers in code, not yet confirmed on qwen | Section split (cross-references are not treated as the Item header), Risk/MD&A diff, red-flag scan, Form 4 net, 8-K item codes, Exhibit 99.1 guidance excerpts. Filings and Earnings readers run on that packet only and are pasted into the other seats | A section can still be missed when the header wording differs. A live `qwen3.6:27b` brief has not been checked to see that Risk and Growth cite the readers |
| 3 What's priced in | Built | Reverse DCF, forensic ratios, four core seats (optional lenses on the form), same-SIC peer multiples, customer-concentration sentences, price correlation on the watchlist | The number check against the fact sheet is still a coarse scan. A section header can still be missed |
| 4 Scorecard | Built | Calls stay in `output/reports/`. Horizons score vs SPY and the sector ETF only after the date. `/scorecard` and `/ticker/:symbol`. Superseded briefs stay | A horizon is blank until that month has passed, so a new install shows no returns yet |
| 5 Watchlist | Built | Checkable `sell_if`, staleness banner, Update Analyst delta note, daily check and desktop notification while the app is open | No email. The model does not run unless you ask for the delta note |
| 6 Release | Built except a hosted weekly board | `scripts/start.ps1` / `start.sh` serve the built UI from the API. Demo preview when no model is installed. Sizing is general guidance. MIT license | Optional public weekly scorecard is not hosted |

**Next human step:** restart the API after `.env` changes, convene one US ticker (`AAPL` or `TSLA`), and read the Fact sheet tab before trusting the CIO. The Fact sheet should show guidance excerpts when Exhibit 99.1 has them, then a Filings reader and an Earnings reader that only summarize that packet. A 27B local run is slow (those two readers, then ten seats, one at a time). `LOCAL_CONTEXT_WINDOW` must be large enough for the fact sheet plus the seat prompt (32768 is the working default to try).

## What "useful" means here

- **Accurate facts.** Every number in a brief can be traced to a source: a filing, a price series, a macro series. This is achievable.
- **Accurate predictions.** Nobody has this, including Wall Street. Futures are written as scenarios with stated assumptions, and the scorecard measures how those scenarios did.
- **Better decisions.** Most losses come from buying on hype, over-concentrating, and ignoring warning signs. The app should make those mistakes harder.

## Principles

1. Code computes, the model interprets, the person decides.
2. Every number has a source. A number with no source is labelled as the model's opinion.
3. The core question is "what is already priced in?", not "is this a good company?". A good company at a rich price still loses money.
4. The future is a set of scenarios built from explicit assumptions, not a single price.
5. Remember every call and keep score. Never overwrite a past call; supersede it and keep the original on the record.
6. Fewer, deeper analyses beat more voices. Extra seats add tokens and false confidence, not edge.
7. Free and local. No paid data, no required account.

## Scope and horizon

- **Unit of analysis is one security** — a stock or ETF. There is no filing for "AI stocks in general", so the fact-based pipeline only grounds per-security work.
- **Funnel any input down to one security.** A ticker is used as-is. A company name or question resolves to a ticker. A theme or sector maps to a sector ETF (`XLK`, `XLE`, ...) and analyzes that. An open macro question ("is the market overvalued?") is out of scope for now.
- **One analysis, two lenses.** The same grounded data answers two questions:
  - **Long-term lens (default, our strength):** fundamentals, reverse DCF, quality of earnings, filings, thesis and invalidation. Horizon: quarters to years.
  - **Short-term lens (labelled low-edge):** real price trend, momentum, volatility, key levels, and dated upcoming catalysts (earnings, ex-dividend). Situational awareness, never "buy here". Framed around risk around events, not entry timing, because overtrading is how retail loses money.
- **Success is not only alpha.** For large, heavily-covered names the council likely has no edge, and the scorecard will show that honestly. Winning means helping the user understand the business and avoid a bad decision. Edge is most plausible on small, under-followed companies.

## Prior art: TradingAgents

`TradingAgents` (open-source, paper-backed) is the closest reference. Lessons folded into this plan:

- **Point-in-time / as-filed data.** Store the filing date with every figure and read data as it stood on a given date, never a later restatement. Stamp our own briefs the same way so the scorecard is honest.
- **Benchmark against the sector, not only SPY.** A chip stock up 20% while chips are up 25% actually lagged.
- Where we differ on purpose: a real web UI, a strictly forward-only scorecard, honesty over backtested returns, and decision-hygiene tools (watchlist, thesis alerts) over trade signals.

## How an analyst works, and where the app stands

| Analyst step | App today | Target |
|---|---|---|
| Gather filings and history | Fact sheet: 10y prices, SEC annuals, FRED, pasted into every seat | Same, plus a human check that the brief matches the filing |
| Read the reports and find what changed | Code digest plus two readers that see only the diff and Exhibit 99.1 excerpts. Not confirmed on a live brief | Risk and Growth seats cite those notes on a real run |
| Build a model | Reverse DCF and bear/base/bull prices in code | Model states whether it believes the implied growth; code stays the calculator |
| Check earnings quality | Forensic ratios computed and pasted | A dedicated seat that interprets those ratios |
| Judge management | ROIC is computed | Buyback timing and debt trajectory as a narrative |
| Compare to peers | SIC maps to a sector ETF | Same-SIC peers with real multiples |
| Variant perception (where I differ from the market) | Reverse DCF is on the brief when FCF exists | CIO headline must quote it; not yet enforced |
| Catalysts | Latest Item 2.02 8-K date when found | Earnings-release guidance text |
| Group and dependency | None | Price correlation (moves-together warning) and filing-based customer concentration (real dependency) |
| Thesis and what would change my mind | Free-text "Sell if" lines | Checkable conditions on real metrics, written before buying |
| Update after new data | None | Update Analyst writes a delta note; old brief is superseded, not overwritten |
| Accountability | None | Forward scorecard vs SPY and the sector ETF |

## Phases

### Phase 0 — Groundwork

- Put the repo under git. Add a license (MIT).
- Resolve questions and company names to tickers through Yahoo search. Today "Is Tesla worth buying?" becomes `IS`.
- Make the provider and model chosen on the form control sequential vs parallel and the timeout. Today both come from `.env`.
- Tests for `backend/app/utils/parse.py` using saved model outputs.

### Phase 1 — Fact sheet (real data layer)

- New package `backend/app/data/`:
  - `prices.py` — Yahoo daily history, up to 10 years.
  - `sec.py` — ticker to CIK, `companyfacts` (financials), `submissions` (filings list, industry code).
  - `macro.py` — FRED series: 10-year Treasury, fed funds, CPI, unemployment.
  - Disk cache under `output/cache/` with a time-to-live per source.
- `metrics.py` computes, in code:
  - Business: revenue growth and 5-year CAGR, gross / operating / net margin, free cash flow, net debt, return on capital.
  - Valuation: P/E, EV/EBITDA, free cash flow yield, versus the company's own history.
  - Price: 50- and 200-day averages, RSI, MACD, 52-week range, maximum drawdown, volatility. These also feed the short-term lens.
- **As-filed stamping.** Every financial figure carries its filing date, so a figure is never shown for a date before it was filed, and a later restatement does not overwrite the first-reported value.
- The fact sheet is pasted into every seat and replaces the placeholder macro sentence.
- **Freshness stamp** on every brief: as-of date, last price, latest filing read, and when the council last ran.
- Every brief states its coverage: US company (full), non-US (price only), ETF (price only).
- The UI charts real history, labelled with its source.

Done when a TSLA run shows real revenue, margins, and multiples, each carries a filing date, and the brief header shows the freshness stamp.

### Phase 2 — Reading the reports (Filings and Earnings analysts)

Two new seats that run first (Round 0). Their digest is pasted into every other seat, next to the fact sheet.

- **Filings Analyst** — 10-K, 10-Q, event 8-Ks, proxy (DEF 14A), Form 4. Call: Improving / Stable / Deteriorating.
- **Earnings Analyst** — latest earnings 8-K (Exhibit 99.1), guidance, optional pasted call transcript. Call: Beat and raise / In line / Miss or cut.

Pipeline (`backend/app/data/filings.py`, `backend/app/agents/filings.py`):

1. Find filings through SEC `submissions` (form, date, accession number, primary document, 8-K item codes).
2. Download from `sec.gov/Archives/edgar/data/{cik}/{accession}/{document}`, strip HTML, split by Item headers.
3. Diff Risk Factors and MD&A against the prior year's filing in code. Only new, removed, and edited paragraphs go to the model.
4. Red-flag scan in code: "material weakness", "going concern", "substantial doubt", "restatement", auditor change (8-K Item 4.01), executive departure (8-K Item 5.02).
5. Insider activity from Form 4: net shares bought or sold by officers and directors over 90 days, excluding option exercises.
6. Chunked reading within the context window: summarize each slice, then combine.
7. Cache digests by accession number under `output/cache/filings/`. A filing is read once.

Output: a Filings Digest — what changed, new risks, guidance, red flags, insider activity, management incentives. Every item cites form, date, and section.

Tier 3: red-flag scan and earnings-release summary only.

Done when a run on a US company shows new risk factors versus last year, the latest guidance, and insider activity, each with a citation, and the Risk and Growth seats refer to them.

### Phase 3 — Numbers you can check, and what's priced in

- Seats cite fact-sheet fields for the numbers they use.
- A validator compares numbers in the notes with the fact sheet and flags mismatches on the brief.
- **Reverse DCF is the report's spine, not a bullet.** Code derives the growth the current price implies; the CIO headline states it plainly ("the price assumes 22%/yr for a decade; history did 12%") and whether the council believes it.
- Valuation model: the model proposes assumptions (growth for years 1–5, terminal growth, margin, discount rate) with reasons. Code runs a DCF and a sensitivity grid. Bull / base / bear prices come from that math.
- **Forensic quality-of-earnings seat** (code-computed, model-interpreted): cash flow vs net income divergence, accruals, share-count dilution, stock-based comp as % of revenue, receivables growth vs sales.
- **Capital-allocation record:** ROIC trend, buyback timing vs price, debt trajectory.
- Peers by SEC industry code, with real multiples side by side.
- **Group view:** price correlation among a user's names as a "these move together" concentration warning, kept separate from filing-disclosed customer concentration, which is the only thing labelled real dependency.
- **Consolidate the ten seats into fewer, deeper ones.** Fundamentals, valuation/what's-priced-in, quality/forensic, and a filings-grounded bear case carry the weight; moat, macro, technical, sentiment, ESG become optional lenses.

### Phase 4 — Memory and scorecard

- Store every call: ticker, date, verdict, last price, targets, provider, model, tier.
- A scoring job measures return at 1, 3, 6, and 12 months against **both SPY and the sector ETF**, and whether the price stayed inside the bear–bull range.
- Ticker page: every past brief, how the call changed, how each call did. Superseded calls stay on the record.
- Scorecard page: results by verdict, by model, and by seat.
- Success metric is decision quality, not only alpha: does the brief help understand the business and avoid a bad decision. Expect little edge on large caps; look for it in under-followed names.
- Forward only. No backtests, because models remember what happened to past prices.

### Phase 5 — Watchlist, alerts, and the Update Analyst

- The CIO also writes structured conditions: `{metric, operator, threshold}`, limited to fact-sheet metrics and price, written before buying.
- **Detecting change is automatic and code-only** (price move, new filing, tripped condition). It is cheap and always on.
- **Running the AI is not silent.** When something changes, the app shows a staleness banner on the old brief ("8 days old; since then price −12%, new 8-K, 'Sell if margin < 40%' now TRUE. Re-run?").
- **Update Analyst (delta note).** On request, it reads the old brief plus only what changed and writes a short "does this change the thesis" note in 1–2 calls, instead of re-running all seats. It produces a new stamped brief that supersedes the old one; the original stays for the scorecard.
- A daily check while the app runs. In-app and desktop notifications. No email or phone, since that needs a server. Background auto-runs wait for a hosted version.

### Phase 6 — Public release

- One command to start: the API serves the built frontend, so users do not need Node.js.
- Demo mode on first run, so the app works before a model is installed.
- README with screenshots, contributing guide, clear disclaimers.
- Replace portfolio-percentage sizing with general guidance. Personal sizing reads as advice.
- Optional: a public weekly scorecard on a fixed list of tickers.

## Data sources (all free)

| Data | Source | Notes |
|---|---|---|
| Prices, history, ticker search | Yahoo `v8/finance/chart`, `v1/finance/search` | Unofficial. Keep it behind one module |
| Financials | SEC `data.sec.gov/api/xbrl/companyfacts` | US filers only. User-Agent defaults to the app identity; `SEC_USER_AGENT` is optional |
| Filings list, industry code | SEC `data.sec.gov/submissions` | Earnings press releases are 8-K exhibits |
| Ticker to CIK | SEC `sec.gov/files/company_tickers.json` | Cache daily |
| Macro | FRED `fredgraph.csv?id=...` | No key needed for CSV |
| Filing documents | SEC `sec.gov/Archives/edgar/data/...` | 10-K, 10-Q, 8-K, DEF 14A, Form 4. Same `User-Agent` rule. Max 10 requests per second |
| Call transcripts | User paste | No free official source |

## Known limits

- No free source for analyst consensus estimates or earnings-call transcripts. The reverse DCF stands in for consensus. Pasting a transcript can be an optional input.
- SEC tags vary between companies, so some fields will be missing. Show the gap. Never fill it with a guess.
- Local models are slow. Ten seats on an 8B model take minutes.
- The first run on a new ticker also reads its filings: a few seconds of downloading plus a few dozen short model calls. Later runs reuse the cached digest, and only a newly published filing is read.
- Filings cover US companies only. Foreign companies file a yearly 20-F, which can be added later with less detail.
- Companies format filings differently. When a section cannot be found, the digest says so instead of guessing.
- The scorecard needs months of calls before it means anything.
