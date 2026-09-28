"""Code-only change detection for a saved brief. No model calls."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ALLOWED_METRICS = {
    "price",
    "gross_margin",
    "operating_margin",
    "net_margin",
    "fcf_yield",
    "pe",
    "revenue_cagr_5y",
}
OPERATORS = {"<", "<=", ">", ">="}
_RATIO_METRICS = {"gross_margin", "operating_margin", "net_margin", "fcf_yield", "revenue_cagr_5y"}


def normalize_conditions(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    cleaned = []
    for item in raw[:8]:
        if not isinstance(item, dict):
            continue
        metric = str(item.get("metric") or "").strip()
        operator = str(item.get("operator") or "").strip()
        if metric not in ALLOWED_METRICS or operator not in OPERATORS:
            continue
        try:
            threshold = float(item.get("threshold"))
        except (TypeError, ValueError):
            continue
        label = str(item.get("label") or f"{metric} {operator} {threshold}").strip()[:160]
        cleaned.append(
            {"metric": metric, "operator": operator, "threshold": threshold, "label": label}
        )
    return cleaned


def _scale(metric: str, threshold: float) -> float:
    if metric in _RATIO_METRICS and abs(threshold) > 1.5:
        return threshold / 100
    return threshold


def _compare(left: float, operator: str, right: float) -> bool:
    if operator == "<":
        return left < right
    if operator == "<=":
        return left <= right
    if operator == ">":
        return left > right
    return left >= right


def metric_values(report: dict[str, Any], price: float | None) -> dict[str, float]:
    sheet = report.get("fact_sheet") or {}
    business = sheet.get("business") or {}
    valuation = sheet.get("valuation") or {}
    values: dict[str, float] = {}
    if price is not None:
        values["price"] = float(price)
    for key in ("gross_margin", "operating_margin", "net_margin", "revenue_cagr_5y"):
        if business.get(key) is not None:
            values[key] = float(business[key])
    for key in ("pe", "fcf_yield"):
        if valuation.get(key) is not None:
            values[key] = float(valuation[key])
    return values


def evaluate_conditions(conditions: list[dict[str, Any]], values: dict[str, float]) -> list[dict[str, Any]]:
    tripped = []
    for condition in conditions:
        metric = condition["metric"]
        if metric not in values:
            continue
        threshold = _scale(metric, float(condition["threshold"]))
        if _compare(values[metric], condition["operator"], threshold):
            tripped.append({**condition, "actual": values[metric]})
    return tripped


def banner_text(
    age_days: int | None,
    price_change: float | None,
    new_filing: dict[str, Any] | None,
    tripped: list[dict[str, Any]],
) -> str:
    material = bool(tripped) or new_filing is not None or (price_change is not None and abs(price_change) >= 0.05)
    if not material:
        return ""
    bits = []
    if age_days is not None:
        bits.append(f"{age_days} days old")
    if price_change is not None:
        bits.append(f"since then price {price_change * 100:+.0f}%")
    if new_filing:
        bits.append(f"new {new_filing.get('form') or 'filing'} {new_filing.get('filed') or ''}".strip())
    for condition in tripped:
        bits.append(f"'{condition.get('label')}' now TRUE")
    return "; ".join(bits) + ". Re-run?"


def age_days(generated_at: str | None, today: datetime | None = None) -> int | None:
    if not generated_at:
        return None
    try:
        opened = datetime.fromisoformat(str(generated_at).replace("Z", "+00:00"))
    except ValueError:
        return None
    if opened.tzinfo is None:
        opened = opened.replace(tzinfo=timezone.utc)
    now = today or datetime.now(timezone.utc)
    return max(0, (now - opened).days)


def _path(output_dir: str, name: str) -> Path:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root / name


def load_watchlist(output_dir: str) -> list[dict[str, Any]]:
    path = _path(output_dir, "watchlist.json")
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    items = data.get("items") if isinstance(data, dict) else None
    return [item for item in (items or []) if isinstance(item, dict) and item.get("ticker")]


def save_watchlist(output_dir: str, items: list[dict[str, Any]]) -> None:
    _path(output_dir, "watchlist.json").write_text(
        json.dumps({"items": items}, indent=2),
        encoding="utf-8",
    )


def add_watch(output_dir: str, ticker: str, report_id: str) -> list[dict[str, Any]]:
    symbol = (ticker or "").strip().upper()
    items = [item for item in load_watchlist(output_dir) if str(item.get("ticker")).upper() != symbol]
    items.append(
        {
            "ticker": symbol,
            "report_id": report_id,
            "added_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    save_watchlist(output_dir, items)
    return items


def remove_watch(output_dir: str, ticker: str) -> list[dict[str, Any]]:
    symbol = (ticker or "").strip().upper()
    items = [item for item in load_watchlist(output_dir) if str(item.get("ticker")).upper() != symbol]
    save_watchlist(output_dir, items)
    return items


def load_alerts(output_dir: str) -> list[dict[str, Any]]:
    path = _path(output_dir, "alerts.json")
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    items = data.get("items") if isinstance(data, dict) else None
    return [item for item in (items or []) if isinstance(item, dict)]


def save_alerts(output_dir: str, items: list[dict[str, Any]]) -> None:
    _path(output_dir, "alerts.json").write_text(
        json.dumps({"items": items[-100:]}, indent=2),
        encoding="utf-8",
    )


def push_alert(output_dir: str, ticker: str, report_id: str, message: str) -> dict[str, Any] | None:
    if not message:
        return None
    items = load_alerts(output_dir)
    for item in items:
        if item.get("report_id") == report_id and item.get("message") == message and not item.get("seen"):
            return None
    alert = {
        "id": datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S") + ticker,
        "ticker": ticker,
        "report_id": report_id,
        "message": message,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "seen": False,
    }
    items.append(alert)
    save_alerts(output_dir, items)
    return alert


def mark_alerts_seen(output_dir: str) -> None:
    items = load_alerts(output_dir)
    for item in items:
        item["seen"] = True
    save_alerts(output_dir, items)
