from __future__ import annotations

from typing import Any

from .schema import ActionItem


DEFAULT_DIFFICULTY_LEVELS = ["初级", "中级", "高级"]


def action_to_dict(action: ActionItem) -> dict[str, Any]:
    if hasattr(action, "model_dump"):
        return action.model_dump()
    return action.dict()


def build_error_comparisons(action: ActionItem) -> list[dict[str, str]]:
    mistakes = action.common_mistakes or []
    cues = action.correct_cues or []
    comparisons = []
    for index, mistake in enumerate(mistakes):
        comparisons.append({
            "mistake": mistake,
            "correct": cues[index] if index < len(cues) else "回到无痛范围，按示范缓慢完成动作。",
            "risk": "可能降低训练效果或诱发疼痛不适。",
        })
    return comparisons


def build_difficulty_profiles(action: ActionItem) -> list[dict[str, Any]]:
    base_sets = action.sets or 3
    base_reps = action.reps or 10
    recommended = action.difficulty_level or "中级"
    level_offset = {"初级": -1, "中级": 0, "高级": 1}
    rec_offset = level_offset.get(recommended, 0)

    def profile_sets(level: str) -> int:
        offset = level_offset[level] - rec_offset
        return max(1, min(20, base_sets + offset))

    def profile_reps(level: str) -> int:
        offset = level_offset[level] - rec_offset
        return max(1, min(200, base_reps + offset * 2))

    return [
        {
            "level": "初级",
            "sets": profile_sets("初级"),
            "reps": profile_reps("初级"),
            "tempo": "慢速，动作幅度控制在无痛范围内。",
            "guidance": action.regression or "先缩小动作幅度，确认无明显疼痛后再完成标准次数。",
        },
        {
            "level": "中级",
            "sets": profile_sets("中级"),
            "reps": profile_reps("中级"),
            "tempo": "按标准动作节奏完成，注意呼吸和关节对线。",
            "guidance": action.description or action.note or "按标准动作完成训练。",
        },
        {
            "level": "高级",
            "sets": profile_sets("高级"),
            "reps": profile_reps("高级"),
            "tempo": "保持动作质量后再增加保持时间、次数或轻阻力。",
            "guidance": action.progression or "连续训练无疼痛加重后，逐步增加训练量。",
        },
    ]


def enrich_library_detail(action: ActionItem) -> ActionItem:
    payload = action_to_dict(action)
    payload["error_comparisons"] = payload.get("error_comparisons") or build_error_comparisons(action)
    payload["difficulty_profiles"] = payload.get("difficulty_profiles") or build_difficulty_profiles(action)
    if not payload.get("demo_media"):
        payload["demo_media"] = {
            "image": payload.get("image"),
            "video": payload.get("video_url") or "",
            "image_hint": payload.get("image_hint"),
            "video_hint": payload.get("video_hint"),
        }
    return ActionItem(**payload)


def _matches_keyword(action: ActionItem, keyword: str) -> bool:
    data = action_to_dict(action)
    haystack = " ".join(
        str(value)
        for value in [
            data.get("id"),
            data.get("name"),
            data.get("category"),
            data.get("description"),
            data.get("note"),
            data.get("frequency"),
            " ".join(data.get("body_regions") or []),
            " ".join(data.get("target_conditions") or []),
            " ".join(data.get("target_muscles") or []),
        ]
        if value
    ).lower()
    return keyword.lower() in haystack


def list_exercises(
    q: str | None = None,
    body_region: str | None = None,
    condition: str | None = None,
    category: str | None = None,
    difficulty_level: str | None = None,
    risk_level: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[ActionItem]:
    from .knowledge import load_action_library

    actions = [enrich_library_detail(action) for action in load_action_library()]
    if q and q.strip():
        keyword = q.strip()
        actions = [action for action in actions if _matches_keyword(action, keyword)]
    if body_region and body_region.strip():
        region = body_region.strip()
        actions = [action for action in actions if region in (action.body_regions or [])]
    if condition and condition.strip():
        target = condition.strip()
        actions = [action for action in actions if target in (action.target_conditions or [])]
    if category and category.strip():
        target = category.strip()
        actions = [action for action in actions if action.category == target]
    if difficulty_level and difficulty_level.strip():
        target = difficulty_level.strip()
        actions = [action for action in actions if action.difficulty_level == target]
    if risk_level and risk_level.strip():
        target = risk_level.strip()
        actions = [action for action in actions if action.risk_level == target]

    start = max(0, offset)
    size = max(1, min(limit, 200))
    return actions[start:start + size]


def get_exercise_detail(action_id: str) -> ActionItem | None:
    for action in list_exercises(limit=200):
        if action.id == action_id:
            return action
    return None


def build_library_meta() -> dict[str, Any]:
    actions = list_exercises(limit=200)
    return {
        "total": len(actions),
        "body_regions": sorted({item for action in actions for item in (action.body_regions or [])}),
        "target_conditions": sorted({item for action in actions for item in (action.target_conditions or [])}),
        "categories": sorted({action.category for action in actions if action.category}),
        "difficulty_levels": sorted({action.difficulty_level for action in actions if action.difficulty_level}),
        "risk_levels": sorted({action.risk_level for action in actions if action.risk_level}),
        "media_types": ["image", "video"],
    }
