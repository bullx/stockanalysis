import { verdictBg } from "../lib/format";

export default function VerdictMark({ verdict, large }: { verdict: string; large?: boolean }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-3 py-1 font-medium uppercase tracking-[0.16em] ${verdictBg(
        verdict,
      )} ${large ? "text-xs" : "text-[10px]"}`}
    >
      {verdict}
    </span>
  );
}
