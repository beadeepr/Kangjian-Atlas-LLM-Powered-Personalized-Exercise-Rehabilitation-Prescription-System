from __future__ import annotations

import json
from typing import Any

from .doubao import generate_with_http


DEFAULT_REJECT_REASON = "内容不符合医学检查报告特征，请上传 MRI/X光/CT 报告或粘贴诊断结论。"
RISK_LEVELS = {"low", "medium", "high", "unknown"}


class ImagingAnalysisError(Exception):
    pass


def analyze_imaging_report(text: str, report_type: str | None = None) -> dict[str, Any]:
    cleaned_text = (text or "").strip()
    if not cleaned_text:
        raise ImagingAnalysisError("empty report text")

    prompt = _build_prompt(cleaned_text, report_type)
    result = generate_with_http(prompt, timeout=28)
    data = result.get("json")
    if not isinstance(data, dict):
        raise ImagingAnalysisError("LLM did not return a JSON object")
    return normalize_imaging_analysis(data)


def normalize_imaging_analysis(data: dict[str, Any]) -> dict[str, Any]:
    is_medical_report = bool(data.get("is_medical_report"))
    risk_level = str(data.get("risk_level") or "unknown").lower()
    if risk_level not in RISK_LEVELS:
        risk_level = "unknown"

    red_flags = data.get("red_flags") or []
    if not isinstance(red_flags, list):
        red_flags = []

    summary = data.get("summary")
    if summary is not None:
        summary = str(summary).strip() or None

    reject_reason = data.get("reject_reason")
    if reject_reason is not None:
        reject_reason = str(reject_reason).strip() or None
    if not is_medical_report and not reject_reason:
        reject_reason = DEFAULT_REJECT_REASON

    confidence = data.get("confidence")
    try:
        confidence = float(confidence) if confidence is not None else None
    except (TypeError, ValueError):
        confidence = None
    if confidence is not None:
        confidence = max(0.0, min(1.0, confidence))

    return {
        "is_medical_report": is_medical_report,
        "summary": summary,
        "red_flags": _normalize_red_flags(red_flags),
        "risk_level": risk_level,
        "reject_reason": reject_reason,
        "confidence": confidence,
    }


def _normalize_red_flags(red_flags: list[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in red_flags:
        if not isinstance(item, dict):
            continue
        code = str(item.get("code") or "").strip()
        label = str(item.get("label") or "").strip()
        if not code or not label:
            continue
        normalized_item: dict[str, Any] = {"code": code, "label": label}
        evidence = item.get("evidence")
        if evidence:
            normalized_item["evidence"] = str(evidence).strip()
        matched = item.get("matched")
        if isinstance(matched, list):
            normalized_item["matched"] = matched
        normalized.append(normalized_item)
    return normalized


def _build_prompt(text: str, report_type: str | None) -> str:
    report_type_text = report_type or "未指定"
    sample = {
        "is_medical_report": True,
        "summary": "MRI 提示 L4-L5 椎间盘膨出，建议结合临床评估。",
        "red_flags": [
            {
                "code": "numbness_or_weakness",
                "label": "下肢麻木或无力",
                "evidence": "原文片段",
            }
        ],
        "risk_level": "high",
        "reject_reason": None,
        "confidence": 0.92,
    }
    return (
        "请判断下面内容是否为医学影像/检查报告，并提取康复安全相关信息。\n"
        "必须只输出 JSON，不要输出 Markdown、解释或额外文本。\n"
        "字段固定为：is_medical_report, summary, red_flags, risk_level, reject_reason, confidence。\n"
        "risk_level 只能是 low、medium、high、unknown。\n"
        "如果不是医学报告，is_medical_report=false，summary=null，red_flags=[]，risk_level=unknown，"
        f"reject_reason 使用可读中文原因，默认可用：{DEFAULT_REJECT_REASON}\n"
        "红旗重点包括：下肢麻木或无力、大小便异常、马尾综合征、骨折/肿瘤/感染提示、严重神经压迫等。\n"
        f"报告类型：{report_type_text}\n"
        f"输出示例：{json.dumps(sample, ensure_ascii=False)}\n"
        "待分析内容：\n"
        f"{text[:12000]}"
    )
