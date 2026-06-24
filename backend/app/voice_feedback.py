from __future__ import annotations

import re
from typing import Any


DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"


def normalize_feedback_text(feedback: list[str] | str | None, max_items: int = 2) -> str:
    if feedback is None:
        return "动作已记录，请保持稳定呼吸。"
    if isinstance(feedback, str):
        items = [feedback]
    else:
        items = [item for item in feedback if item]
    text = "；".join(items[:max_items]).strip()
    if not text:
        text = "动作已记录，请保持稳定呼吸。"
    text = re.sub(r"\s+", " ", text)
    return text[:180]


def _priority_from_status(status: str | None, score: int | None) -> str:
    if status == "error" or (score is not None and score < 45):
        return "high"
    if status == "warning" or (score is not None and score < 80):
        return "medium"
    return "low"


def build_voice_cue(
    feedback: list[str] | str | None,
    status: str | None = None,
    score: int | None = None,
    enabled: bool = True,
    voice: str = DEFAULT_VOICE,
) -> dict[str, Any]:
    text = normalize_feedback_text(feedback)
    priority = _priority_from_status(status, score)
    if not enabled:
        return {
            "enabled": False,
            "text": text,
            "ssml": None,
            "priority": priority,
            "voice": voice,
            "rate": 1.0,
        }

    rate = 0.92 if priority == "high" else 1.0
    escaped = (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
    ssml = (
        f'<speak version="1.0" xml:lang="zh-CN">'
        f'<voice name="{voice}"><prosody rate="{int(rate * 100)}%">{escaped}</prosody></voice>'
        "</speak>"
    )
    return {
        "enabled": True,
        "text": text,
        "ssml": ssml,
        "priority": priority,
        "voice": voice,
        "rate": rate,
    }

