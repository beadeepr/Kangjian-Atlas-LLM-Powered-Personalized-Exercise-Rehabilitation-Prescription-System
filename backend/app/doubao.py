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
    pain_regions: Optional[list[str]] = None,
    mobility_score: Optional[int] = None,
) -> str:
    """Generate prescription summary using Doubao LLM."""
    try:
        client = _get_client()
    except DoubaoError:
        return _fallback_summary(patient_name, age, symptoms, history, actions)

    action_text = "；".join(actions) if actions else "暂未推荐具体动作"
    age_text = str(age) if age is not None else "未知年龄"
    history_text = history or "无"

    pain_text = "、".join(pain_regions) if pain_regions else "未说明"
    mobility_text = f"{mobility_score}/10" if mobility_score is not None else "未评估"

    prompt = (
        f"你是一名运动康复领域的专业助手。请根据以下已审核的问诊信息，"
        f"撰写一段专业、谨慎、适合居家执行的康复处方摘要。\n"
        f"患者姓名: {patient_name}\n"
        f"年龄: {age_text}\n"
        f"主诉: {symptoms}\n"
        f"既往病史: {history_text}\n"
        f"疼痛部位: {pain_text}\n"
        f"活动度自评: {mobility_text}\n"
        f"推荐动作: {action_text}\n"
        f"\n"
        f"输出要求：\n"
        f"1. 使用规范中文，体现康复医学专业性；\n"
        f"2. 说明训练目标、动作逻辑与循序渐进方案；\n"
        f"3. 明确疼痛监测原则，出现剧烈疼痛需停止并就医；\n"
        f"4. 不要编造诊断名称，不要替代医生面诊；\n"
        f"5. 篇幅控制在150-250字。"
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
