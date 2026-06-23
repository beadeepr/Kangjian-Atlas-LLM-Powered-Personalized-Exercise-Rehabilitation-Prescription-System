from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from . import models
from .knowledge import load_action_catalog


def _count(db: Session, model) -> int:
    return db.query(func.count(model.id)).scalar() or 0


def _count_recent(db: Session, model, days: int = 7) -> int:
    since = date.today() - timedelta(days=days - 1)
    column = getattr(model, "created_at", None)
    if column is None:
        return 0
    return db.query(func.count(model.id)).filter(column >= since).scalar() or 0


def feedback_response(feedback: models.UserFeedbackModel) -> dict[str, Any]:
    user = feedback.user
    return {
        "id": feedback.id,
        "user_id": feedback.user_id,
        "user_account": user.account if user else None,
        "user_nickname": user.nickname if user else None,
        "category": feedback.category,
        "rating": feedback.rating,
        "content": feedback.content,
        "contact": feedback.contact,
        "source": feedback.source,
        "status": feedback.status,
        "admin_note": feedback.admin_note,
        "created_at": feedback.created_at,
        "updated_at": feedback.updated_at,
    }


def create_feedback(
    db: Session,
    user_id: int | None,
    category: str,
    rating: int | None,
    content: str,
    contact: str | None,
    source: str | None,
) -> models.UserFeedbackModel:
    feedback = models.UserFeedbackModel(
        user_id=user_id,
        category=category,
        rating=rating,
        content=content,
        contact=contact,
        source=source,
        status="open",
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback


def list_feedback(
    db: Session,
    status: str | None = None,
    category: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[models.UserFeedbackModel]:
    query = db.query(models.UserFeedbackModel)
    if status:
        query = query.filter(models.UserFeedbackModel.status == status)
    if category:
        query = query.filter(models.UserFeedbackModel.category == category)
    return (
        query.order_by(models.UserFeedbackModel.created_at.desc(), models.UserFeedbackModel.id.desc())
        .offset(max(0, offset))
        .limit(max(1, min(limit, 200)))
        .all()
    )


def build_admin_dashboard(db: Session) -> dict[str, Any]:
    actions = load_action_catalog()
    categories = {}
    body_regions = {}
    for action in actions:
        category = action.get("category") or "未分类"
        categories[category] = categories.get(category, 0) + 1
        for region in action.get("body_regions") or []:
            body_regions[region] = body_regions.get(region, 0) + 1

    feedback_by_status = dict(
        db.query(models.UserFeedbackModel.status, func.count(models.UserFeedbackModel.id))
        .group_by(models.UserFeedbackModel.status)
        .all()
    )
    feedback_by_category = dict(
        db.query(models.UserFeedbackModel.category, func.count(models.UserFeedbackModel.id))
        .group_by(models.UserFeedbackModel.category)
        .all()
    )
    risk_by_level = dict(
        db.query(models.ImagingReportModel.risk_level, func.count(models.ImagingReportModel.id))
        .group_by(models.ImagingReportModel.risk_level)
        .all()
    )
    return {
        "totals": {
            "users": _count(db, models.UserModel),
            "patient_profiles": _count(db, models.PatientProfileModel),
            "prescriptions": _count(db, models.PrescriptionModel),
            "training_checkins": _count(db, models.TrainingCheckinModel),
            "imaging_reports": _count(db, models.ImagingReportModel),
            "pose_feedback": _count(db, models.PoseFeedbackModel),
            "user_feedback": _count(db, models.UserFeedbackModel),
            "actions": len(actions),
        },
        "recent_activity": {
            "new_users_7d": _count_recent(db, models.UserModel, days=7),
            "new_prescriptions_7d": _count_recent(db, models.PrescriptionModel, days=7),
            "training_checkins_7d": _count_recent(db, models.TrainingCheckinModel, days=7),
            "feedback_7d": _count_recent(db, models.UserFeedbackModel, days=7),
        },
        "feedback_summary": {
            "by_status": feedback_by_status,
            "by_category": feedback_by_category,
            "open_count": feedback_by_status.get("open", 0),
        },
        "action_library_summary": {
            "by_category": categories,
            "by_body_region": body_regions,
        },
        "risk_summary": {
            "imaging_reports_by_risk": risk_by_level,
            "red_flag_reports": sum(count for level, count in risk_by_level.items() if level in {"medium", "high"}),
        },
    }


def list_admin_users(db: Session, q: str | None = None, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    query = db.query(models.UserModel)
    if q:
        keyword = f"%{q.strip()}%"
        query = query.filter(
            (models.UserModel.account.like(keyword)) |
            (models.UserModel.nickname.like(keyword))
        )
    users = (
        query.order_by(models.UserModel.created_at.desc(), models.UserModel.id.desc())
        .offset(max(0, offset))
        .limit(max(1, min(limit, 200)))
        .all()
    )
    result = []
    for user in users:
        result.append({
            "id": user.id,
            "account": user.account,
            "nickname": user.nickname,
            "role": user.role,
            "gender": user.gender,
            "age": user.age,
            "patient_profile_count": len(user.patient_profiles or []),
            "prescription_count": len(user.prescriptions or []),
            "training_checkin_count": len(user.training_checkins or []),
            "imaging_report_count": len(user.imaging_reports or []),
            "feedback_count": len(user.feedback_items or []),
            "created_at": user.created_at,
            "updated_at": user.updated_at,
        })
    return result
