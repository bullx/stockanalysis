# Local LLM Patch — Stock Intelligence System
## Addendum to `stock-intelligence-system-spec.md`

**Purpose:** This document patches the main spec for local LLM usage.  
**Read alongside:** `stock-intelligence-system-spec.md` (the base spec).  
**When this applies:** Any time `LLM_PROVIDER` is set to `ollama`, `lmstudio`, `llamacpp`, or any self-hosted model.  
**Priority:** Where this document contradicts the base spec, this document wins.

---

## Why the base spec needs patching for local models

The base spec was written assuming a capable cloud model (GPT-4o, Claude 3.5, Gemini 1.5 Pro). Local models differ in five critical ways that break the system if unaddressed:

| Dimension | Cloud model | Local model | Impact if ignored |
|---|---|---|---|
| Context window | 128k–200k tokens | 4k–32k tokens | Round 3 crashes — too much input |
| Parallelism | 10 simultaneous calls fine | Single process, sequential only | 10x slower or crashes |
| JSON reliability | Very reliable | Unreliable on small models | CIO synthesis fails |
| System prompt handling | Native support | Varies by model family | Agent personas don't work |
| Timeout | 30–60s fine | 2–20 mins per call | Needs much longer timeouts |

Every section below addresses one or more of these gaps.

---

## Patch 1 — Provider config (replaces Section 2.2 Ollama entry)

The base spec has one Ollama entry. Replace it with entries for all common local runtimes:

```javascript
// config/providers.js  — LOCAL PROVIDERS SECTION

const LOCAL_PROVIDERS = {

  // ── Ollama ──────────────────────────────────────────────────────────────
  // Install: https://ollama.com  |  Run: ollama serve
  // Pull a model first: ollama pull llama3.1:8b
  ollama: {
    endpoint:           "http://localhost:11434/api/chat",
    authHeader:         () => ({}),
    supportsSystem:     true,          // Ollama supports system role natively
    streaming:          false,
    defaultModel:       "llama3.1:8b",
    bodyMapper: (messages, maxTokens, model, options = {}) => ({
      model:   model || "llama3.1:8b",
      messages,                        // Ollama accepts full messages array including system
      stream:  false,
      options: {
        num_predict:  maxTokens,
        temperature:  options.temperature ?? 0.3,
        num_ctx:      options.contextWindow ?? 8192,  // Set based on your model's actual window
        stop:         options.stopTokens ?? []
      }
    }),
    responseExtractor: (data) => data.message.content
  },

  // ── LM Studio ────────────────────────────────────────────────────────────
  // Install: https://lmstudio.ai  |  Start local server in LM Studio UI
  // Uses OpenAI-compatible endpoint — easiest local option
  lmstudio: {
    endpoint:           "http://localhost:1234/v1/chat/completions",
    authHeader:         () => ({ "Authorization": "Bearer lm-studio" }),
    supportsSystem:     true,
    streaming:          false,
    defaultModel:       "local-model",   // LM Studio uses whatever is loaded
    bodyMapper: (messages, maxTokens, model, options = {}) => ({
      model:       model || "local-model",
      messages,
      max_tokens:  maxTokens,
      temperature: options.temperature ?? 0.3,
      stream:      false
    }),
    responseExtractor: (data) => data.choices[0].message.content
  },

  // ── llama.cpp server ─────────────────────────────────────────────────────
  // Run: ./llama-server -m model.gguf --port 8080 --ctx-size 8192
  llamacpp: {
    endpoint:           "http://localhost:8080/v1/chat/completions",
    authHeader:         () => ({}),
    supportsSystem:     true,
    streaming:          false,
    defaultModel:       "local",
    bodyMapper: (messages, maxTokens, model, options = {}) => ({
      model:       "local",
      messages,
      max_tokens:  maxTokens,
      temperature: options.temperature ?? 0.3,
      stream:      false,
      cache_prompt: true               // llama.cpp supports prompt caching — speeds up repeated system prompts
    }),
    responseExtractor: (data) => data.choices[0].message.content
  },

  // ── Jan ───────────────────────────────────────────────────────────────────
  // Install: https://jan.ai  |  Enable API Server in Jan settings
  jan: {
    endpoint:           "http://localhost:1337/v1/chat/completions",
    authHeader:         () => ({ "Authorization": "Bearer jan-local" }),
    supportsSystem:     true,
    streaming:          false,
    defaultModel:       "local-model",
    bodyMapper: (messages, maxTokens, model, options = {}) => ({
      model:       model || "local-model",
      messages,
      max_tokens:  maxTokens,
      temperature: options.temperature ?? 0.3,
      stream:      false
    }),
    responseExtractor: (data) => data.choices[0].message.content
  },

  // ── Llamafile ─────────────────────────────────────────────────────────────
  // A single executable that serves a model via HTTP
  // Run: ./model.llamafile --port 8080
  llamafile: {
    endpoint:           "http://localhost:8080/v1/chat/completions",
    authHeader:         () => ({}),
    supportsSystem:     true,
    streaming:          false,
    defaultModel:       "local",
    bodyMapper: (messages, maxTokens, model, options = {}) => ({
      model:       "local",
      messages,
      max_tokens:  maxTokens,
      temperature: options.temperature ?? 0.3
    }),
    responseExtractor: (data) => data.choices[0].message.content
  }

};
```

---

## Patch 2 — Model capability tiers (new section, insert after Section 2.2)

Local models vary wildly. The system must behave differently depending on model capability. Use this tier table to configure behavior:

```javascript
// config/model_tiers.js

const MODEL_TIERS = {

  // ── Tier 1: Full capability — use exactly like a cloud model ─────────────
  // These models handle the full spec without modification
  tier1: {
    models: [
      "llama3.1:70b", "llama3.1:405b",
      "llama3.3:70b",
      "qwen2.5:72b", "qwen2.5:32b",
      "mistral-large",
      "deepseek-r1:70b", "deepseek-v3",
      "gemma3:27b",
      "phi4:14b",
      "command-r-plus"                 // via Ollama
    ],
    parallelism:      "sequential",    // Still sequential for local — hardware constraint
    maxTokensAgent:   800,
    maxTokensDebate:  1200,
    maxTokensCIO:     2000,
    contextWindow:    32768,
    jsonMode:         "prompt",        // Prompt-based JSON ("output only JSON")
    systemPromptMode: "native",        // Full system prompt supported
    roundsEnabled:    [1, 2, 3],       // All 3 rounds
    agentCount:       10
  },

  // ── Tier 2: Capable mid-range — minor adjustments needed ─────────────────
  tier2: {
    models: [
      "llama3.1:8b", "llama3.2:11b",
      "mistral:7b", "mixtral:8x7b",
      "qwen2.5:14b", "qwen2.5:7b",
      "deepseek-r1:14b", "deepseek-r1:8b",
      "gemma3:12b", "gemma3:4b",
      "phi3.5:3.8b", "phi4-mini",
      "gemma2:9b",
      "command-r"
    ],
    parallelism:      "sequential",
    maxTokensAgent:   600,             // Reduced — smaller models get verbose quickly
    maxTokensDebate:  800,
    maxTokensCIO:     1500,
    contextWindow:    8192,
    jsonMode:         "prompt+schema", // Prompt + simplified schema
    systemPromptMode: "native",
    roundsEnabled:    [1, 2, 3],
    agentCount:       10,
    simplifyPrompts:  true             // Use simplified agent prompts (see Patch 5)
  },

  // ── Tier 3: Small models — significant degradation mode ──────────────────
  // These models struggle with complex JSON and long system prompts
  tier3: {
    models: [
      "llama3.2:3b", "llama3.2:1b",
      "phi3:mini", "phi3.5:mini",
      "gemma2:2b", "gemma3:1b",
      "qwen2.5:3b", "qwen2.5:1.5b",
      "tinyllama", "smollm2"
    ],
    parallelism:      "sequential",
    maxTokensAgent:   400,
    maxTokensDebate:  600,
    maxTokensCIO:     800,
    contextWindow:    4096,
    jsonMode:         "key-value",     // Fallback: structured key-value instead of JSON
    systemPromptMode: "inject",        // Inject persona into user message (see Patch 4)
    roundsEnabled:    [1, 3],          // SKIP debate round — too expensive for small models
    agentCount:       5,               // Run only 5 core agents (see Patch 6)
    simplifyPrompts:  true,
    flattenJSON:      true             // Use simplified flat JSON schema (see Patch 7)
  }

};

// Auto-detect tier from model name
function detectTier(modelName) {
  const name = modelName.toLowerCase();
  for (const [tier, config] of Object.entries(MODEL_TIERS)) {
    if (config.models.some(m => name.includes(m.toLowerCase().replace(/:.*/, "")))) {
      return { tier, config };
    }
  }
  return { tier: "tier2", config: MODEL_TIERS.tier2 }; // Default to Tier 2 if unknown
}
```

---

## Patch 3 — Updated callLLM with local-aware settings (replaces Section 2.3)

```javascript
// utils/llm.js  — LOCAL-AWARE VERSION

async function callLLM(systemPrompt, userMessage, maxTokens = 800, options = {}) {
  const providerName = process.env.LLM_PROVIDER || "openai";
  const apiKey       = process.env.LLM_API_KEY || "";
  const modelName    = process.env.LLM_MODEL || "";
  const provider     = { ...PROVIDERS, ...LOCAL_PROVIDERS }[providerName];

  if (!provider) throw new Error(`Unknown provider: ${providerName}`);

  // ── System prompt handling: not all local models handle it the same way ──
  let messages;
  if (provider.supportsSystem) {
    // Model accepts system role natively
    messages = [
      { role: "system", content: systemPrompt },
      { role: "user",   content: userMessage  }
    ];
  } else {
    // Inject system prompt into the user message — fallback for models without system role
    messages = [
      { role: "user", content: `[INSTRUCTIONS]\n${systemPrompt}\n\n[TASK]\n${userMessage}` }
    ];
  }

  const body    = provider.bodyMapper(messages, maxTokens, modelName, options);
  const url     = provider.endpoint + (provider.queryParam?.(apiKey) || "");
  const headers = { "Content-Type": "application/json", ...provider.authHeader(apiKey) };

  // ── Timeout: local models are much slower than cloud ─────────────────────
  const timeoutMs = process.env.LLM_PROVIDER_TYPE === "local"
    ? parseInt(process.env.LOCAL_LLM_TIMEOUT_MS || "300000")  // 5 minutes default for local
    : 60000;                                                    // 60 seconds for cloud

  const controller = new AbortController();
  const timeoutId  = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(url, {
      method:  "POST",
      headers,
      body:    JSON.stringify(body),
      signal:  controller.signal
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      const err = await response.text();
      throw new Error(`LLM API ${response.status}: ${err}`);
    }

    const data = await response.json();
    return provider.responseExtractor(data);

  } catch (err) {
    clearTimeout(timeoutId);
    if (err.name === "AbortError") {
      throw new Error(`LLM call timed out after ${timeoutMs / 1000}s — model may be too slow for this task size`);
    }
    throw err;
  }
}
```

---

## Patch 4 — System prompt injection for models that ignore system role

Some quantized local models (especially smaller GGUF files) partially or fully ignore the system role. Use this wrapper to inject the persona into the user message instead:

```javascript
// utils/prompt_adapter.js

function adaptPromptsForModel(systemPrompt, userMessage, mode) {
  switch (mode) {

    case "native":
      // Model fully supports system role — use as-is
      return { system: systemPrompt, user: userMessage };

    case "inject":
      // Model ignores system role — inject persona into user turn
      return {
        system: "",
        user: `You must follow these instructions precisely for this entire response:

${systemPrompt}

---

Now complete this task:
${userMessage}`
      };

    case "chatml":
      // Some models respond better to ChatML format explicitly written out
      return {
        system: "",
        user: `<|im_start|>system\n${systemPrompt}<|im_end|>\n<|im_start|>user\n${userMessage}<|im_end|>\n<|im_start|>assistant\n`
      };

    default:
      return { system: systemPrompt, user: userMessage };
  }
}
```

---

## Patch 5 — Simplified agent prompts for Tier 2/3 models

Long, multi-section system prompts confuse smaller local models. Use these shorter versions when `simplifyPrompts: true`:

```javascript
// agents/simplified_prompts.js
// Use for Tier 2 and Tier 3 models only. Full prompts are in the main spec.

const SIMPLIFIED_AGENT_PROMPTS = {

  fundamental: `You are a financial analyst. Analyze the revenue growth, profit margins, 
free cash flow, balance sheet health, and return on capital of the stock given. 
Be specific. End with: CONVICTION: X/10 and FUNDAMENTAL STANCE: [BUY/HOLD/SELL].`,

  valuation: `You are a valuation analyst. Assess whether the stock is cheap or expensive 
using P/E ratio, EV/EBITDA, and free cash flow yield vs history and peers. 
End with: CONVICTION: X/10 and VALUATION: [UNDERVALUED/FAIRLY VALUED/OVERVALUED].`,

  growth: `You are a growth analyst. Assess the company's revenue growth rate, total 
addressable market, and long-term earnings power. Is growth secular or cyclical? 
End with: CONVICTION: X/10 and GROWTH OUTLOOK: [STRONG/MODERATE/WEAK].`,

  moat: `You are a competitive analyst. Assess whether this company has durable competitive 
advantages: switching costs, network effects, brand, patents, or cost advantages. 
End with: CONVICTION: X/10 and MOAT: [WIDE/NARROW/NONE].`,

  macro: `You are a macro analyst. Is the current economic environment — interest rates, 
inflation, and growth outlook — a tailwind or headwind for this stock? 
End with: CONVICTION: X/10 and MACRO STANCE: [TAILWIND/NEUTRAL/HEADWIND].`,

  technical: `You are a technical analyst. Based on price trend, momentum, and key levels, 
what is the technical setup for this stock? 
End with: CONVICTION: X/10 and TECHNICAL BIAS: [BULLISH/NEUTRAL/BEARISH].`,

  sentiment: `You are a sentiment analyst. Is this stock loved or hated by investors? 
Assess short interest, positioning, and contrarian signals. 
End with: CONVICTION: X/10 and SENTIMENT: [OVERCROWDED/NEUTRAL/OUT OF FAVOR].`,

  risk: `You are a risk manager. What are the top 3 risks for this investment? 
What could cause a major loss? Assess leverage, competition, and execution risk. 
End with: CONVICTION: X/10 and RISK LEVEL: [HIGH/MODERATE/LOW].`,

  esg: `You are an ESG analyst. What environmental, social, or governance risks are 
financially material for this company over the next 5 years? 
End with: CONVICTION: X/10 and ESG PROFILE: [STRONG/AVERAGE/LAGGARD].`,

  devil: `You are a skeptic. Construct the strongest possible bear case for this stock. 
Why should an investor NOT buy it? What could cause a 40% loss? 
End with: BEAR CASE CONVICTION: X/10 and PRIMARY BEAR THESIS: [one sentence].`

};
```

---

## Patch 6 — 5-agent core set for Tier 3 / very small models

When running on a Tier 3 model (< 4B parameters), reduce to the 5 most essential agents:

```javascript
// agents/core_five.js

// Priority order — if you must cut agents, cut from the bottom up
const CORE_AGENT_IDS = [
  "fundamental",   // #1 — non-negotiable: business quality
  "valuation",     // #2 — non-negotiable: are you overpaying?
  "risk",          // #3 — non-negotiable: what could go wrong?
  "growth",        // #4 — important: long-term thesis
  "devil"          // #5 — always keep the bear case
  // Removed for Tier 3: technical, sentiment, macro, moat, esg
];

// Why these 5 specifically:
// - fundamental + valuation = core investment decision (good business + good price)
// - risk + devil = mandatory downside protection
// - growth = thesis direction
// The other 5 (technical, sentiment, macro, moat, esg) add richness but aren't decision-critical
```

---

## Patch 7 — JSON fallback for unreliable local models (replaces Section 8.1)

Small local models frequently produce invalid JSON. Implement a 5-strategy extraction chain plus a non-JSON fallback:

```javascript
// utils/parse.js  — ROBUST LOCAL VERSION

function extractAndParseJSON(rawText) {

  // Strategy 1: direct parse (works for well-behaved models)
  try { return JSON.parse(rawText.trim()); } catch (_) {}

  // Strategy 2: extract first {...} block via regex
  const jsonBlock = rawText.match(/\{[\s\S]*\}/);
  if (jsonBlock) { try { return JSON.parse(jsonBlock[0]); } catch (_) {} }

  // Strategy 3: strip markdown fences
  const stripped = rawText.replace(/```json\s*/gi, "").replace(/```\s*/gi, "").trim();
  try { return JSON.parse(stripped); } catch (_) {}

  // Strategy 4: fix common local model JSON errors
  const fixed = rawText
    .replace(/```json/gi, "").replace(/```/gi, "")    // strip fences
    .replace(/,\s*\}/g, "}")                           // trailing commas before }
    .replace(/,\s*\]/g, "]")                           // trailing commas before ]
    .replace(/(['"])?([a-zA-Z_][a-zA-Z0-9_]*)(['"])?:/g, '"$2":') // unquoted keys
    .replace(/:\s*'([^']*)'/g, ': "$1"')               // single-quoted values
    .replace(/\n/g, " ")                               // collapse newlines
    .match(/\{[\s\S]*\}/)?.[0] || "";
  try { return JSON.parse(fixed); } catch (_) {}

  // Strategy 5: key-value fallback — extract structured text when JSON fails completely
  console.warn("JSON parse failed — falling back to key-value extraction");
  return extractKeyValueFallback(rawText);
}

function extractKeyValueFallback(text) {
  // When the model refuses to output JSON, extract what we can from structured text
  const extract = (pattern, defaultVal) => {
    const m = text.match(pattern);
    return m ? m[1].trim() : defaultVal;
  };

  return {
    ticker:              extract(/ticker[:\s]+([A-Z]{1,5})/i, "UNKNOWN"),
    company_name:        extract(/company[:\s]+(.+)/i, "Unknown"),
    verdict:             extract(/verdict[:\s]+(STRONG BUY|BUY|HOLD|AVOID|STRONG AVOID)/i, "HOLD"),
    title:               extract(/title[:\s]+(.+)/i, "Analysis complete"),
    summary:             extract(/summary[:\s]+(.{20,300})/i, text.slice(0, 200)),
    conviction:          parseInt(extract(/conviction[:\s]+(\d+)/i, "5")),
    price_target_base:   extract(/(?:base|target)[:\s]+(\$[\d,]+)/i, "N/A"),
    price_target_bull:   extract(/bull[:\s]+(\$[\d,]+)/i, "N/A"),
    price_target_bear:   extract(/bear[:\s]+(\$[\d,]+)/i, "N/A"),
    implied_upside_base: extract(/upside[:\s]+([+-]?\d+%)/i, "N/A"),
    risk_level:          extract(/risk level[:\s]+(Low|Moderate|High|Very High)/i, "Moderate"),
    horizon:             extract(/horizon[:\s]+(Short|Medium|Long)/i, "Medium-term"),
    consensus_score:     parseInt(extract(/consensus[:\s]+(\d+)/i, "5")),
    scenarios:           [],
    catalysts:           [],
    risks:               [],
    financial_health:    [],
    predictability_scores: [],
    position_sizing:     { aggressive_investor: "N/A", moderate_investor: "N/A", conservative_investor: "N/A", sizing_rationale: "Extraction fallback — review manually" },
    investment_strategy: [text.slice(0, 500)],
    thesis_invalidators: [],
    data_quality_notes:  "WARNING: JSON extraction failed — key-value fallback used. Output quality reduced. Consider upgrading to a Tier 1 or Tier 2 model."
  };
}
```

---

## Patch 8 — Sequential execution with progress (replaces Section 9 Round 1)

Local models cannot handle 10 parallel calls. Replace `Promise.all` with sequential execution:

```javascript
// orchestrator/rounds.js  — LOCAL-AWARE VERSION

async function runRound1(query, tier) {
  const agentDefs = tier.agentCount === 5
    ? AGENT_DEFINITIONS.filter(a => CORE_AGENT_IDS.includes(a.id))
    : AGENT_DEFINITIONS;

  const promptMode   = tier.systemPromptMode;
  const useSimplified = tier.simplifyPrompts;
  const round1 = {};

  // Local models: sequential only
  for (let i = 0; i < agentDefs.length; i++) {
    const agent = agentDefs[i];
    console.log(`[Round 1] Agent ${i + 1}/${agentDefs.length}: ${agent.name}...`);

    const systemPrompt = useSimplified
      ? SIMPLIFIED_AGENT_PROMPTS[agent.id]
      : agent.system_prompt;

    const userMessage = buildAgentUserMessage(agent, query);
    const { system, user } = adaptPromptsForModel(systemPrompt, userMessage, promptMode);

    try {
      const raw    = await callLLMWithRetry(system, user, tier.maxTokensAgent);
      const parsed = parseAgentOutput(raw, agent.id);
      round1[agent.id] = {
        agent_id: agent.id, agent_name: agent.name,
        ...parsed, timestamp: new Date().toISOString()
      };
      console.log(`  ✓ ${agent.name} — conviction: ${parsed.conviction}/10, stance: ${parsed.stance}`);

    } catch (e) {
      console.warn(`  ✗ ${agent.name} failed: ${e.message}`);
      round1[agent.id] = {
        agent_id: agent.id, agent_name: agent.name,
        output: `AGENT_ERROR: ${e.message}`, conviction: 5, stance: "unknown",
        error: e.message, timestamp: new Date().toISOString()
      };
    }

    // Small delay between calls — helps with CPU/thermal throttling on local machines
    if (i < agentDefs.length - 1) {
      await sleep(parseInt(process.env.LOCAL_AGENT_DELAY_MS || "500"));
    }
  }

  return round1;
}

async function runRound2(query, round1, tier) {
  // If tier skips debate round (Tier 3), return a minimal synthetic debate
  if (!tier.roundsEnabled.includes(2)) {
    console.log("[Round 2] Skipped for Tier 3 model — generating synthetic debate summary");
    return buildSyntheticDebate(round1);
  }

  console.log("[Round 2] Running debate moderator...");
  const { system, user } = adaptPromptsForModel(
    DEBATE_SYSTEM_PROMPT,
    buildDebateUserMessage(query, round1),
    tier.systemPromptMode
  );
  const raw = await callLLMWithRetry(system, user, tier.maxTokensDebate);
  return parseDebateOutput(raw);
}

// Synthetic debate for Tier 3 — generated from agent outputs without an LLM call
function buildSyntheticDebate(round1) {
  const outputs  = Object.values(round1).filter(o => !o.error);
  const avgConv  = outputs.reduce((s, o) => s + o.conviction, 0) / (outputs.length || 1);
  const bulls    = outputs.filter(o => o.conviction >= 7);
  const bears    = outputs.filter(o => o.conviction <= 4);
  const devOutput = round1["devil"]?.output || "";

  return {
    consensus_points:    ["Multiple analysts cited business quality as a positive factor"],
    key_disagreements:   ["Valuation assessment and timing differ across analysts"],
    strongest_bull:      bulls[0]?.output?.slice(0, 200) || "See individual agent outputs",
    strongest_bear:      devOutput.slice(0, 200) || "See risk manager output",
    swing_factor:        "Earnings growth vs. valuation multiple compression",
    unresolved_questions: ["Current price vs. fair value", "Near-term catalyst timing"],
    consensus_score:     Math.round(avgConv),
    raw_text:            `[SYNTHETIC] Average conviction: ${avgConv.toFixed(1)}/10. ${bulls.length} bullish agents, ${bears.length} bearish agents.`
  };
}
```

---

## Patch 9 — CIO prompt for local models (replaces Section 7 CIO prompt)

The base CIO prompt asks for a large, deeply nested JSON object. Small/mid local models struggle. Use a tiered CIO prompt approach:

```javascript
// agents/synthesis.js  — TIERED CIO PROMPTS

// For Tier 1 models — use the full schema from the base spec (no change)
const CIO_PROMPT_TIER1 = CIO_SYSTEM_PROMPT; // from base spec

// For Tier 2 models — simplified schema, same fields but shorter instructions
const CIO_PROMPT_TIER2 = `You are the lead investment analyst. Based on the specialist reports 
and debate summary provided, deliver a final investment verdict.

Output ONLY valid JSON. No text before or after. No markdown fences. Just the JSON object.

Use this exact schema:
{
  "ticker": "string",
  "company_name": "string",
  "verdict": "STRONG BUY | BUY | HOLD | AVOID | STRONG AVOID",
  "title": "string (max 10 words)",
  "summary": "string (2-3 sentences)",
  "conviction": 1-10,
  "price_target_base": "$XXX",
  "price_target_bull": "$XXX",
  "price_target_bear": "$XXX",
  "risk_level": "Low | Moderate | High | Very High",
  "horizon": "Short-term | Medium-term | Long-term",
  "consensus_score": 1-10,
  "scenarios": [
    {"type":"bull","probability":"XX%","price_target":"$XXX","thesis":"string"},
    {"type":"base","probability":"XX%","price_target":"$XXX","thesis":"string"},
    {"type":"bear","probability":"XX%","price_target":"$XXX","thesis":"string"}
  ],
  "top_risks": ["string","string","string"],
  "investment_strategy": ["string","string","string"],
  "position_sizing": {
    "aggressive": "X%", "moderate": "X%", "conservative": "X%"
  }
}`;

// For Tier 3 models — absolute minimal schema to maximize JSON reliability
const CIO_PROMPT_TIER3 = `You are an investment analyst. Read the reports below and give 
a final investment verdict. Output ONLY a JSON object with these exact keys:

{
  "ticker": "string",
  "verdict": "BUY or HOLD or AVOID",
  "conviction": number between 1 and 10,
  "summary": "string with your 2-sentence conclusion",
  "top_bull_point": "string",
  "top_bear_point": "string",
  "suggested_action": "string with what an investor should do"
}

Output only the JSON. Nothing else.`;

function getCIOPrompt(tier) {
  switch (tier) {
    case "tier1": return CIO_PROMPT_TIER1;
    case "tier2": return CIO_PROMPT_TIER2;
    case "tier3": return CIO_PROMPT_TIER3;
    default:      return CIO_PROMPT_TIER2;
  }
}
```

---

## Patch 10 — Context window management for Round 3

Local models have small context windows. The 10 agent outputs + debate can easily exceed 4k–8k tokens. Always trim before passing to the CIO:

```javascript
// utils/context.js

// Rough token estimate: 1 token ≈ 4 chars in English
function estimateTokens(text) { return Math.ceil(text.length / 4); }

function prepareRound3Context(round1, debate, contextWindow) {
  // Reserve: CIO system prompt (~400 tokens) + query (~100 tokens) + output (~2000 tokens)
  // Available for Round 1 + Round 2 input:
  const available = contextWindow - 2500;

  let round1Text = AGENT_DEFINITIONS
    .filter(a => round1[a.id])
    .map(a => `=== ${a.name.toUpperCase()} ===\n${round1[a.id].output}`)
    .join("\n\n");

  const debateText = debate.raw_text || "";
  const debateTokens = estimateTokens(debateText);
  const availableForRound1 = available - debateTokens - 200; // 200 token buffer

  if (estimateTokens(round1Text) > availableForRound1) {
    console.warn(`Context trimming: Round 1 output exceeds ${availableForRound1} tokens. Truncating.`);
    round1Text = trimRound1Outputs(round1, availableForRound1);
  }

  return { round1Text, debateText };
}

function trimRound1Outputs(round1, maxTokens) {
  const agentOutputs = AGENT_DEFINITIONS
    .filter(a => round1[a.id])
    .map(a => ({ id: a.id, name: a.name, output: round1[a.id].output, conviction: round1[a.id].conviction }));

  // Priority order for trimming: cut ESG first, then technical, then sentiment, then macro
  const trimPriority = ["esg", "technical", "sentiment", "macro", "moat", "growth", "valuation", "fundamental", "risk", "devil"];
  const tokensPerAgent = Math.floor(maxTokens / agentOutputs.length);

  return agentOutputs
    .map(a => {
      const text = a.output;
      // Always keep the last 3 lines (contains CONVICTION and STANCE)
      const lines   = text.split("\n");
      const tail    = lines.slice(-3).join("\n");
      const body    = text.slice(0, tokensPerAgent * 4 - tail.length).trim();
      return `=== ${a.name.toUpperCase()} ===\n${body}\n...\n${tail}`;
    })
    .join("\n\n");
}
```

---

## Patch 11 — Updated .env for local setups

```bash
# .env  — LOCAL LLM CONFIGURATION

# Provider
LLM_PROVIDER=ollama               # ollama | lmstudio | llamacpp | jan | llamafile

# Model — match exactly what you have pulled/loaded
LLM_MODEL=llama3.1:8b             # Examples:
                                   # ollama:   llama3.1:8b, qwen2.5:14b, deepseek-r1:8b
                                   # lmstudio: leave blank — uses loaded model
                                   # llamacpp: leave blank — uses loaded model

# Mark as local — enables longer timeouts and sequential execution
LLM_PROVIDER_TYPE=local

# Timeout per agent call (milliseconds)
# Small model (3-8B):   120000  (2 minutes)
# Medium model (14B):   300000  (5 minutes)
# Large model (70B):    600000  (10 minutes)
LOCAL_LLM_TIMEOUT_MS=300000

# Delay between sequential agent calls (milliseconds)
# Helps with CPU thermal throttling and memory pressure
LOCAL_AGENT_DELAY_MS=500

# Context window size — set to match your model's actual context
# llama3.1:8b  → 8192 or 128000 (check your Ollama modelfile)
# mistral:7b   → 8192
# phi3:mini    → 4096
# qwen2.5:14b  → 32768
LOCAL_CONTEXT_WINDOW=8192

# Enable web search for live data (requires web search capability in your agent runtime)
ENABLE_WEB_SEARCH=false

# Optional: API key (leave blank for Ollama, LM Studio, llama.cpp)
LLM_API_KEY=
```

---

## Patch 12 — Updated orchestrator main flow (replaces Section 9)

```javascript
// orchestrator/orchestrator.js  — COMPLETE LOCAL-AWARE VERSION

async function runAnalysis(userInput) {

  // ── 1. Detect model tier ─────────────────────────────────────────────────
  const modelName    = process.env.LLM_MODEL || "unknown";
  const contextWindow = parseInt(process.env.LOCAL_CONTEXT_WINDOW || "8192");
  const { tier, config: tierConfig } = detectTier(modelName);
  const isLocal = process.env.LLM_PROVIDER_TYPE === "local";

  console.log(`Provider: ${process.env.LLM_PROVIDER} | Model: ${modelName} | Tier: ${tier}`);
  console.log(`Agents: ${tierConfig.agentCount} | Context: ${contextWindow} tokens | Rounds: ${tierConfig.roundsEnabled.join(", ")}`);

  // ── 2. Normalize query ───────────────────────────────────────────────────
  const query = normalizeQuery(userInput);

  // ── 3. Optional live data (skip for local by default) ────────────────────
  if (process.env.ENABLE_WEB_SEARCH === "true") {
    try {
      query.live_data = await fetchLiveData(query.ticker);
    } catch (e) {
      console.warn("Live data fetch failed:", e.message);
    }
  }

  // ── 4. Round 1 ───────────────────────────────────────────────────────────
  const startTime = Date.now();
  console.log(`\nRound 1: Running ${tierConfig.agentCount} specialist agents (${isLocal ? "sequential" : "parallel"})...`);
  const round1 = await runRound1(query, tierConfig);
  console.log(`Round 1 complete in ${Math.round((Date.now() - startTime) / 1000)}s`);

  // ── 5. Round 2 ───────────────────────────────────────────────────────────
  console.log("\nRound 2: Debate synthesis...");
  const round2 = await runRound2(query, round1, tierConfig);
  console.log(`Consensus score: ${round2.consensus_score}/10`);

  // ── 6. Round 3 ───────────────────────────────────────────────────────────
  console.log("\nRound 3: CIO synthesis...");
  const { round1Text, debateText } = prepareRound3Context(round1, round2, contextWindow);
  const cioPrompt = getCIOPrompt(tier);

  const synthUser = `Security: ${query.ticker} — ${query.company}
Context: ${query.context}

ANALYST REPORTS:
${round1Text}

DEBATE SUMMARY:
${debateText}

Output only the JSON verdict.`;

  const { system: cioSystem, user: cioUser } = adaptPromptsForModel(
    cioPrompt, synthUser, tierConfig.systemPromptMode
  );

  const synthRaw = await callLLMWithRetry(cioSystem, cioUser, tierConfig.maxTokensCIO);
  const report   = extractAndParseJSON(synthRaw);

  report.generated_at   = new Date().toISOString();
  report.provider_used  = `${process.env.LLM_PROVIDER}/${modelName} (${tier})`;
  report.total_time_s   = Math.round((Date.now() - startTime) / 1000);
  report.data_quality_notes = [
    Object.values(round1).filter(r => r.error).map(r => `${r.agent_name}: ${r.error}`).join("; ") || null,
    tier === "tier3" ? "Tier 3 model — reduced agent count and simplified schema" : null,
    !tierConfig.roundsEnabled.includes(2) ? "Debate round skipped (Tier 3)" : null
  ].filter(Boolean).join(" | ") || null;

  console.log(`\n✓ Analysis complete in ${report.total_time_s}s`);
  console.log(`  ${report.ticker} — ${report.verdict} (Conviction: ${report.conviction}/10)`);

  await saveReport(query.ticker, report, round1, round2);
  return report;
}
```

---

## Patch 13 — Hardware requirements and model recommendations

```
MINIMUM VIABLE SETUP (Tier 3 — 5 agents, basic output)
─────────────────────────────────────────────────────
RAM:   8 GB system RAM
VRAM:  None needed (CPU inference)
Model: llama3.2:3b, phi3:mini, gemma3:1b
Speed: ~30–90 seconds total
Quality: Basic — gives a verdict but limited depth

RECOMMENDED LOCAL SETUP (Tier 2 — 10 agents, good output)
──────────────────────────────────────────────────────────
RAM:   16 GB system RAM
VRAM:  8 GB (NVIDIA/AMD GPU) OR Apple Silicon M1/M2/M3 with 16GB unified
Model: llama3.1:8b (8GB VRAM), mistral:7b, qwen2.5:7b, phi4:14b (12GB VRAM)
Speed: ~5–15 minutes total
Quality: Good — comparable to a competent analyst summary

FULL-QUALITY LOCAL SETUP (Tier 1 — 10 agents, near-cloud quality)
──────────────────────────────────────────────────────────────────
RAM:   32 GB system RAM
VRAM:  24 GB (RTX 3090/4090) OR Apple Silicon M2/M3 Pro/Max with 32GB+
Model: llama3.1:70b (Q4 quant: ~40GB), qwen2.5:32b, deepseek-r1:32b
Speed: ~30–90 minutes total (70B models are slow on consumer hardware)
Quality: Excellent — approaches cloud model quality for financial analysis

FASTEST LOCAL OPTION (Tier 2 via Groq — free tier available)
─────────────────────────────────────────────────────────────
Use Groq (https://console.groq.com) with llama3.1:70b or mixtral:8x7b
LLM_PROVIDER=groq (already in base spec providers)
Speed: ~2–4 minutes total (Groq is fast hardware)
Cost: Free tier — 14,400 tokens/minute, 500,000 tokens/day
Note: Cloud-hosted but open weights — a middle ground
```

---

## Patch 14 — Updated implementation checklist (local LLM additions)

Append these to the base spec Section 12 checklist:

```markdown
## Local LLM Setup
- [ ] Ollama/LM Studio/llama.cpp installed and running (test: curl http://localhost:11434/api/tags)
- [ ] Desired model pulled and available (ollama pull llama3.1:8b)
- [ ] LLM_PROVIDER_TYPE=local set in .env
- [ ] LOCAL_LLM_TIMEOUT_MS set appropriately for model size
- [ ] LOCAL_CONTEXT_WINDOW set to match actual model context

## Tier detection
- [ ] detectTier() correctly identifies your model name
- [ ] Tier config logged on startup
- [ ] Correct agent count used (10 for Tier 1/2, 5 for Tier 3)
- [ ] Correct prompts used (full for Tier 1, simplified for Tier 2/3)

## Sequential execution
- [ ] Round 1 runs agents one at a time, NOT in parallel
- [ ] LOCAL_AGENT_DELAY_MS delay between calls
- [ ] Progress logged per agent

## Context management
- [ ] estimateTokens() used before Round 3 call
- [ ] trimRound1Outputs() called if over limit
- [ ] CONVICTION/STANCE lines preserved in truncated outputs

## JSON robustness
- [ ] All 5 extraction strategies implemented
- [ ] extractKeyValueFallback() implemented as last resort
- [ ] data_quality_notes populated when fallback is used

## Output
- [ ] report.provider_used includes model name and tier
- [ ] report.total_time_s populated
- [ ] Tier 3 limitation flagged in data_quality_notes when applicable
```

---

## Summary of all changes vs base spec

| Area | Base spec | This patch |
|---|---|---|
| Providers | Ollama only (1 entry) | Ollama, LM Studio, llama.cpp, Jan, Llamafile |
| Parallelism | `Promise.all` (parallel) | Sequential with delay for local |
| Model tiers | None | 3 tiers with different behavior per tier |
| System prompts | Always native | Native / inject / chatml depending on model |
| Agent count | Always 10 | 10 for Tier 1/2, 5 core agents for Tier 3 |
| Agent prompts | Full (long) | Full for Tier 1, simplified for Tier 2/3 |
| CIO JSON schema | Large nested schema | Tiered: full / simplified / minimal |
| JSON extraction | 3 strategies | 5 strategies + key-value fallback |
| Timeouts | 60s (cloud) | 2–10 mins configurable for local |
| Context management | Mention only | Full trimming logic with token estimation |
| Debate round | Always runs | Skipped for Tier 3, synthetic summary inserted |
| Hardware guide | None | Minimum / recommended / full-quality specs |

---

*End of patch document.*
*Read alongside `stock-intelligence-system-spec.md`. This patch is complete — no other changes to the base spec are required.*
