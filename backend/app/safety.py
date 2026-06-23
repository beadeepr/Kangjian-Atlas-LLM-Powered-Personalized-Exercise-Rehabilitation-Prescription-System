from __future__ import annotations

from typing import Iterable

from .schema import ActionItem


SAFETY_WARNING = (
    "本处方仅用于居家康复训练建议，不能替代医生诊断。训练中如出现疼痛明显加重、"
    "麻木无力、头晕、发热或其他异常，应立即停止并就医。"
)


_CONTRAINDICATION_KEYWORDS = {
    "acute_injury": {
        "triggers": ("急性", "刚受伤", "刚扭伤", "48小时", "明显肿胀", "肿胀明显"),
        "reason": "存在急性损伤或明显肿胀描述，需避免可能增加负荷的训练动作。",
    },
    "fracture_or_instability": {
        "triggers": ("骨折", "不稳定", "未固定", "脱位", "压缩骨折"),
        "reason": "存在骨折、脱位或关节不稳定风险，应由医生评估后再训练。",
    },
    "dizziness": {
        "triggers": ("头晕", "眩晕", "恶心"),
        "reason": "存在头晕或眩晕描述，需避免诱发症状的颈部或体位变化动作。",
    },
    "post_op_early": {
        "triggers": ("术后早期", "刚手术", "术后未评估", "医生限制"),
        "reason": "存在术后早期或医生限制描述，需要按医嘱调整训练。",
    },
    "severe_arthritis": {
        "triggers": ("严重关节炎", "关节红肿", "红肿热痛"),
        "reason": "存在明显炎症或严重关节问题，需降低或暂停关节负荷训练。",
    },
}


def _text_contains_any(text: str, keywords: Iterable[str]) -> bool:
    return any(keyword and keyword in text for keyword in keywords)


def _action_payload(action: ActionItem) -> dict:
    if hasattr(action, "model_dump"):
        return action.model_dump()
    return action.dict()


def _match_action_contraindications(action: ActionItem, user_text: str) -> list[str]:
    contraindications = action.contraindications or ""
    reasons = []
    for rule in _CONTRAINDICATION_KEYWORDS.values():
        if _text_contains_any(user_text, rule["triggers"]) and _text_contains_any(
            contraindications,
            rule["triggers"],
        ):
            reasons.append(rule["reason"])
    return reasons


def evaluate_prescription_safety(
    actions: list[ActionItem],
    symptoms: str,
    history: str | None = None,
    mobility_score: int | None = None,
) -> tuple[list[ActionItem], dict]:
    user_text = f"{symptoms or ''} {history or ''}"
    safe_actions = []
    filtered_actions = []
    warnings = [SAFETY_WARNING]

    for action in actions:
        reasons = _match_action_contraindications(action, user_text)
        if reasons:
            filtered_actions.append({
                "id": action.id,
                "name": action.name,
                "reasons": reasons,
                "contraindications": action.contraindications,
            })
            continue
        safe_actions.append(action)

    adjusted_actions = []
    for action in safe_actions:
        payload = _action_payload(action)
        if mobility_score is not None and mobility_score <= 3:
            payload["sets"] = max(1, min(payload.get("sets") or 1, 2))
            payload["reps"] = max(1, min(payload.get("reps") or 1, 8))
            payload["note"] = (
                (payload.get("note") or payload.get("description") or "")
                + " 已根据较低活动度评分自动降阶。"
            ).strip()
        adjusted_actions.append(ActionItem(**payload))

    if mobility_score is not None and mobility_score <= 3:
        warnings.append("活动度评分较低，系统已自动降低训练组数或次数，建议从无痛范围开始。")
    if filtered_actions:
        warnings.append("部分动作因禁忌风险已从处方候选中移除。")
    if not adjusted_actions:
        warnings.append("所有候选动作均存在潜在禁忌，建议暂不生成训练动作并咨询专业人员。")

    risk_level = "medium" if filtered_actions else "low"
    if not adjusted_actions:
        risk_level = "high"

    safety = {
        "risk_level": risk_level,
        "warnings": warnings,
        "filtered_actions": filtered_actions,
        "actions_before_filter": len(actions),
        "actions_after_filter": len(adjusted_actions),
    }
    return adjusted_actions, safety
