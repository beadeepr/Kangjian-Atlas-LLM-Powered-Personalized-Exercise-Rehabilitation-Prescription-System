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
    "用户活动度评分: {mobility_score}\n"
    "知识库候选动作: {actions}\n"
    "请输出 JSON，包含 summary、actions、warnings、follow_up。"
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


def save_action_catalog(actions: List[dict]) -> None:
    actions_file = BASE_DIR / "knowledge" / "actions.json"
    payload = {"actions": actions}
    actions_file.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def get_action_payload(action_id: str) -> Optional[dict]:
    for action in load_action_catalog():
        if action.get("id") == action_id:
            return action
    return None


def create_action_payload(action: dict) -> dict:
    actions = load_action_catalog()
    if any(item.get("id") == action.get("id") for item in actions):
        raise ValueError("action id already exists")
    actions.append(action)
    save_action_catalog(actions)
    return action


def update_action_payload(action_id: str, updates: dict) -> Optional[dict]:
    actions = load_action_catalog()
    for index, action in enumerate(actions):
        if action.get("id") != action_id:
            continue
        next_action = {**action, **updates}
        next_id = next_action.get("id")
        if next_id != action_id and any(item.get("id") == next_id for item in actions):
            raise ValueError("action id already exists")
        actions[index] = next_action
        save_action_catalog(actions)
        return next_action
    return None


def delete_action_payload(action_id: str) -> bool:
    actions = load_action_catalog()
    next_actions = [action for action in actions if action.get("id") != action_id]
    if len(next_actions) == len(actions):
        return False
    save_action_catalog(next_actions)
    return True


def load_action_library() -> List[ActionItem]:
    actions_file = BASE_DIR / 'knowledge' / 'actions.json'
    with open(actions_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return [ActionItem(
        id=item.get('id'),
        name=item['name'],
        sets=item.get('sets', 1),
        reps=item.get('reps', 1),
        note=item.get('note') or item.get('description'),
        description=item.get('description'),
        frequency=item.get('frequency'),
        contraindications=item.get('contraindications'),
        progression=item.get('progression'),
        regression=item.get('regression'),
        body_regions=item.get('body_regions', []),
        target_conditions=item.get('target_conditions', []),
    ) for item in data.get('actions', [])]


def _score_action(
    action: ActionItem,
    symptoms: str,
    pain_regions: Optional[List[str]],
    history: Optional[str],
) -> int:
    text = f"{symptoms} {history or ''}".lower()
    score = 0

    for region in pain_regions or []:
        if region in (action.body_regions or []):
            score += 4
        for hint in REGION_HINTS.get(region, []):
            if hint.lower() in text:
                score += 1

    for condition in action.target_conditions or []:
        if condition.lower() in text:
            score += 3

    for region, hints in REGION_HINTS.items():
        if region in (action.body_regions or []) and any(hint.lower() in text for hint in hints):
            score += 2

    if (action.reps or 0) > 0:
        score += 1

    return score


def select_actions_for_prescription(
    symptoms: str,
    pain_regions: Optional[List[str]] = None,
    history: Optional[str] = None,
    mobility_score: Optional[int] = None,
    min_actions: int = 2,
    max_actions: int = 4,
) -> List[ActionItem]:
    actions = load_action_library()
    scored = [(_score_action(action, symptoms, pain_regions, history), action) for action in actions]
    scored.sort(key=lambda pair: pair[0], reverse=True)

    selected = [action for score, action in scored if score > 0][:max_actions]

    if len(selected) < min_actions:
        fallback_ids = []
        region_defaults = {
            "颈部": ["neck_chin_tuck", "neck_side_bend"],
            "肩部": ["scapular_retraction", "thoracic_extension"],
            "腰部": ["pelvic_tilt", "bird_dog", "glute_bridge"],
            "膝关节": ["wall_squat", "straight_leg_raise", "quad_set"],
            "踝关节": ["calf_stretch", "ankle_pump"],
        }
        for region in pain_regions or []:
            fallback_ids.extend(region_defaults.get(region, []))

        if not fallback_ids:
            fallback_ids = ["neck_side_bend", "pelvic_tilt", "wall_squat"]

        library_by_id = {action.id: action for action in actions}
        for action_id in fallback_ids:
            if len(selected) >= min_actions:
                break
            candidate = library_by_id.get(action_id)
            if candidate and all(item.id != candidate.id for item in selected):
                selected.append(candidate)

    if mobility_score is not None and mobility_score <= 4:
        adjusted = []
        for action in selected:
            payload = action.model_dump() if hasattr(action, "model_dump") else action.dict()
            payload["sets"] = max(2, (action.sets or 3) - 1)
            payload["reps"] = max(1, action.reps or 1)
            adjusted.append(ActionItem(**payload))
        return adjusted[:max_actions]

    return selected[:max_actions]


def select_actions_for_request(
    symptoms: str,
    pain_regions: Optional[List[str]] = None,
    limit: int = 4,
) -> List[ActionItem]:
    actions = load_action_library()
    symptom_text = (symptoms or "").lower()
    requested_regions = set(pain_regions or [])

    region_keywords = {
        "颈部": ["颈", "脖", "落枕"],
        "肩部": ["肩"],
        "腰部": ["腰", "腰突", "腰椎", "坐骨"],
        "膝关节": ["膝"],
        "踝关节": ["踝", "脚踝"],
    }
    for region, keywords in region_keywords.items():
        if any(keyword in symptom_text for keyword in keywords):
            requested_regions.add(region)

    condition_keywords = {
        "颈椎病": ["颈椎", "颈部", "脖"],
        "腰椎间盘突出": ["腰突", "腰椎间盘", "坐骨"],
        "腰痛": ["腰痛", "腰肌"],
        "膝关节疼痛": ["膝"],
        "肩颈疼痛": ["肩颈", "肩部"],
    }

    scored = []
    for action in actions:
        score = 0
        if requested_regions and set(action.body_regions or []) & requested_regions:
            score += 4
        for condition, keywords in condition_keywords.items():
            if condition in (action.target_conditions or []) and any(keyword in symptom_text for keyword in keywords):
                score += 3
        if action.reps > 0:
            score += 1
        scored.append((score, action))

    selected = [action for score, action in sorted(scored, key=lambda item: item[0], reverse=True) if score > 0]
    if not selected:
        selected = actions[:limit]
    return selected[:limit]


def load_prompt_template() -> str:
    template_file = BASE_DIR / "knowledge" / "prompt_template.txt"
    if not template_file.exists():
        return DEFAULT_PROMPT_TEMPLATE
    text = template_file.read_text(encoding="utf-8").strip()
    return text or DEFAULT_PROMPT_TEMPLATE


def render_prescription_summary(
    name: Optional[str],
    age: Optional[int],
    symptoms: str,
    history: Optional[str],
    actions: List[ActionItem],
    mobility_score: Optional[int] = None,
    model_summary: Optional[str] = None,
) -> str:
    patient_name = name or '患者'
    age_text = str(age) if age is not None else '未知年龄'
    history_text = history or '无'
    action_text = '；'.join(
        f"{action.name}（{action.sets}组×{action.reps}次）" for action in actions
    ) or '暂未推荐具体动作'
    mobility_text = str(mobility_score) if mobility_score is not None else '未提供'
    model_text = f"大模型建议摘要：{model_summary}\n" if model_summary else ''

    return (
        f"患者：{patient_name}，年龄：{age_text}。主诉：{symptoms}。既往病史：{history_text}。"
        f"活动度评分：{mobility_text}。推荐康复训练包括：{action_text}。\n"
        f"{model_text}"
        "训练目标：缓解症状、恢复功能、改善姿势，提升日常活动能力。\n"
        "注意事项：训练前充分热身，保持呼吸平稳，避免突然用力。如出现剧烈疼痛或不适立即停止并咨询专业医师。\n"
        "建议根据自身承受能力逐步增加强度，每周进行3-4次训练，并结合功能性恢复练习。"
    )
