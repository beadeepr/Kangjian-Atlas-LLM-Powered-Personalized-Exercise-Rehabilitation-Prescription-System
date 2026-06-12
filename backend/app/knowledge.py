import json
from pathlib import Path
from typing import List, Optional
from .schema import ActionItem

BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_PROMPT_TEMPLATE = (
    "请根据以下信息撰写一个安全、渐进的家庭康复训练摘要。\n"
    "姓名: {name}\n"
    "年龄: {age}\n"
    "主诉: {symptoms}\n"
    "既往病史: {history}\n"
    "推荐动作: {actions}\n"
    "请输出一段中文康复处方摘要，包含训练目标、注意事项和循序渐进的建议。"
)

REGION_HINTS = {
    "颈部": ["颈", "颈椎", "脖子", "转头", "落枕", "低头"],
    "肩部": ["肩", "肩胛", "圆肩", "抬手", "冻结"],
    "腰部": ["腰", "腰椎", "久坐", "弯腰", "突出", "劳损"],
    "膝关节": ["膝", "髌骨", "蹲", "下楼", "跑步"],
    "踝关节": ["踝", "脚跟", "小腿", "跟腱", "肿胀"],
}


def load_action_catalog() -> List[dict]:
    actions_file = BASE_DIR / "knowledge" / "actions.json"
    with open(actions_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("actions", [])


def load_action_library() -> List[ActionItem]:
    return [
        ActionItem(
            name=item["name"],
            sets=item.get("sets", 1),
            reps=item.get("reps", 1),
            note=item.get("description"),
        )
        for item in load_action_catalog()
    ]


def _score_action(
    action: dict,
    symptoms: str,
    pain_regions: Optional[List[str]],
    history: Optional[str],
) -> int:
    text = f"{symptoms} {history or ''}"
    score = 0

    for region in pain_regions or []:
        if region in action.get("target_regions", []):
            score += 4
        for hint in REGION_HINTS.get(region, []):
            if hint in text:
                score += 1

    for keyword in action.get("keywords", []):
        if keyword in text:
            score += 3

    return score


def select_actions_for_prescription(
    symptoms: str,
    pain_regions: Optional[List[str]] = None,
    history: Optional[str] = None,
    mobility_score: Optional[int] = None,
    min_actions: int = 2,
    max_actions: int = 4,
) -> List[ActionItem]:
    catalog = load_action_catalog()
    scored = [
        (_score_action(item, symptoms, pain_regions, history), item)
        for item in catalog
    ]
    scored.sort(key=lambda pair: pair[0], reverse=True)

    positive = [item for score, item in scored if score > 0]
    selected = positive[:max_actions]

    if len(selected) < min_actions:
        fallback_ids = []
        region_defaults = {
            "颈部": ["neck_side_bend", "chin_tuck"],
            "肩部": ["shoulder_roll", "neck_side_bend"],
            "腰部": ["cat_cow", "pelvic_tilt"],
            "膝关节": ["wall_squat", "calf_stretch"],
            "踝关节": ["ankle_pump", "calf_stretch"],
        }
        for region in pain_regions or []:
            fallback_ids.extend(region_defaults.get(region, []))

        if not fallback_ids:
            fallback_ids = ["neck_side_bend", "cat_cow", "wall_squat"]

        id_to_action = {item["id"]: item for item in catalog}
        for action_id in fallback_ids:
            if len(selected) >= min_actions:
                break
            candidate = id_to_action.get(action_id)
            if candidate and candidate not in selected:
                selected.append(candidate)

    if mobility_score is not None and mobility_score <= 4 and selected:
        for item in selected:
            item["sets"] = max(2, int(item.get("sets", 3)) - 1)
            item["reps"] = max(1, int(item.get("reps", 1)))

    return [
        ActionItem(
            name=item["name"],
            sets=item.get("sets", 1),
            reps=item.get("reps", 1),
            note=item.get("description"),
        )
        for item in selected[:max_actions]
    ]


def load_prompt_template() -> str:
    template_file = BASE_DIR / "knowledge" / "prompt_template.txt"
    if not template_file.exists():
        return DEFAULT_PROMPT_TEMPLATE
    text = template_file.read_text(encoding="utf-8").strip()
    return text or DEFAULT_PROMPT_TEMPLATE
