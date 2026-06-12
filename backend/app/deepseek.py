import os
import requests
from typing import Any

BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.ai")
SEARCH_PATH = os.getenv("DEEPSEEK_SEARCH_PATH", "/v1/search")
API_KEY = os.getenv("DEEPSEEK_API_KEY")


class DeepSeekError(Exception):
    pass


def _headers() -> dict[str, str]:
    if not API_KEY:
        raise DeepSeekError("Missing DEEPSEEK_API_KEY environment variable")
    return {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }


def _build_url() -> str:
    return BASE_URL.rstrip("/") + "/" + SEARCH_PATH.lstrip("/")


def search_deepseek(query: str, top_k: int = 3) -> dict[str, Any]:
    if not query:
        raise ValueError("query is required")

    url = _build_url()
    payload = {"query": query, "top_k": top_k}
    response = requests.post(url, json=payload, headers=_headers(), timeout=15)
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise DeepSeekError(
            f"DeepSeek request failed ({response.status_code}): {response.text}"
        ) from exc

    return response.json()


def extract_titles(result: dict[str, Any]) -> list[str]:
    if not isinstance(result, dict):
        return []

    items = result.get("results") or result.get("items") or result.get("hits") or []
    if not isinstance(items, list):
        return []

    titles: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title = item.get("title") or item.get("name") or item.get("snippet")
        if isinstance(title, str) and title.strip():
            titles.append(title.strip())
    return titles
