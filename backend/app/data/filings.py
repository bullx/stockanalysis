"""Download, split, diff, and red-flag SEC filings. No LLM calls here."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any
from xml.etree import ElementTree as ET

from backend.app.data.cache import cache_get, cache_set
from backend.app.data.http import get_json, get_text, sec_headers
from backend.app.data.sec import list_filings, pad_cik
from backend.app.settings import get_settings

RED_FLAGS = [
    "material weakness",
    "going concern",
    "substantial doubt",
    "restatement",
    "unable to file",
    "non-reliance",
]

ITEM_HEADERS = [
    ("1A", re.compile(r"item\s+1a\s*[\.\:]\s*(?:risk factors|risks)\b", re.I)),
    ("7", re.compile(r"item\s+7\s*[\.\:]\s*management", re.I)),
    ("7A", re.compile(r"item\s+7a\s*[\.\:]", re.I)),
    ("8", re.compile(r"item\s+8\s*[\.\:]\s*financial", re.I)),
    ("1", re.compile(r"item\s+1\s*[\.\:]\s*business", re.I)),
]


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = False

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style"}:
            self._skip = True
        if tag in {"p", "div", "br", "tr", "h1", "h2", "h3", "li"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            self._skip = False

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)


def strip_html(raw: str) -> str:
    if "<html" in raw.lower() or "<div" in raw.lower() or "<p" in raw.lower():
        parser = _TextExtractor()
        try:
            parser.feed(raw)
            text = "".join(parser.parts)
        except Exception:  # noqa: BLE001
            text = re.sub(r"<[^>]+>", " ", raw)
    else:
        text = raw
    text = re.sub(r"\r", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_items(text: str) -> dict[str, str]:
    """Split a 10-K/10-Q into Item sections. Missing items are omitted, never guessed.

    Cross-references ("Item 1A of this Form 10-K") are not headers. When a real
    header appears more than once, the copy with the longest following body is kept.
    """
    found: list[tuple[int, str]] = []
    for name, pattern in ITEM_HEADERS:
        for match in pattern.finditer(text):
            found.append((match.start(), name))
    if not found:
        return {}
    found.sort()
    later = [hit for hit in found if hit[0] > len(text) * 0.05]
    use = later or found
    positions = [pos for pos, _ in found]
    best: dict[str, tuple[int, int]] = {}
    for pos, name in use:
        nxt = next((p for p in positions if p > pos + 30), len(text))
        span = nxt - pos
        prev = best.get(name)
        if prev is None or span > prev[1]:
            best[name] = (pos, span)
    sections: dict[str, str] = {}
    for name, (pos, span) in best.items():
        body = text[pos : pos + span].strip()
        if len(body) > 80:
            sections[name] = body
    return sections


def paragraphs(text: str) -> list[str]:
    chunks = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", text)]
    return [c for c in chunks if len(c) > 40]


def _clip_chunk(text: str, limit: int = 480) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    window = text[:limit]
    dot = window.rfind(". ")
    if dot >= 160:
        return window[: dot + 1]
    return window.rstrip() + "…"


def diff_units(text: str) -> list[str]:
    """Sentence-sized chunks so a changed line is not the whole Item."""
    units: list[str] = []
    pending = ""
    for para in paragraphs(text):
        parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", para) if p.strip()]
        for sentence in parts:
            if pending and len(pending) + 1 + len(sentence) > 420:
                units.append(_clip_chunk(pending))
                pending = sentence
            else:
                pending = f"{pending} {sentence}".strip()
            if len(pending) >= 80:
                units.append(_clip_chunk(pending))
                pending = ""
        if len(pending) > 40:
            units.append(_clip_chunk(pending))
        pending = ""
    return units


def diff_sections(old: str, new: str, limit: int = 8) -> dict[str, list[str]]:
    old_units = diff_units(old)
    new_units = diff_units(new)
    old_set = set(old_units)
    new_set = set(new_units)
    added = [_clip_chunk(p) for p in new_units if p not in old_set][:limit]
    removed = [_clip_chunk(p) for p in old_units if p not in new_set][:limit]
    return {"added": added, "removed": removed}


_GUIDANCE_CUE = re.compile(
    r"\b("
    r"guidance|outlook|"
    r"expect(?:s|ed|ing)?|"
    r"forecast(?:s|ed|ing)?|"
    r"rais(?:e|ed|ing)|lower(?:s|ed|ing)|reaffirm(?:s|ed|ing)|"
    r"full[- ]year|fiscal (?:year|20\d\d)"
    r")\b",
    re.I,
)
_FIGURE = re.compile(
    r"("
    r"\$[\d,]+(?:\.\d+)?"
    r"|\d+(?:\.\d+)?\s*(?:%|percent|billion|million)"
    r"|(?:low|mid|high|double)[- ](?:single[- ])?digits"
    r")",
    re.I,
)
_OUTLOOK_HEADING = re.compile(
    r"(financial outlook|business outlook|company outlook|\bguidance\b|\boutlook\b)",
    re.I,
)


_CUSTOMER = re.compile(
    r"[^.]{0,100}(?:customer|client|distributor)[^.]{0,100}\d+(?:\.\d+)?\s*(?:%|percent)"
    r"|[^.]{0,100}\d+(?:\.\d+)?\s*(?:%|percent)[^.]{0,100}(?:customer|client|distributor)",
    re.I,
)


def extract_customer_concentration(text: str, limit: int = 4) -> list[str]:
    """Sentences that tie a customer to a percent of sales. Empty when the filing does not say so."""
    if not text:
        return []
    flat = re.sub(r"\s+", " ", text)
    hits: list[str] = []
    seen: set[str] = set()
    for match in _CUSTOMER.finditer(flat):
        snippet = match.group(0).strip()
        if len(snippet) < 24:
            continue
        key = snippet[:100].lower()
        if key in seen:
            continue
        seen.add(key)
        hits.append(snippet[:320])
        if len(hits) >= limit:
            break
    return hits


def extract_guidance(text: str, limit: int = 6) -> list[str]:
    """Outlook lines from an earnings release. Empty when no figure or cue is present."""
    if not text:
        return []
    flat = text.replace("\r", "")
    heading = _OUTLOOK_HEADING.search(flat)
    window = flat[heading.start() : heading.start() + 3500] if heading else flat
    hits: list[str] = []
    seen: set[str] = set()
    pieces = re.split(r"\n+|(?<=[.!?])\s+", window)
    for piece in pieces:
        piece = re.sub(r"\s+", " ", piece).strip(" •·-\t")
        if len(piece) < 28:
            continue
        has_figure = _FIGURE.search(piece) is not None
        has_cue = _GUIDANCE_CUE.search(piece) is not None
        if heading:
            if not (has_figure or has_cue):
                continue
        elif not (has_figure and has_cue):
            continue
        clipped = piece[:480]
        if clipped in seen:
            continue
        seen.add(clipped)
        hits.append(clipped)
        if len(hits) >= limit:
            break
    return hits


def archive_names(index_json: Any) -> list[str]:
    if not isinstance(index_json, dict):
        return []
    raw = (index_json.get("directory") or {}).get("item") or []
    if isinstance(raw, dict):
        raw = [raw]
    names: list[str] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "")
        if not name or name.endswith("/"):
            continue
        base = name.split("/")[-1]
        lower = base.lower()
        if lower in {"index.html", "index.json"} or lower.endswith("-index.html"):
            continue
        names.append(base)
    return names


def pick_exhibit_99_1(names: list[str]) -> str | None:
    """Prefer a 99.1 press release over a generic exhibit 99 or an earnings filename."""
    best: str | None = None
    best_rank = 99
    for name in names:
        base = name.split("?")[0].split("/")[-1]
        if not base:
            continue
        rank = _exhibit_rank(base)
        if rank < best_rank:
            best = base
            best_rank = rank
    return best if best_rank < 99 else None


def _exhibit_rank(name: str) -> int:
    n = name.lower()
    if re.search(r"(?:ex|exhibit)", n) and re.search(r"99(?:[._-]|d)?1", n):
        return 0
    if re.search(r"(?:ex|exhibit)[-_]?99", n):
        return 1
    if "earnings" in n and n.endswith((".htm", ".html", ".txt")):
        return 2
    return 99


_HREF = re.compile(r"""href=["']([^"']+)["']""", re.I)


def href_names(html: str) -> list[str]:
    names: list[str] = []
    for href in _HREF.findall(html or ""):
        base = href.split("?")[0].split("/")[-1]
        if base:
            names.append(base)
    return names


_NEGATED = (
    "no material weakness",
    "not identify a material weakness",
    "without material weakness",
    "risk that a material weakness",
    "whether a material weakness",
    "if a material weakness",
    "did not restat",
    "no restatement",
    "not a restatement",
    "without restatement",
    "are restatements that required",
    "error corrections are restatements",
)


def scan_red_flags(text: str, source: str) -> list[dict[str, str]]:
    found = []
    lower = text.lower()
    for phrase in RED_FLAGS:
        start_at = 0
        while True:
            idx = lower.find(phrase, start_at)
            if idx < 0:
                break
            window = lower[max(0, idx - 60) : idx + 80]
            if any(neg in window for neg in _NEGATED):
                start_at = idx + len(phrase)
                continue
            start = max(0, idx - 80)
            end = min(len(text), idx + 120)
            snippet = re.sub(r"\s+", " ", text[start:end]).strip()
            found.append({"phrase": phrase, "source": source, "snippet": snippet})
            break
    return found


def filing_url(cik: str | int, accession_nodash: str, primary: str) -> str:
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_nodash}/{primary}"


async def download_filing(cik: str | int, accession_nodash: str, primary: str, output_dir: str = "output") -> str | None:
    key = f"{accession_nodash}_{primary}"
    cached = cache_get("filings", key, ttl_s=0, output_dir=output_dir)  # never expires
    if cached is not None:
        return cached
    url = filing_url(cik, accession_nodash, primary)
    headers = sec_headers(get_settings().sec_user_agent)
    # Archives live on www.sec.gov
    text = await get_text(url, headers=headers, timeout=45.0)
    if not text:
        return None
    cache_set("filings", key, text, output_dir=output_dir)
    return text


async def list_archive_names(
    cik: str | int,
    accession: str,
    accession_nodash: str,
    output_dir: str = "output",
) -> list[str]:
    key = f"index_{accession_nodash}"
    cached = cache_get("filings", key, ttl_s=0, output_dir=output_dir)
    if isinstance(cached, list) and cached:
        return cached
    url = (
        f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
        f"{accession_nodash}/{accession}-index.json"
    )
    data = await get_json(url, headers=sec_headers(get_settings().sec_user_agent), timeout=30.0)
    names = archive_names(data)
    if names:
        cache_set("filings", key, names, output_dir=output_dir)
    return names


async def load_exhibit_99_1(
    cik: str | int,
    filing: dict[str, Any],
    output_dir: str = "output",
) -> dict[str, Any] | None:
    """Download Exhibit 99.1 for an Item 2.02 8-K. None when the index has no match."""
    names = await list_archive_names(
        cik, filing.get("accession") or "", filing.get("accession_nodash") or "", output_dir
    )
    chosen = pick_exhibit_99_1(names)
    if not chosen and filing.get("primary"):
        raw = await download_filing(cik, filing["accession_nodash"], filing["primary"], output_dir)
        chosen = pick_exhibit_99_1(href_names(raw or ""))
    if not chosen:
        return None
    if chosen.lower().endswith(".pdf"):
        return {"name": chosen, "pdf": True, "text": ""}
    text = await download_filing(cik, filing["accession_nodash"], chosen, output_dir)
    if not text:
        return None
    if text.lstrip()[:8].startswith("%PDF"):
        return {"name": chosen, "pdf": True, "text": ""}
    return {"name": chosen, "pdf": False, "text": text}


def _local(tag: str) -> str:
    return tag.split("}")[-1].lower()


def parse_form4_net(xml_text: str) -> dict[str, float]:
    """Net shares bought (P) minus sold (S), skipping option exercises (M, A)."""
    bought = 0.0
    sold = 0.0
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return {"bought": 0.0, "sold": 0.0, "net": 0.0}
    for node in root.iter():
        if _local(node.tag) != "nonderivativetransaction":
            continue
        code = ""
        shares = 0.0
        acquired = ""
        for child in node.iter():
            name = _local(child.tag)
            if name == "transactioncode" and child.text:
                code = child.text.strip().upper()
            if name == "transactionshares":
                val = child.find(".//{*}value")
                if val is None:
                    for sub in child:
                        if _local(sub.tag) == "value" and sub.text:
                            try:
                                shares = float(sub.text)
                            except ValueError:
                                pass
                elif val.text:
                    try:
                        shares = float(val.text)
                    except ValueError:
                        pass
            if name == "transactionacquireddisposedcode" and child.text:
                acquired = child.text.strip().upper()
        if code in {"M", "A", "F", "D", "C", "X"}:
            continue
        if code == "P" or (code == "P" or acquired == "A" and code in {"P", "I"}):
            bought += shares
        elif code == "S" or acquired == "D":
            sold += shares
    return {"bought": bought, "sold": sold, "net": bought - sold}


async def build_filings_digest(
    cik: str | int,
    submissions: dict[str, Any],
    output_dir: str = "output",
    max_docs: int = 6,
) -> dict[str, Any]:
    """Code-only digest: latest 10-K/10-Q diffs, 8-K events, Form 4 net, red flags."""
    tens = list_filings(submissions, {"10-K", "10-Q", "20-F"}, limit=8)
    eights = list_filings(submissions, {"8-K"}, limit=12)
    forms4 = list_filings(submissions, {"4"}, limit=20)

    latest_k = next((f for f in tens if f["form"].upper() in {"10-K", "20-F"}), None)
    prior_k = None
    if latest_k:
        prior_k = next(
            (f for f in tens if f["form"] == latest_k["form"] and f["accession"] != latest_k["accession"]),
            None,
        )
    latest_q = next((f for f in tens if f["form"].upper() == "10-Q"), None)

    sections_new: dict[str, str] = {}
    sections_old: dict[str, str] = {}
    flags: list[dict[str, str]] = []
    docs_read = 0

    async def load_split(filing: dict[str, Any] | None) -> dict[str, str]:
        nonlocal docs_read, flags
        if not filing or docs_read >= max_docs:
            return {}
        raw = await download_filing(cik, filing["accession_nodash"], filing["primary"], output_dir)
        docs_read += 1
        if not raw:
            return {}
        text = strip_html(raw)
        flags.extend(scan_red_flags(text, f"{filing['form']} {filing['filed']}"))
        return split_items(text)

    sections_new = await load_split(latest_k or latest_q)
    sections_old = await load_split(prior_k)

    diffs: dict[str, Any] = {}
    for item in ("1A", "7"):
        if item in sections_new and item in sections_old:
            diffs[item] = diff_sections(sections_old[item], sections_new[item])
        elif item in sections_new:
            diffs[item] = {
                "added": [_clip_chunk(p) for p in diff_units(sections_new[item])[:3]],
                "removed": [],
                "note": "No prior filing to diff",
            }
        else:
            diffs[item] = {"added": [], "removed": [], "note": f"Item {item} not found"}

    event_8k = []
    for f in eights[:8]:
        items = f.get("items") or ""
        event_8k.append(
            {
                "filed": f["filed"],
                "items": items,
                "accession": f["accession"],
                "auditor_change": "4.01" in items,
                "executive_departure": "5.02" in items,
                "earnings": "2.02" in items,
            }
        )
        if "4.01" in items:
            flags.append({"phrase": "auditor change", "source": f"8-K {f['filed']}", "snippet": "Item 4.01"})
        if "5.02" in items:
            flags.append({"phrase": "executive departure", "source": f"8-K {f['filed']}", "snippet": "Item 5.02"})

    earnings = next((e for e in event_8k if e["earnings"]), None)
    earnings_filing = next((f for f in eights if "2.02" in (f.get("items") or "")), None)

    insider = {"bought": 0.0, "sold": 0.0, "net": 0.0, "forms": 0}
    for f in forms4[:8]:
        if docs_read >= max_docs + 4:
            break
        raw = await download_filing(cik, f["accession_nodash"], f["primary"], output_dir)
        docs_read += 1
        if not raw:
            continue
        parsed = parse_form4_net(raw)
        insider["bought"] += parsed["bought"]
        insider["sold"] += parsed["sold"]
        insider["net"] += parsed["net"]
        insider["forms"] += 1

    guidance: list[str] = []
    guidance_note = None
    guidance_source = None
    if earnings_filing:
        exhibit = None
        try:
            exhibit = await load_exhibit_99_1(cik, earnings_filing, output_dir)
        except Exception:  # noqa: BLE001
            guidance_note = "Exhibit 99.1 lookup failed."
        if exhibit and exhibit.get("pdf"):
            guidance_note = f"Exhibit 99.1 ({exhibit['name']}) is a PDF. Guidance text was not extracted."
        elif exhibit and exhibit.get("text"):
            guidance = extract_guidance(strip_html(exhibit["text"]))
            guidance_source = (
                f"{exhibit['name']} from the Item 2.02 8-K filed {earnings_filing.get('filed')}"
            )
            if not guidance:
                guidance_note = (
                    f"Exhibit 99.1 ({exhibit['name']}) downloaded. "
                    "No outlook paragraph with a figure was found."
                )
        elif guidance_note is None:
            guidance_note = "Item 2.02 8-K found. Exhibit 99.1 was not in the filing index."

    concentration_blob = "\n".join(sections_new.get(item, "") for item in ("1", "1A", "8") if sections_new.get(item))
    customer_concentration = extract_customer_concentration(concentration_blob)

    latest_filing = latest_k or latest_q
    return {
        "latest_annual": latest_k,
        "latest_quarterly": latest_q,
        "latest_filing": latest_filing,
        "risk_diff": diffs.get("1A"),
        "mda_diff": diffs.get("7"),
        "items_found": list(sections_new.keys()),
        "red_flags": flags[:12],
        "eight_k": event_8k,
        "earnings_8k": earnings,
        "guidance": guidance,
        "guidance_source": guidance_source,
        "guidance_note": guidance_note,
        "customer_concentration": customer_concentration,
        "insider_90d": insider,
        "coverage": "partial" if not sections_new else "ok",
    }


def format_filings_digest(digest: dict[str, Any]) -> str:
    if not digest:
        return "FILINGS: none available (non-US or lookup failed)."
    lines = ["FILINGS DIGEST (code-extracted from SEC EDGAR — cite these, do not invent filings):"]
    latest = digest.get("latest_annual") or digest.get("latest_quarterly")
    if latest:
        lines.append(f"- Latest {latest.get('form')} filed {latest.get('filed')} (accession {latest.get('accession')})")
    if digest.get("items_found"):
        lines.append(f"- Sections found: {', '.join('Item ' + i for i in digest['items_found'])}")
    else:
        lines.append("- Could not split Item sections. Do not invent Risk Factors or MD&A quotes.")

    rd = digest.get("risk_diff") or {}
    if rd.get("added"):
        lines.append("- New / changed Risk Factor paragraphs vs prior year:")
        for p in rd["added"][:4]:
            lines.append(f"  • {p[:280]}")
    elif rd.get("note"):
        lines.append(f"- Risk Factors: {rd['note']}")

    md = digest.get("mda_diff") or {}
    if md.get("added"):
        lines.append("- New / changed MD&A paragraphs vs prior year:")
        for p in md["added"][:3]:
            lines.append(f"  • {p[:280]}")

    flags = digest.get("red_flags") or []
    if flags:
        lines.append("- Red flags (keyword scan, not a legal conclusion):")
        for f in flags[:6]:
            lines.append(f"  • [{f['source']}] “{f['phrase']}” — {f['snippet'][:160]}")
    else:
        lines.append("- Red-flag scan: none of the watched phrases were found.")

    earn = digest.get("earnings_8k")
    if earn:
        lines.append(
            f"- Latest earnings 8-K (Item 2.02) filed {earn['filed']} (accession {earn.get('accession')})."
        )
    guidance = digest.get("guidance") or []
    if guidance:
        source = digest.get("guidance_source") or "Exhibit 99.1"
        lines.append(f"- Guidance excerpts from {source} (code-extracted; cite these, do not invent figures):")
        for snippet in guidance[:6]:
            lines.append(f"  • {snippet[:400]}")
    elif digest.get("guidance_note"):
        lines.append(f"- {digest['guidance_note']}")
    elif earn:
        lines.append("- Exhibit 99.1 guidance was not extracted.")
    else:
        lines.append("- No Item 2.02 earnings 8-K found in the recent list.")

    customers = digest.get("customer_concentration") or []
    if customers:
        lines.append("- Customer concentration (filing sentences that name a customer and a percent; not a model guess):")
        for snippet in customers[:4]:
            lines.append(f"  • {snippet[:300]}")
    else:
        lines.append("- Customer concentration: no sentence tying a customer to a percent of sales was found.")

    ins = digest.get("insider_90d") or {}
    lines.append(
        f"- Form 4 (sample of {ins.get('forms', 0)} filings): "
        f"bought {ins.get('bought', 0):,.0f} / sold {ins.get('sold', 0):,.0f} / net {ins.get('net', 0):,.0f} shares. "
        "Option exercises excluded. This is not a complete 90-day tape."
    )
    return "\n".join(lines)
