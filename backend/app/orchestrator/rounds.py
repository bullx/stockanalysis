import asyncio
from datetime import datetime, timezone
from typing import Awaitable, Callable

from backend.app.agents.debate import (
    DEBATE_SYSTEM_PROMPT,
    build_debate_user_message,
    build_synthetic_debate,
)
from backend.app.agents.definitions import AGENT_DEFINITIONS, CORE_AGENT_IDS
from backend.app.agents.simplified import SIMPLIFIED_AGENT_PROMPTS
from backend.app.orchestrator.normalize import build_agent_user_message
from backend.app.utils.llm import _fatal_llm_error, call_llm_with_retry
from backend.app.utils.parse import debate_is_empty, parse_agent_output, parse_debate_output
from backend.app.utils.prompt_adapter import adapt_prompts_for_model

Emit = Callable[[dict], Awaitable[None]]


async def run_round1(
    query: dict,
    tier: dict,
    sequential: bool,
    delay_ms: int,
    emit: Emit,
    llm_opts: dict,
    agent_ids: list[str] | None = None,
) -> dict:
    wanted = agent_ids or CORE_AGENT_IDS
    by_id = {agent["id"]: agent for agent in AGENT_DEFINITIONS}
    agent_defs = [by_id[agent_id] for agent_id in wanted if agent_id in by_id]
    round1: dict = {}
    total = len(agent_defs)
    await emit(
        {
            "type": "round1.started",
            "total": total,
            "agent_ids": [a["id"] for a in agent_defs],
        }
    )

    async def run_one(index: int, agent: dict) -> tuple[str, dict]:
        await emit(
            {
                "type": "agent.started",
                "agent_id": agent["id"],
                "agent_name": agent["name"],
                "tag": agent["tag"],
                "index": index,
                "total": total,
            }
        )
        system_prompt = (
            SIMPLIFIED_AGENT_PROMPTS[agent["id"]]
            if tier.get("simplify_prompts")
            else agent["system_prompt"]
        )
        user_message = build_agent_user_message(agent, query)
        adapted = adapt_prompts_for_model(
            system_prompt, user_message, tier.get("system_prompt_mode") or "native"
        )
        try:
            raw = await call_llm_with_retry(
                adapted["system"],
                adapted["user"],
                tier["max_tokens_agent"],
                options=llm_opts,
            )
            if agent["id"] == "devil":
                parsed_try = parse_agent_output(raw)
                if parsed_try["conviction"] < 4:
                    raw = await call_llm_with_retry(
                        adapted["system"],
                        adapted["user"]
                        + "\n\nConstruct a more aggressive bear case. Give me the path to -40%.",
                        tier["max_tokens_agent"],
                        options=llm_opts,
                    )
            parsed = parse_agent_output(raw)
            if not (parsed.get("output") or "").strip():
                raise RuntimeError("Empty model response")
            record = {
                "agent_id": agent["id"],
                "agent_name": agent["name"],
                "tag": agent["tag"],
                **parsed,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as exc:  # noqa: BLE001
            record = {
                "agent_id": agent["id"],
                "agent_name": agent["name"],
                "tag": agent["tag"],
                "output": f"AGENT_ERROR: {exc}",
                "conviction": 5,
                "stance": "unknown",
                "error": str(exc),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            await emit({"type": "agent.completed", **record})
            if _fatal_llm_error(exc):
                gate = llm_opts.get("gate")
                if gate:
                    await gate.request_stop()
                raise
            return agent["id"], record
        await emit({"type": "agent.completed", **record})
        return agent["id"], record

    if sequential:
        for i, agent in enumerate(agent_defs):
            gate = llm_opts.get("gate")
            if gate:
                gate.raise_if_stopped()
            agent_id, record = await run_one(i, agent)
            round1[agent_id] = record
            if i < total - 1:
                await asyncio.sleep(delay_ms / 1000)
    else:
        results = await asyncio.gather(*[run_one(i, a) for i, a in enumerate(agent_defs)])
        round1 = dict(results)

    ok = sum(1 for r in round1.values() if not r.get("error"))
    await emit({"type": "round1.completed", "succeeded": ok, "total": total})
    return round1


async def run_round2(query: dict, round1: dict, tier: dict, emit: Emit, llm_opts: dict) -> dict:
    if 2 not in tier.get("rounds_enabled", [1, 2, 3]):
        debate = build_synthetic_debate(round1)
        await emit({"type": "round2.skipped", "debate": debate})
        return debate

    usable = [
        r
        for r in round1.values()
        if (r.get("output") or "").strip() and not r.get("error")
    ]
    if not usable:
        debate = {
            "consensus_points": [],
            "key_disagreements": [],
            "strongest_bull": "",
            "strongest_bear": "",
            "swing_factor": "",
            "unresolved_questions": [],
            "consensus_score": 5,
            "raw_text": "",
            "empty": True,
        }
        await emit({"type": "round2.skipped", "reason": "no_agent_notes", "debate": debate})
        return debate

    await emit({"type": "round2.started"})
    adapted = adapt_prompts_for_model(
        DEBATE_SYSTEM_PROMPT,
        build_debate_user_message(query, round1),
        tier.get("system_prompt_mode") or "native",
    )
    raw = await call_llm_with_retry(
        adapted["system"], adapted["user"], tier["max_tokens_debate"], options=llm_opts
    )
    debate = parse_debate_output(raw)
    if debate_is_empty(debate):
        debate = build_synthetic_debate(round1)
        debate["fallback"] = "empty_moderator"
    await emit({"type": "round2.completed", "debate": debate})
    return debate
