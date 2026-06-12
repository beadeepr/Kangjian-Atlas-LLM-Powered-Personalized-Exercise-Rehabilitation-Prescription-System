import os
from typing import Optional
import json
import requests

DOUBAO_API_KEY = os.getenv("DOUBAO_API_KEY")
DOUBAO_BASE_URL = os.getenv("DOUBAO_BASE_URL")
DOUBAO_MODEL_ID = os.getenv("DOUBAO_MODEL_ID")


class DoubaoError(Exception):
    pass


def _headers():
    if not DOUBAO_API_KEY:
        raise DoubaoError("Missing DOUBAO_API_KEY environment variable")
    return {
        "Authorization": f"Bearer {DOUBAO_API_KEY}",
        "Content-Type": "application/json",
    }


def generate_with_http(prompt: str, model_id: Optional[str] = None, timeout: int = 30) -> str:
    """Generic HTTP fallback to call Doubao/Ark REST endpoint. Replace `invoke_path` if your region differs."""
    if not DOUBAO_BASE_URL:
        raise DoubaoError("Missing DOUBAO_BASE_URL environment variable")
    model = model_id or DOUBAO_MODEL_ID
    if not model:
        raise DoubaoError("Missing DOUBAO_MODEL_ID (or model_id argument)")

    # NOTE: ensure this path matches the API in your account; adjust if needed
    invoke_path = "/invoke"
    url = DOUBAO_BASE_URL.rstrip("/") + invoke_path

    payload = {
        "model": model,
        "input": prompt,
        # add other parameters if required by your API
    }

    resp = requests.post(url, headers=_headers(), json=payload, timeout=timeout)
    try:
        resp.raise_for_status()
    except requests.HTTPError as exc:
        raise DoubaoError(f"HTTP error from Doubao: {resp.status_code} {resp.text}") from exc

    try:
        data = resp.json()
    except Exception:
        # return both text and raw
        return {"text": resp.text, "raw": resp.text}

    # Attempt to extract text from common fields
    extracted = None
    if isinstance(data, dict):
        for key in ("output", "result", "data", "choices", "response"):
            if key in data:
                val = data[key]
                extracted = json.dumps(val, ensure_ascii=False) if not isinstance(val, str) else val
                break
    if extracted is None:
        extracted = json.dumps(data, ensure_ascii=False)
    return {"text": extracted, "raw": data}


def generate_summary(prompt: str, model_id: Optional[str] = None) -> str:
    """Try to use the installed volcengine SDK (ARKApi). If that fails, fall back to HTTP requests."""
    # Try SDK first
    try:
        from volcenginesdkark.api import ARKApi
        # instantiate client (SDK uses environment configuration)
        client = ARKApi()
        # Attempt to call a synchronous/simple method if available.
        # Many Ark endpoints are async (batch). We attempt create_batch_inference_job as best-effort.
        payload = {
            "foundationModel": {"model": model_id or DOUBAO_MODEL_ID},
            "input": {"input": prompt}
        }
        # Some SDK variants accept dict directly; wrap in try/except
        if hasattr(client, "create_batch_inference_job"):
            resp = client.create_batch_inference_job(body=payload)
            # try to extract text if possible, else return resp as raw
            try:
                # attempt to get dict-like representation
                raw = resp if isinstance(resp, (dict, list)) else getattr(resp, '__dict__', str(resp))
                text = str(resp)
                return {"text": text, "raw": raw}
            except Exception:
                return {"text": str(resp), "raw": str(resp)}
        # fallback to other available method names
        if hasattr(client, "create_endpoint"):
            resp = client.create_endpoint(body={"foundationModel": {"model": model_id or DOUBAO_MODEL_ID}})
            return {"text": str(resp), "raw": resp}
    except Exception:
        # ignore SDK errors and try HTTP fallback
        pass

    # HTTP fallback
    return generate_with_http(prompt, model_id=model_id)
def generate_prescription_summary(
    patient_name: str,
    age: Optional[int],
    symptoms: str,
    history: Optional[str],
    actions: list[str],
) -> str:
    """Generate prescription summary using Doubao/Ark. This wraps `generate_summary()` with a structured prompt and falls back to local summary on error."""
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
        result = generate_summary(prompt)
        # result may be str or dict
        if isinstance(result, dict):
            return result
        return {"text": result, "raw": None}
    except Exception:
        # fallback returns text string
        return {"text": _fallback_summary(patient_name, age, symptoms, history, actions), "raw": None}


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
