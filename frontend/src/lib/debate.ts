import type { Debate } from "./types";

const MARKERS = [
  "CONSENSUS POINTS",
  "KEY DISAGREEMENTS",
  "STRONGEST BULL THESIS",
  "STRONGEST BEAR THESIS",
  "SWING FACTOR",
  "UNRESOLVED QUESTIONS",
  "CONSENSUS SCORE",
];

function unwrap(text: string) {
  return text
    .replace(/\*\*(.+?)\*\*/g, "$1")
    .replace(/__(.+?)__/g, "$1")
    .replace(/^#{1,3}\s*/gm, "")
    .trim();
}

function section(text: string, header: string) {
  const look = MARKERS.join("|");
  const re = new RegExp(`${header}\\s*:?\\s*\\n([\\s\\S]*?)(?=\\n(?:${look})\\b|$)`, "i");
  return (text.match(re)?.[1] || "").trim();
}

function bullets(block: string) {
  return block
    .split("\n")
    .map((ln) => ln.replace(/^[-*\d.)\s]+/, "").trim())
    .filter((ln) => ln && !MARKERS.includes(ln.toUpperCase()))
    .slice(0, 5);
}

export function debateHasStructure(debate?: Debate | null) {
  if (!debate) return false;
  return Boolean(
    debate.strongest_bull ||
      debate.strongest_bear ||
      debate.swing_factor ||
      debate.consensus_points?.length ||
      debate.key_disagreements?.length ||
      debate.unresolved_questions?.length,
  );
}

export function hydrateDebate(debate?: Debate | null): Debate | null {
  if (!debate) return null;
  if (debateHasStructure(debate)) return debate;
  const raw = debate.raw_text || "";
  if (!raw.trim()) return debate;
  const text = unwrap(raw);
  const swing = section(text, "SWING FACTOR");
  const score = text.match(/CONSENSUS SCORE\s*:?\s*(\d+)/i);
  return {
    ...debate,
    consensus_points: bullets(section(text, "CONSENSUS POINTS")),
    key_disagreements: bullets(section(text, "KEY DISAGREEMENTS")),
    strongest_bull: section(text, "STRONGEST BULL THESIS"),
    strongest_bear: section(text, "STRONGEST BEAR THESIS"),
    swing_factor: swing.split("\n")[0] || "",
    unresolved_questions: bullets(section(text, "UNRESOLVED QUESTIONS")),
    consensus_score: score ? Number(score[1]) : debate.consensus_score,
    raw_text: raw,
  };
}
