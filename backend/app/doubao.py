import os
from typing import Optional
from openai import OpenAI

API_KEY = os.getenv("DOUBAO_API_KEY")
BASE_URL = os.getenv("DOUBAO_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
MODEL_ID = os.getenv("DOUBAO_MODEL_ID", "ep-20250101000000-xxxxx")


class DoubaoError(Exception):
    pass


def _get_client() -> OpenAI:
    if not API_KEY:
        raise DoubaoError("Missing DOUBAO_API_KEY environment variable")
    return OpenAI(api_key=API_KEY, base_url=BASE_URL)


def generate_prescription_summary(
    patient_name: str,
    age: Optional[int],
    symptoms: str,
    history: Optional[str],
    actions: list[str],
) -> str:
    """Generate prescription summary using Doubao LLM."""
    try:
        client = _get_client()
    except DoubaoError:
        return _fallback_summary(patient_name, age, symptoms, history, actions)

    action_text = "；".join(actions) if actions else "暂未推荐具体动作"
    age_text = str(age) if age is not None else "未知年龄"
    history_text = history or "无"

    prompt = (
        f"请根据以下信息撰写一个安全、渐进的家庭康复训练摘要。\n"
        f"患者姓名: {patient_name}\n"
        f"年龄: {age_text}\n"
        f"主诉: {symptoms}\n"
        f"既往病史: {history_text}\n"
        f"推荐动作: {action_text}\n"
        f"\n"
        f"请输出一段中文康复处方摘要，包含训练目标、注意事项和循序渐进的建议。"
    )

    try:
        response = client.chat.completions.create(
            model=MODEL_ID,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=500,
        )
        return response.choices[0].message.content or _fallback_summary(
            patient_name, age, symptoms, history, actions
        )
    except Exception as exc:
        raise DoubaoError(f"Doubao API call failed: {str(exc)}") from exc


def _fallback_summary(
    patient_name: str,
    age: Optional[int],
    symptoms: str,
    history: Optional[str],
    actions: list[str],
) -> str:
    """Fallback summary when Doubao API is unavailable."""
    patient_name = patient_name or "患者"
    age_text = str(age) if age is not None else "未知年龄"
    history_text = history or "无"
    action_text = (
        "；".join(f"{action}（3组×1次）" for action in actions)
        if actions
        else "暂未推荐具体动作"
    )

    return (
        f"患者：{patient_name}，年龄：{age_text}。主诉：{symptoms}。既往病史：{history_text}。"
        f"推荐康复训练包括：{action_text}。\n"
        "训练目标：缓解症状、恢复功能、改善姿势，提升日常活动能力。\n"
        "注意事项：训练前充分热身，保持呼吸平稳，避免突然用力。如出现剧烈疼痛或不适立即停止并咨询专业医师。\n"
        "建议根据自身承受能力逐步增加强度，每周进行3-4次训练，并结合功能性恢复练习。"
    )
