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
    template_file = BASE_DIR / 'knowledge' / 'prompt_template.txt'
    if not template_file.exists():
        return DEFAULT_PROMPT_TEMPLATE
    text = template_file.read_text(encoding='utf-8').strip()
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
