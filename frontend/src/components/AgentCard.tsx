import { Loader2 } from "lucide-react";
import { seatCall, toneClass } from "../lib/stance";
import type { AgentOutput } from "../lib/types";

type Status = "queued" | "running" | "done" | "error" | "stopped";

export default function AgentCard({
  name,
  tag,
  status,
  data,
}: {
  name: string;
  tag: string;
  status: Status;
  data?: AgentOutput;
}) {
  return (
    <article
      className={`glass flex min-h-[156px] flex-col rounded-2xl p-4 transition-colors duration-200 ${
        status === "running" ? "ring-1 ring-cta/50 shadow-glow" : ""
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[10px] uppercase tracking-[0.2em] text-gold/70">{tag}</p>
          <h3 className="mt-1 font-sans text-base font-semibold leading-tight tracking-tight">{name}</h3>
        </div>
        <StatusDot status={status} />
      </div>
      {status === "done" && data && <SeatFooter data={data} />}
      {status === "running" && (
        <p className="mt-auto flex items-center gap-2 pt-4 text-xs text-gold">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          Writing brief
        </p>
      )}
      {status === "error" && (
        <p className="mt-auto pt-4 text-xs text-stop">Agent failed — placeholder inserted</p>
      )}
      {status === "queued" && <p className="mt-auto pt-4 text-xs text-mute">Waiting to speak</p>}
      {status === "stopped" && <p className="mt-auto pt-4 text-xs text-mute">Stopped</p>}
    </article>
  );
}

function SeatFooter({ data }: { data: AgentOutput }) {
  const call = seatCall(data);
  return (
    <div className="mt-auto pt-4">
      <div className="flex items-baseline justify-between gap-2">
        <span className={`truncate rounded-full px-2 py-0.5 text-xs font-medium ring-1 ${toneClass(call.tone)}`}>
          {call.label}
        </span>
        <span className="font-mono text-sm tabular-nums text-gold">{call.score != null ? `${call.score}/10` : "—"}</span>
      </div>
      {call.score != null && (
        <div className="mt-2 h-1 overflow-hidden rounded-full bg-black/10">
          <div className="h-full rounded-full bg-gradient-to-r from-cta to-gold" style={{ width: `${call.score * 10}%` }} />
        </div>
      )}
      {call.detail && <p className="mt-2 text-[11px] leading-snug text-mute">{call.detail}</p>}
    </div>
  );
}

function StatusDot({ status }: { status: Status }) {
  const map = {
    queued: "bg-mute/40",
    running: "bg-cta animate-pulse",
    done: "bg-go",
    error: "bg-stop",
    stopped: "bg-mute/40",
  };
  return <span className={`mt-1 inline-block h-2 w-2 rounded-full ${map[status]}`} />;
}
