"""Shared HTTP helpers for free data vendors."""

from __future__ import annotations

from typing import Any

import httpx

YAHOO_UA = "Mozilla/5.0 (compatible; AureliaInvestments/1.0)"


def sec_headers(user_agent: str) -> dict[str, str]:
    return {
        "User-Agent": user_agent,
        "Accept-Encoding": "gzip, deflate",
        "Host": "www.sec.gov",
    }


def sec_data_headers(user_agent: str) -> dict[str, str]:
    return {
        "User-Agent": user_agent,
        "Accept-Encoding": "gzip, deflate",
        "Host": "data.sec.gov",
    }


async def get_json(
    url: str,
    headers: dict[str, str],
    params: dict[str, Any] | None = None,
    timeout: float = 20.0,
) -> Any | None:
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
    except Exception:  # noqa: BLE001
        return None


async def get_text(
    url: str,
    headers: dict[str, str],
    params: dict[str, Any] | None = None,
    timeout: float = 30.0,
) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.text
    except Exception:  # noqa: BLE001
        return None
