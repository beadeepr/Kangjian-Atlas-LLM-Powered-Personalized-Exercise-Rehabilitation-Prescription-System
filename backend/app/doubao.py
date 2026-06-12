import json
import os
import re
from pathlib import Path
from typing import Any, Optional

import requests
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR / "backend" / ".env")

DOUBAO_API_KEY = os.getenv("DOUBAO_API_KEY")
DOUBAO_BASE_URL = os.getenv("DOUBAO_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
DOUBAO_MODEL_ID = os.getenv("DOUBAO_MODEL_ID")


class DoubaoError(Exception):
    pass


def _headers() -> dict[str, str]:
    if not DOUBAO_API_KEY:
        raise DoubaoError("Missing DOUBAO_API_KEY environment variable")
    return {
        "Authorization": f"Bearer {DOUBAO_API_KEY}",
        "Content-Type": "application/json",
    }


def _sanitize_payload(payload: Any) -> Any:
    if isinstance(payload, dict):
        sanitized = {}
        for key, value in payload.items():
            key_lower = key.lower()
            if key_lower in {"authorization", "api_key", "apikey", "secret", "token", "signature"}:
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, (dict, list)):
                sanitized[key] = _sanitize_payload(value)
            else:
                sanitized[key] = value
        return sanitized
    if isinstance(payload, list):
        return [_sanitize_payload(item) for item in payload]
    return payload


def _extract_chat_text(data: dict[str, Any]) -> str:
    choices = data.get("choices") or []
    if choices:
        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, str):
            return content
    for key in ("output", "result", "response", "data"):
        value = data.get(key)
        if isinstance(value, str):
            return value
        if value is not None:
            return json.dumps(value, ensure_ascii=False)
    return json.dumps(data, ensure_ascii=False)


def _extract_json_object(text: str) -> Optional[dict[str, Any]]:
    if not text:
        return None
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", cleaned, flags=re.S)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


def generate_with_http(prompt: str, model_id: Optional[str] = None, timeout: int = 30) -> dict[str, Any]:
    model = model_id or DOUBAO_MODEL_ID
    if not model:
        raise DoubaoError("Missing DOUBAO_MODEL_ID (or model_id argument)")

    url = f"{DOUBAO_BASE_URL.rstrip('/')}/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "你是谨慎的中文运动康复处方助手，必须优先保证安全并按要求输出。",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }

    try:
        resp = requests.post(url, headers=_headers(), json=payload, timeout=timeout)
        resp.raise_for_status()
    except requests.RequestException as exc:
        detail = getattr(exc.response, "text", str(exc))
        raise DoubaoError(f"HTTP error from Doubao: {detail}") from exc

    resp.encoding = "utf-8"
    try:
        data = resp.json()
    except ValueError as exc:
        raise DoubaoError("Doubao returned non-JSON response") from exc

    text = _extract_chat_text(data)
    return {
        "text": text,
        "json": _extract_json_object(text),
        "raw": _sanitize_payload(data),
    }


def generate_summary(prompt: str, model_id: Optional[str] = None) -> dict[str, Any]:
    return generate_with_http(prompt, model_id=model_id)


def generate_prescription_summary(
    patient_name: str,
    age: Optional[int],
    symptoms: str,
    history: Optional[str],
    actions: list[dict[str, Any]],
    pain_regions: Optional[list[str]] = None,
    mobility_score: Optional[int] = None,
    prompt_template: Optional[str] = None,
) -> dict[str, Any]:
    from .knowledge import DEFAULT_PROMPT_TEMPLATE

    template = prompt_template or DEFAULT_PROMPT_TEMPLATE
    prompt = template.format(
        name=patient_name or "患者",
        age=str(age) if age is not None else "未知年龄",
        symptoms=symptoms,
        history=history or "无",
        pain_regions="、".join(pain_regions or []) or "未提供",
        mobility_score=str(mobility_score) if mobility_score is not None else "未提供",
        actions=json.dumps(actions, ensure_ascii=False, indent=2),
    )

    try:
        return generate_summary(prompt)
    except Exception:
        return {
            "text": _fallback_summary(patient_name, age, symptoms, history, actions, mobility_score),
            "json": None,
            "raw": None,
        }


def _fallback_summary(
    patient_name: str,
    age: Optional[int],
    symptoms: str,
    history: Optional[str],
    actions: list[dict[str, Any]],
    mobility_score: Optional[int] = None,
) -> str:
    patient_name = patient_name or "患者"
    age_text = str(age) if age is not None else "未知年龄"
    history_text = history or "无"
    mobility_text = str(mobility_score) if mobility_score is not None else "未提供"
    action_text = (
        "；".join(
            f"{action.get('name')}（{action.get('sets', 1)}组×{action.get('reps', 1)}次，{action.get('frequency', '按耐受频次')}）"
            for action in actions
        )
        if actions
        else "暂未推荐具体动作"
    )

    return (
        f"患者：{patient_name}，年龄：{age_text}。主诉：{symptoms}。既往病史：{history_text}。"
        f"活动度评分：{mobility_text}。推荐康复训练包括：{action_text}。\n"
        "训练目标：缓解症状、恢复功能、改善姿势与核心稳定，提升日常活动能力。\n"
        "注意事项：训练前热身，动作全程保持可耐受；若出现剧烈疼痛、麻木无力、头晕或症状加重，应立即停止并咨询医生。\n"
        "进阶建议：连续3天训练后无疼痛加重，再逐步增加保持时间、次数或轻阻力。"
    )
