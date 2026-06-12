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


def load_action_library() -> List[ActionItem]:
    actions_file = BASE_DIR / 'knowledge' / 'actions.json'
    with open(actions_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return [ActionItem(
        name=item['name'],
        sets=item.get('sets', 1),
        reps=item.get('reps', 1),
        note=item.get('description')
    ) for item in data.get('actions', [])]


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
    deepseek_summary: Optional[str] = None,
) -> str:
    patient_name = name or '患者'
    age_text = str(age) if age is not None else '未知年龄'
    history_text = history or '无'
    action_text = '；'.join(
        f"{action.name}（{action.sets}组×{action.reps}次）" for action in actions
    ) or '暂未推荐具体动作'
    deepseek_text = f"参考DeepSeek检索结果：{deepseek_summary}。\n" if deepseek_summary else ''

    return (
        f"患者：{patient_name}，年龄：{age_text}。主诉：{symptoms}。既往病史：{history_text}。"
        f"推荐康复训练包括：{action_text}。\n"
        f"{deepseek_text}"
        "训练目标：缓解症状、恢复功能、改善姿势，提升日常活动能力。\n"
        "注意事项：训练前充分热身，保持呼吸平稳，避免突然用力。如出现剧烈疼痛或不适立即停止并咨询专业医师。\n"
        "建议根据自身承受能力逐步增加强度，每周进行3-4次训练，并结合功能性恢复练习。"
    )
