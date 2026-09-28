export function verdictTone(verdict?: string) {
  const v = (verdict || "").toUpperCase();
  if (v.includes("STRONG BUY") || v === "BUY") return "text-go";
  if (v.includes("AVOID") || v.includes("SELL")) return "text-stop";
  return "text-warn";
}

export function verdictBg(verdict?: string) {
  const v = (verdict || "").toUpperCase();
  if (v.includes("STRONG BUY") || v === "BUY") return "bg-go/15 text-go";
  if (v.includes("AVOID") || v.includes("SELL")) return "bg-stop/15 text-stop";
  return "bg-warn/15 text-warn";
}

export function stanceTone(stance?: string) {
  const s = (stance || "").toUpperCase();
  if (
    /BUY|UNDERVALUED|EXCEPTIONAL|STRONG|WIDE|TAILWIND|BULLISH|LEADER|LOW/.test(s) &&
    !/HEADWIND|OVERVALUED|OVERCROWDED|BEAR|SELL|HIGH|CRITICAL|LAGGARD|NONE/.test(s)
  ) {
    return "text-go";
  }
  if (/SELL|OVERVALUED|WEAK|DECLINING|NONE|HEADWIND|BEARISH|HIGH|CRITICAL|LAGGARD|RED FLAG|OUT OF FAVOR/.test(s)) {
    return "text-stop";
  }
  return "text-mute";
}

export function formatTime(iso?: string) {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}
