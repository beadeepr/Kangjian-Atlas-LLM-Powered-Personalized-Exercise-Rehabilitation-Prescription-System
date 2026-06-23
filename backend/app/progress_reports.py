from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from sqlalchemy.orm import Session

from . import models
from .crud import build_training_trends, list_training_checkins


def _average(values: list[int | float | None]) -> float | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return round(sum(present) / len(present), 1)


def normalize_report_dates(
    period: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> tuple[str, date, date]:
    normalized = (period or "weekly").lower()
    if normalized not in {"weekly", "monthly", "custom"}:
        raise ValueError("period must be weekly, monthly or custom")

    today = date.today()
    if end_date is None:
        end_date = today
    if start_date is None:
        start_date = end_date - timedelta(days=6 if normalized == "weekly" else 29)

    if start_date > end_date:
        raise ValueError("start_date cannot be after end_date")
    if (end_date - start_date).days > 180:
        raise ValueError("report date range cannot exceed 180 days")
    return normalized, start_date, end_date


def _action_summaries(checkins: list[models.TrainingCheckinModel]) -> list[dict[str, Any]]:
    grouped: dict[str, list[models.TrainingCheckinModel]] = defaultdict(list)
    for checkin in checkins:
        grouped[checkin.action_name].append(checkin)

    summaries = []
    for action_name, items in grouped.items():
        summaries.append({
            "action_name": action_name,
            "count": len(items),
            "total_duration_minutes": sum(item.duration_minutes or 0 for item in items),
            "avg_score": _average([item.score for item in items]),
        })
    return sorted(summaries, key=lambda item: (item["count"], item["total_duration_minutes"]), reverse=True)


def _vas_summary(avg_before: float | None, avg_after: float | None, avg_change: float | None) -> str:
    if avg_before is None or avg_after is None or avg_change is None:
        return "本周期疼痛 VAS 数据不足，建议训练前后持续记录。"
    if avg_change <= -1:
        return f"本周期训练后 VAS 平均下降 {abs(avg_change):.1f} 分，疼痛趋势改善。"
    if avg_change < 0:
        return f"本周期训练后 VAS 平均下降 {abs(avg_change):.1f} 分，已有轻度改善。"
    if avg_change == 0:
        return "本周期训练前后 VAS 基本持平，建议继续观察。"
    return f"本周期训练后 VAS 平均上升 {avg_change:.1f} 分，需要降低强度并关注不适。"


def _report_messages(
    checkins: list[models.TrainingCheckinModel],
    active_days: int,
    expected_days: int,
    completion_rate: float,
    avg_score: float | None,
    avg_change: float | None,
) -> tuple[list[str], list[str], list[str]]:
    highlights = []
    risks = []
    recommendations = []

    if active_days:
        highlights.append(f"本周期共训练 {active_days} 天，完成 {len(checkins)} 条打卡。")
    else:
        risks.append("本周期暂无训练打卡，无法判断康复进度。")

    if completion_rate >= 0.7:
        highlights.append("训练连续性较好，完成率达到目标水平。")
    elif completion_rate >= 0.4:
        recommendations.append("完成率中等，可优先固定每周 3-4 天训练时间。")
    else:
        risks.append("完成率偏低，康复计划执行不足。")

    if avg_score is not None and avg_score >= 85:
        highlights.append("动作评分整体较好，说明跟练质量稳定。")
    elif avg_score is not None and avg_score < 70:
        recommendations.append("动作评分偏低，建议降低难度并重点查看动作纠错提示。")

    if avg_change is not None and avg_change > 0:
        risks.append("训练后疼痛评分上升，建议减少组数或暂停诱发疼痛的动作。")
    elif avg_change is not None and avg_change <= -1:
        highlights.append("训练后疼痛评分较训练前下降，短期反馈积极。")

    if not recommendations:
        recommendations.append("继续保持当前训练节奏，逐步增加动作质量和完成稳定性。")
    recommendations.append("如出现剧烈疼痛、麻木无力、大小便异常或症状快速加重，应停止训练并就医。")
    return highlights, risks, recommendations


def build_training_report(
    db: Session,
    user_id: int,
    period: str,
    start_date: date,
    end_date: date,
    patient_profile_id: int | None = None,
) -> dict[str, Any]:
    checkins = list_training_checkins(
        db,
        user_id=user_id,
        patient_profile_id=patient_profile_id,
        start_date=start_date,
        end_date=end_date,
    )
    expected_days = (end_date - start_date).days + 1
    active_days = len({checkin.trained_on for checkin in checkins})
    completion_rate = round(active_days / expected_days, 2) if expected_days else 0
    pain_changes = [
        checkin.pain_after - checkin.pain_before
        for checkin in checkins
        if checkin.pain_before is not None and checkin.pain_after is not None
    ]
    avg_score = _average([checkin.score for checkin in checkins])
    avg_before = _average([checkin.pain_before for checkin in checkins])
    avg_after = _average([checkin.pain_after for checkin in checkins])
    avg_change = _average(pain_changes)
    total_duration = sum(checkin.duration_minutes or 0 for checkin in checkins)
    points = build_training_trends(
        db,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        patient_profile_id=patient_profile_id,
    )
    highlights, risks, recommendations = _report_messages(
        checkins=checkins,
        active_days=active_days,
        expected_days=expected_days,
        completion_rate=completion_rate,
        avg_score=avg_score,
        avg_change=avg_change,
    )
    return {
        "period": period,
        "start_date": start_date,
        "end_date": end_date,
        "patient_profile_id": patient_profile_id,
        "total_checkins": len(checkins),
        "expected_days": expected_days,
        "active_days": active_days,
        "completion_rate": completion_rate,
        "total_duration_minutes": total_duration,
        "avg_duration_per_active_day": round(total_duration / active_days, 1) if active_days else None,
        "avg_score": avg_score,
        "avg_pain_before": avg_before,
        "avg_pain_after": avg_after,
        "avg_pain_change": avg_change,
        "vas_summary": _vas_summary(avg_before, avg_after, avg_change),
        "action_summaries": _action_summaries(checkins),
        "highlights": highlights,
        "risks": risks,
        "recommendations": recommendations,
        "trend": {
            "start_date": start_date,
            "end_date": end_date,
            "points": points,
        },
    }


def render_training_report_markdown(report: dict[str, Any]) -> str:
    action_lines = [
        f"- {item['action_name']}：{item['count']} 次，累计 {item['total_duration_minutes']} 分钟，平均评分 {item.get('avg_score') or '暂无'}"
        for item in report.get("action_summaries", [])
    ] or ["- 暂无动作打卡"]
    return "\n".join([
        "# 康复进度报告",
        "",
        f"- 周期：{report['start_date']} 至 {report['end_date']}",
        f"- 训练天数：{report['active_days']} / {report['expected_days']}",
        f"- 完成率：{int(report['completion_rate'] * 100)}%",
        f"- 累计训练时长：{report['total_duration_minutes']} 分钟",
        f"- 平均动作评分：{report.get('avg_score') or '暂无'}",
        f"- VAS 总结：{report['vas_summary']}",
        "",
        "## 动作分布",
        *action_lines,
        "",
        "## 亮点",
        *[f"- {item}" for item in report.get("highlights", [])],
        "",
        "## 风险",
        *[f"- {item}" for item in report.get("risks", []) or ["暂无明显风险"]],
        "",
        "## 建议",
        *[f"- {item}" for item in report.get("recommendations", [])],
        "",
    ])
