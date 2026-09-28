# Aurelia Investments — Private Investment Council

Aurelia takes a ticker or a question and runs it through a council of specialist analysts. They write separately, a moderator forces the disagreement into the open, and a CIO writes the brief you use to decide whether the name is worth more work.

The design contract is [stock-intelligence-agent-plan.md](stock-intelligence-agent-plan.md). What is built versus still planned is [ROADMAP.md](ROADMAP.md). Agents changing the code should also read [CONTEXT.md](CONTEXT.md).

This is informational. It is not a brokerage, not a price forecast, and not financial advice.

## Screenshots

These files live in `demoscreenshots/`. GitHub renders them below. This run is `VGT`, an ETF, so the fact sheet is price and macro only. A US company would also show SEC figures, filing diffs, and peer multiples.

**Home.** Ticker or question, optional company, provider, and model. Short desk is off.

![Home](<demoscreenshots/Screenshot 2026-09-28 080134.png>)

**Live, round 1.** One specialist is writing. The others are still waiting.

![Specialist writing](<demoscreenshots/Screenshot 2026-09-28 075704.png>)

**Live, debate.** The seats have called. The moderator is writing.

![Moderator writing](<demoscreenshots/Screenshot 2026-09-28 075854.png>)

**Live, CIO.** The verdict is being written. Bull and bear from the chamber are already on the page.

![CIO writing](<demoscreenshots/Screenshot 2026-09-28 075905.png>)

**Brief.** Verdict, last price against the base target, and the bear-to-bull rail.

![Decision](<demoscreenshots/Screenshot 2026-09-28 075915.png>)

**Brief, continued.** Council chips and the three scenarios.

![Council on the brief](<demoscreenshots/Screenshot 2026-09-28 080115.png>)

**Fact sheet.** Yahoo closes and the packet the seats actually received.

![Fact sheet](<demoscreenshots/Screenshot 2026-09-28 075930.png>)

**Council notes.** Full specialist text. Earnings quality on this run stopped before a verdict.

![Council notes](<demoscreenshots/Screenshot 2026-09-28 075943.png>)

**Valuation note.**

![Valuation note](<demoscreenshots/Screenshot 2026-09-28 080011.png>)

**Debate.** Bull, bear, the swing factor, and where the seats split.

![Debate](<demoscreenshots/Screenshot 2026-09-28 080034.png>)

## Why it is a council

One prompt that says "analyze this stock" tends to average every lens into a hedge. Aurelia splits the work so each lens has to commit.

**Round 1 — the seats.** Each specialist sees the same security and does not see the other seats. That is deliberate. A valuation note should not soften itself because the growth note was cheerful.

**Round 2 — the chamber.** A moderator reads the notes and writes where they agree, where they split, the strongest bull, the strongest bear, and the one variable that would decide the argument.

**Round 3 — the CIO.** A synthesis pass reads the notes and the debate and writes the verdict, a base / bull / bear price, the risks, and what would make the thesis wrong.

The live page names who is writing: a specialist, then the moderator, then the CIO. **Stop** freezes the timer. Seats that had not spoken say **Stopped**. The brief is the thing you read afterward.

## The seats

The default desk is the full council: fundamentals, valuation, growth, moat, macro, technical, sentiment, risk, ESG, earnings quality, and the bear case. Earnings quality is the extra seat. The other ten are the original roster.

Check **Short desk only** to sit four: fundamentals, valuation, earnings quality, and the bear case. A very small model always uses that short desk.

Each note is supposed to open with a conviction score and a short call. **Incomplete** means the model stopped before it wrote one. That is not a vote, and the page does not invent a 5/10 to fill the gap. The health line under the form tells you the count before you start.

## What happens when you convene

1. You type a ticker (`TSM`) or a question (`Is Tesla worth buying?`). A bare ticker is used as typed. A question is resolved through Yahoo search (`Tesla` becomes `TSLA`).
2. It fetches a live quote, up to 10 years of daily prices, SEC financials and filings when the company files in the US, and a few FRED macro series. Code computes margins, multiples, forensic ratios, and a reverse DCF (what growth the price implies). For a US company it also extracts what changed in Risk Factors and MD&A, guidance lines from the latest earnings Exhibit 99.1 when that exhibit states a figure, any sentence that ties a customer to a percent of sales, and same-industry peer multiples. Two short readers then summarize that packet only — not the whole 10-K — and those notes are what the seats read, next to the fact sheet. For a non-US stock or an ETF, only the price history is real, and the brief says so. Targets and the "+10% vs last" figure are measured from the live quote.
3. The model you selected writes each seat. On your machine, with Ollama, seats run one after another, because one local model cannot honestly write ten opinions at once. A cloud provider can run them together.
4. If the connection dies, the call times out, or the model server returns an error, the desk stops. It does not keep spending the next seats on a dead request. **Stop** on the live page does the same thing on purpose: it closes the request in flight.
5. The moderator writes the debate, then the CIO writes the brief. Both are saved under `output/reports/`. The live job is kept in `output/jobs/` so a reload does not forget a finished run.

The line under the form, such as `ollama · qwen3.6:27b · tier1 · 11 seats`, is the engine for the next run. Refresh the page after you change `.env`. A run that already started keeps the settings it began with.

## How to read the brief

The top of the brief is the decision, not the essays.

- **Verdict and conviction** are the CIO's call, on a 1–10 scale of how hard they are willing to lean.
- **Where price can go** is a rail from the bear price through the last quote to the bull price. Those are council scenarios. They are not a statistical forecast and not a chart of past prices. The table under the rail is the same numbers, including the move versus the last quote.
- **Council** is one chip per seat. Green leans with the idea, red against it, amber is mixed, gray is incomplete.
- **The chamber** is the debate: bull, bear, and the swing factor that picks the path.
- **Risks** are named. A score is shown only when the model actually scored that risk. Repeated filler scores are hidden.
- **Size** is general guidance. The brief does not tell you what percentage of a portfolio to buy.

The full specialist text is on **Council notes**. Read it when a chip surprises you. **Fact sheet** is the sourced packet: revenue, margins, the price chart, filing diffs, guidance excerpts, and the reverse DCF. Numbers on that tab came from Yahoo, SEC, or FRED. A Filings reader or Earnings reader block is the model summarizing that packet, not a new source. Sentences in the council notes that are not on the fact sheet are the model's opinion.

**What the price implies** sits above the decision when free cash flow exists. It is a calculation, not a forecast. The line under the title is freshness: coverage, price date, latest filing, and when the council ran.

## Company, provider, and model

All three boxes are optional.

**Company** is the name printed on the brief and handed to the analysts. Leave it blank and the quote lookup fills it in. Type it when that lookup comes back truncated, such as "Taiwan Semiconductor Manufactur". It does not choose the stock. The ticker or question does that.

**Provider** and **Model** left blank mean "use `.env`". The `.env` in this folder is `ollama` and `qwen3.6:27b`. `.env.example` still names `llama3.1:8b`, which is what a fresh setup gets.

**Provider** is who answers. `ollama` is the local server. `openai`, `anthropic`, `gemini`, `mistral`, `groq`, and `openrouter` are cloud APIs. `lmstudio`, `llamacpp`, `jan`, and `llamafile` are other local servers. Cloud calls need `LLM_API_KEY` in `.env`. The form does not ask for a key. Cursor is not a provider in this app.

**Model** is which model that provider should run, such as `llama3.1:8b` or `qwen3.6:27b`. The same ticker will not produce the same brief on two models. The name also picks a budget:

| What you select | What you get |
|---|---|
| A listed 8B-class local model | Full desk, shorter prompts, shorter notes |
| A listed large local model, including `qwen3.6:27b` | Full desk, fuller prompts, longer notes |
| `openai`, `anthropic`, or `gemini` | The long path, even if the model id is new |
| A tiny listed model, about 3B and under | 4 seats, and no real debate |
| A name the list does not recognize | The 8B path, even if the tag says 27B or 70B |

The lists live in `backend/app/config/model_tiers.py`. The health line shows which path the next run will take.

## Setup

Python 3.11+, Node.js 18+, and optionally [Ollama](https://ollama.com). A `.sh` file does not run in PowerShell or Command Prompt. Windows uses the PowerShell scripts. macOS and Linux use the bash scripts. Git Bash on Windows can run the bash scripts too.

**Windows (PowerShell), from the project root**

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
```

**macOS / Linux, or Git Bash**

```bash
bash scripts/setup.sh
```

The script checks Python 3.11+ and Node 18+, creates `.venv`, installs both dependency files, and copies `.env.example` to `.env` when `.env` is missing. An existing `.env` is left alone.

`.env` defaults to Ollama and `llama3.1:8b`. To click through the UI with no model, set `LLM_PROVIDER=mock` and `LLM_MODEL=mock`, then start the app again.

## One command

After dependencies are installed, this builds the page and serves it from the API. You open one address. A second Node process is not required after that build.

**Windows**

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1
```

**macOS / Linux, or Git Bash**

```bash
bash scripts/start.sh
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). If Ollama is not installed, the home page offers a demo desk that still walks through a brief. That demo is not a live model.

The two-window scripts below are for development, when you want the page to reload as you edit it.

## Run

**Windows**

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run.ps1
```

That opens two windows: the API from the project root, and the UI from `frontend`. Close both windows to stop.

**macOS / Linux, or Git Bash**

```bash
bash scripts/run.sh
```

That starts the API in the background and the UI in this terminal. Ctrl+C stops both.

Open [http://localhost:5173](http://localhost:5173). The page calls the API through Vite. Health is [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health).

Start the API from the project root. It reads `.env` from the current directory. After you edit `.env`, stop the API and start it again. A reload does not re-read that file.

### Start each service yourself

Same two processes, one terminal each. Run setup first. Stop a service with Ctrl+C in its terminal. The other keeps running.

**Windows, from the project root**

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

```powershell
cd frontend
npm run dev
```

**macOS / Linux, from the project root**

```bash
.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

```bash
cd frontend
npm run dev
```

**Ollama**

Install [Ollama](https://ollama.com), then pull the model named in `.env`:

```bash
ollama pull llama3.1:8b
```

The run script checks that port 11434 answers and that this model is pulled. If the Ollama app is already open, leave it open. `ollama serve` is only for a machine where nothing is already listening on that port.

An 8B council often takes several minutes. A 27B model is slower and needs a large GPU. The first look at a new US ticker also downloads SEC filings; later runs reuse `output/cache/`. The live page is the progress indicator. Leave Ollama running until the CIO brief appears.

Leave `SEC_USER_AGENT` unset. The app identifies itself to SEC as `Aurelia Investments research@example.com`. Set `LOCAL_CONTEXT_WINDOW` to at least `32768` for a large local model so the fact sheet fits beside the seat prompt. Restart the API after editing `.env`.

You can inspect facts without running the council: [http://127.0.0.1:8000/api/facts/AAPL](http://127.0.0.1:8000/api/facts/AAPL).

## Scorecard, watchlist, and updates

**Scorecard** (`/scorecard`) keeps every call. A return at 1, 3, 6, or 12 months appears only after that date. It is measured from the price stored on the brief, against SPY and the sector ETF, including whether the price stayed between the bear and bull targets. Nothing is backtested. A later brief supersedes an earlier one. The earlier file stays. `/ticker/AAPL` lists every brief for that name.

**Archive** (`/history`) lists saved briefs. **Delete** removes that file from this computer. It does not change a filing or a price.

**Watch** (`/watch`) checks price, a new SEC filing, and the checkable sell-if lines while the app is open. The check is code. It does not call the model and it does not send email. A change shows a banner on the old brief. **Write a delta note** asks the model once whether the thesis changed, saves a new brief, and leaves the original on the record. If two watched names move together, the page says so. That is price correlation, not a customer relationship.

## Contributing

Issues and small pull requests are welcome. Keep numbers in code, with a source. Do not add a paid data vendor or a required account. Do not overwrite a saved brief. Run `python -m pytest` from the repo root before opening a pull request. The UI is a light studio: page `#E7E8EC`, cards white, text `#0F172A`, accent `#8B5CF6`. Match that. This project is informational. It is not financial advice, and a portfolio-weight recommendation does not belong in a brief.

## Where the app differs from the specification

The plan describes the ideal shape. A few behaviors in this repo are tighter or not built yet.

- Local seats run in sequence. The plan's parallel round 1 is how cloud providers behave.
- Live data is a Yahoo quote and history, SEC companyfacts and filing text, and FRED. There is still no web search. `ENABLE_WEB_SEARCH` is off.
- Notes ask for the verdict on the first lines, because a token cap used to cut the call off the end.
- A dead model connection stops the desk. The plan recorded a failed seat and continued.
- There is no portfolio fit and no A-versus-B compare. The watchlist checks price, filings, and sell-if lines. It does not size a portfolio.

## Layout

```
backend/app/                      API, seats, debate, CIO
backend/app/data/                 Fact sheet, filings, peers, scorecard, watch
frontend/                         The desk UI
scripts/setup.ps1, scripts/run.ps1
                                  Windows setup and the two-window dev start
scripts/start.ps1, scripts/start.sh
                                  One process: the API serves the built page
scripts/setup.sh, scripts/run.sh  macOS, Linux, and Git Bash
output/reports/                   Saved briefs (not committed)
output/jobs/                      Saved runs, including stopped ones
output/cache/                     Yahoo, SEC, and FRED cache (not committed)
LICENSE                           MIT
stock-intelligence-agent-plan.md  The specification
ROADMAP.md                        What is built and what is next
CONTEXT.md                        Notes for the next person editing the code
```
