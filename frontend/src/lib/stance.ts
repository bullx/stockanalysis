import type { AgentOutput } from "./types";

export type SeatTone = "supports" | "mixed" | "against" | "incomplete" | "empty";

export type SeatCall = {
  tone: SeatTone;
  label: string;
  detail?: string;
  score: number | null;
};

const HEADER =
  /^(?:bear case )?(stance|outlook|valuation|moat|bias|sentiment|risk level|esg profile|macro stance|fundamental stance|growth outlook|technical bias)\s*:\s*(.+)$/im;

export function seatCall(agent: Pick<AgentOutput, "agent_id" | "output" | "stance" | "conviction">): SeatCall {
  const text = (agent.output || "").replace(/\*+/g, "");
  if (!text.trim()) {
    return { tone: "empty", label: "No note", detail: "This seat did not return a note.", score: null };
  }

  const header = readHeader(text);
  const score = readScore(text);
  if (!header) {
    const lean = leanWord(text);
    return {
      tone: "incomplete",
      label: "Incomplete",
      detail: lean
        ? `Leans ${lean}. The specialist stopped before a verdict.`
        : "Stopped before a verdict.",
      score: null,
    };
  }

  const label = prettify(agent.agent_id, header);
  return { tone: toneOf(agent.agent_id, label), label, score };
}

function readHeader(text: string): string | null {
  const match = text.match(HEADER);
  if (match) {
    const value = match[2].replace(/\s+/g, " ").trim();
    return value.split(/[.(]/)[0].trim() || null;
  }
  if (/^primary bear thesis\s*:/im.test(text)) return "Bear case";
  const esg = text.match(/esg profile is\s+([A-Za-z]+)/i);
  if (esg) return esg[1];
  return null;
}

function readScore(text: string): number | null {
  const match = text.match(/(?:bear case )?conviction\s*:?\s*(\d{1,2})/i);
  if (!match) return null;
  const n = Number(match[1]);
  return n >= 1 && n <= 10 ? n : null;
}

function leanWord(text: string): string | null {
  const tail = text.slice(-500).toLowerCase();
  if (/\bovervalued|too rich|expensive\b/.test(tail)) return "rich";
  if (/\bundervalued|\bcheap\b/.test(tail)) return "cheap";
  if (/\bfairly valued|fair value\b/.test(tail)) return "fair";
  return null;
}

function prettify(agentId: string, raw: string): string {
  const cleaned = raw.replace(/\s+/g, " ").trim();
  if (/^bear case$/i.test(cleaned)) return "Bear case";
  if (cleaned.length > 36) return agentId === "devil" ? "Bear case" : `${cleaned.slice(0, 32).trim()}…`;
  const key = cleaned.toUpperCase();
  if (agentId === "risk" && key === "HIGH") return "High risk";
  if (agentId === "risk" && key === "MODERATE") return "Moderate risk";
  if (agentId === "risk" && key === "LOW") return "Low risk";
  if (agentId === "sentiment" && key === "OVERCROWDED") return "Crowded";
  if (agentId === "esg" && key === "AVERAGE") return "Average";
  if (key === cleaned && /[A-Z]/.test(cleaned)) {
    return cleaned
      .toLowerCase()
      .replace(/(^|[\s—-])([a-z])/g, (_, sep: string, ch: string) => `${sep}${ch.toUpperCase()}`)
      .replace(" — ", " · ");
  }
  return cleaned.replace(" — ", " · ");
}

function toneOf(agentId: string, label: string): SeatTone {
  const s = label.toUpperCase();
  if (agentId === "risk") {
    if (/HIGH|CRITICAL/.test(s)) return "against";
    if (/LOW/.test(s)) return "supports";
    return "mixed";
  }
  if (agentId === "sentiment") {
    if (/CROWD|EUPHOR/.test(s)) return "against";
    if (/NEGLECT|FAVOR/.test(s)) return "supports";
    return "mixed";
  }
  if (agentId === "devil") return "against";
  if (/SELL|AVOID|BEAR|OVERVAL|WEAK|DECLIN|HEADWIND|NARROW|LAGGARD|HIGH RISK/.test(s)) return "against";
  if (/NEUTRAL|FAIR|AVERAGE|MODERATE|MIXED|BALANCED/.test(s)) return "mixed";
  if (/BUY|BULL|STRONG|WIDE|UNDERVAL|LEADER|TAILWIND|LOW/.test(s)) return "supports";
  return "mixed";
}

export function toneClass(tone: SeatTone): string {
  if (tone === "supports") return "text-go bg-go/10 ring-go/25";
  if (tone === "against") return "text-stop bg-stop/10 ring-stop/25";
  if (tone === "mixed") return "text-warn bg-warn/10 ring-warn/25";
  return "text-mute bg-black/[0.04] ring-line";
}
