from backend.app.agents.definitions import AGENT_DEFINITIONS


def estimate_tokens(text: str) -> int:
    return max(1, (len(text or "") + 3) // 4)


def trim_round1_outputs(round1: dict, max_tokens: int) -> str:
    agents = [a for a in AGENT_DEFINITIONS if a["id"] in round1]
    if not agents:
        return ""
    tokens_each = max(80, max_tokens // max(len(agents), 1))
    chunks = []
    for agent in agents:
        out = round1[agent["id"]]
        text = out.get("output") or ""
        lines = text.split("\n")
        tail = "\n".join(lines[-3:])
        budget = tokens_each * 4 - len(tail)
        body = text[: max(budget, 80)].strip()
        chunks.append(f"=== {agent['name'].upper()} ===\n{body}\n...\n{tail}")
    return "\n\n".join(chunks)


def prepare_round3_context(round1: dict, debate: dict, context_window: int) -> tuple[str, str]:
    available = context_window - 2500
    round1_text = "\n\n".join(
        f"=== {a['name'].upper()} ===\n{round1[a['id']].get('output', '')}"
        for a in AGENT_DEFINITIONS
        if a["id"] in round1
    )
    debate_text = debate.get("raw_text") or ""
    available_r1 = available - estimate_tokens(debate_text) - 200
    if estimate_tokens(round1_text) > available_r1:
        round1_text = trim_round1_outputs(round1, available_r1)
    return round1_text, debate_text
