import json
import re
from datetime import datetime, timezone
from pathlib import Path

_REPORT_ID = re.compile(r"^[A-Za-z0-9._-]+$")

from backend.app.utils.format import render_markdown_report


def save_report(output_dir: str, ticker: str, report: dict, round1: dict, round2: dict) -> dict[str, str]:
    root = Path(output_dir)
    reports = root / "reports"
    rendered = root / "rendered"
    reports.mkdir(parents=True, exist_ok=True)
    rendered.mkdir(parents=True, exist_ok=True)
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    stamp = datetime.now(timezone.utc).strftime("%H%M%S")
    base = f"{ticker}_{day}_{stamp}"
    report["id"] = base
    payload = {"report": report, "round1": round1, "round2": round2}
    json_path = reports / f"{base}.json"
    md_path = rendered / f"{base}.md"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown_report(report), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path), "id": base}


def list_reports(output_dir: str) -> list[dict]:
    reports = Path(output_dir) / "reports"
    if not reports.exists():
        return []
    items = []
    for path in sorted(reports.glob("*.json"), reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            report = data.get("report") or data
            items.append(
                {
                    "id": path.stem,
                    "ticker": report.get("ticker"),
                    "verdict": report.get("verdict"),
                    "conviction": report.get("conviction"),
                    "title": report.get("title"),
                    "generated_at": report.get("generated_at"),
                    "provider_used": report.get("provider_used"),
                }
            )
        except (json.JSONDecodeError, OSError):
            continue
    return items[:50]


def delete_report(output_dir: str, report_id: str) -> bool:
    """Remove one saved brief from this machine. The id cannot contain a path."""
    if not _REPORT_ID.fullmatch(report_id or ""):
        return False
    removed = False
    for folder, suffix in (("reports", ".json"), ("rendered", ".md")):
        path = Path(output_dir) / folder / f"{report_id}{suffix}"
        if path.is_file():
            path.unlink()
            removed = True
    return removed


def load_report(output_dir: str, report_id: str) -> dict | None:
    path = Path(output_dir) / "reports" / f"{report_id}.json"
    if not path.exists() or not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    data["id"] = path.stem
    return data


def load_all_reports(output_dir: str) -> list[dict]:
    reports = Path(output_dir) / "reports"
    if not reports.exists():
        return []
    rows = []
    for path in sorted(reports.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        data["id"] = path.stem
        rows.append(data)
    return rows
