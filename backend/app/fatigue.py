from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any


def _risk_label(score: int) -> str:
    if score >= 75:
        return "high"
    if score >= 45:
        return "medium"
    return "low"


def evaluate_fatigue(
    heart_rate: int | None = None,
    resting_heart_rate: int | None = None,
    hrv_ms: int | None = None,
    spo2: int | None = None,
    perceived_exertion: int | None = None,
    duration_minutes: int | None = None,
    previous_metrics: list[Any] | None = None,
) -> dict[str, Any]:
    score = 0
    signals = []

    if heart_rate is not None:
        baseline = resting_heart_rate or _average([item.resting_heart_rate for item in previous_metrics or []]) or 70
        delta = heart_rate - baseline
        if heart_rate >= 150 or delta >= 65:
            score += 35
            signals.append("heart_rate_high")
        elif heart_rate >= 130 or delta >= 45:
            score += 22
            signals.append("heart_rate_elevated")
        elif heart_rate >= 110:
            score += 10
            signals.append("heart_rate_moderate")

    if hrv_ms is not None:
        if hrv_ms < 25:
            score += 25
            signals.append("hrv_low")
        elif hrv_ms < 40:
            score += 12
            signals.append("hrv_declining")

    if spo2 is not None:
        if spo2 < 92:
            score += 35
            signals.append("spo2_low")
        elif spo2 < 95:
            score += 18
            signals.append("spo2_watch")

    if perceived_exertion is not None:
        if perceived_exertion >= 8:
            score += 25
            signals.append("rpe_high")
        elif perceived_exertion >= 6:
            score += 12
            signals.append("rpe_moderate")

    if duration_minutes is not None:
        if duration_minutes >= 60:
            score += 15
            signals.append("duration_long")
        elif duration_minutes >= 40:
            score += 8
            signals.append("duration_moderate")

    score = max(0, min(100, score))
    risk_level = _risk_label(score)
    return {
        "fatigue_score": score,
        "risk_level": risk_level,
        "signals": signals,
        "recommendation": fatigue_recommendation(risk_level, signals),
        "should_stop": risk_level == "high" or "spo2_low" in signals,
    }


def fatigue_recommendation(risk_level: str, signals: list[str]) -> str:
    if risk_level == "high":
        return "疲劳风险较高，建议立即暂停训练，坐下休息并补水；若胸闷、头晕或血氧偏低，请及时就医。"
    if risk_level == "medium":
        return "疲劳程度上升，建议降低动作强度或延长组间休息，下一组从低幅度开始。"
    return "当前疲劳风险较低，可继续训练，但仍需保持呼吸平稳并关注疼痛变化。"


def summarize_recent_metrics(metrics: list[Any], window_minutes: int = 30) -> dict[str, Any]:
    if not metrics:
        return {
            "latest": None,
            "fatigue_score": 0,
            "risk_level": "low",
            "recommendation": "暂无可用穿戴设备数据，请按主观疲劳感控制训练强度。",
            "should_stop": False,
            "sample_count": 0,
        }

    latest = metrics[0]
    cutoff = datetime.utcnow() - timedelta(minutes=window_minutes)
    recent = [item for item in metrics if item.recorded_at and item.recorded_at >= cutoff]
    recent = recent or metrics[:1]
    avg_heart_rate = _average([item.heart_rate for item in recent])
    avg_hrv = _average([item.hrv_ms for item in recent])
    avg_spo2 = _average([item.spo2 for item in recent])
    avg_rpe = _average([item.perceived_exertion for item in recent])
    evaluation = evaluate_fatigue(
        heart_rate=round(avg_heart_rate) if avg_heart_rate is not None else latest.heart_rate,
        resting_heart_rate=latest.resting_heart_rate,
        hrv_ms=round(avg_hrv) if avg_hrv is not None else latest.hrv_ms,
        spo2=round(avg_spo2) if avg_spo2 is not None else latest.spo2,
        perceived_exertion=round(avg_rpe) if avg_rpe is not None else latest.perceived_exertion,
        duration_minutes=latest.duration_minutes,
        previous_metrics=metrics,
    )
    return {
        "latest": metric_to_dict(latest),
        "fatigue_score": evaluation["fatigue_score"],
        "risk_level": evaluation["risk_level"],
        "signals": evaluation["signals"],
        "recommendation": evaluation["recommendation"],
        "should_stop": evaluation["should_stop"],
        "sample_count": len(recent),
        "averages": {
            "heart_rate": avg_heart_rate,
            "hrv_ms": avg_hrv,
            "spo2": avg_spo2,
            "perceived_exertion": avg_rpe,
        },
    }


def metric_to_dict(metric) -> dict[str, Any]:
    return {
        "id": metric.id,
        "user_id": metric.user_id,
        "patient_profile_id": metric.patient_profile_id,
        "training_checkin_id": metric.training_checkin_id,
        "device_type": metric.device_type,
        "heart_rate": metric.heart_rate,
        "resting_heart_rate": metric.resting_heart_rate,
        "hrv_ms": metric.hrv_ms,
        "spo2": metric.spo2,
        "steps": metric.steps,
        "calories": metric.calories,
        "skin_temperature_c": metric.skin_temperature_c,
        "perceived_exertion": metric.perceived_exertion,
        "duration_minutes": metric.duration_minutes,
        "fatigue_score": metric.fatigue_score,
        "risk_level": metric.risk_level,
        "signals": metric.signals or [],
        "recommendation": metric.recommendation,
        "recorded_at": metric.recorded_at,
        "created_at": metric.created_at,
    }


def _average(values):
    values = [value for value in values if value is not None]
    if not values:
        return None
    return round(sum(values) / len(values), 1)

