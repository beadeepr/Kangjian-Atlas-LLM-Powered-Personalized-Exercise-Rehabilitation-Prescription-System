from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from . import models
from .knowledge import load_action_library


ACTIVE_LINK_STATUS = "active"


def is_doctor(user: models.UserModel) -> bool:
    return user.role in {"doctor", "admin"}


def doctor_patient_link_exists(db: Session, doctor_id: int, user_id: int, patient_profile_id: int | None = None) -> bool:
    query = db.query(models.DoctorPatientLinkModel).filter(
        models.DoctorPatientLinkModel.doctor_id == doctor_id,
        models.DoctorPatientLinkModel.user_id == user_id,
        models.DoctorPatientLinkModel.status == ACTIVE_LINK_STATUS,
    )
    if patient_profile_id is not None:
        query = query.filter(
            (models.DoctorPatientLinkModel.patient_profile_id == patient_profile_id)
            | (models.DoctorPatientLinkModel.patient_profile_id.is_(None))
        )
    return query.first() is not None


def review_response(review: models.PrescriptionReviewModel) -> dict[str, Any]:
    return {
        "id": review.id,
        "prescription_id": review.prescription_id,
        "user_id": review.user_id,
        "doctor_id": review.doctor_id,
        "patient_profile_id": review.patient_profile_id,
        "status": review.status,
        "patient_note": review.patient_note,
        "doctor_note": review.doctor_note,
        "risk_level": review.risk_level,
        "reviewed_at": review.reviewed_at,
        "created_at": review.created_at,
        "updated_at": review.updated_at,
    }


def link_response(link: models.DoctorPatientLinkModel) -> dict[str, Any]:
    return {
        "id": link.id,
        "user_id": link.user_id,
        "doctor_id": link.doctor_id,
        "patient_profile_id": link.patient_profile_id,
        "status": link.status,
        "patient_note": link.patient_note,
        "doctor_note": link.doctor_note,
        "patient_name": link.patient_profile.name if link.patient_profile else None,
        "created_at": link.created_at,
        "updated_at": link.updated_at,
    }


def adjustment_response(adjustment: models.PrescriptionAdjustmentModel) -> dict[str, Any]:
    return {
        "id": adjustment.id,
        "review_id": adjustment.review_id,
        "prescription_id": adjustment.prescription_id,
        "user_id": adjustment.user_id,
        "doctor_id": adjustment.doctor_id,
        "source": adjustment.source,
        "status": adjustment.status,
        "reason": adjustment.reason,
        "summary": adjustment.summary,
        "action_changes": adjustment.action_changes or [],
        "adjusted_actions": adjustment.adjusted_actions or [],
        "created_prescription_id": adjustment.created_prescription_id,
        "decided_at": adjustment.decided_at,
        "created_at": adjustment.created_at,
        "updated_at": adjustment.updated_at,
    }


def actions_for_prescription(db: Session, prescription_id: int) -> list[dict[str, Any]]:
    library = {item.name: item for item in load_action_library()}
    actions = []
    for action in db.query(models.ActionModel).filter(models.ActionModel.prescription_id == prescription_id).all():
        item = library.get(action.name)
        payload = item.model_dump() if item and hasattr(item, "model_dump") else item.dict() if item else {}
        payload.update({
            "name": action.name,
            "sets": action.sets,
            "reps": action.reps,
            "note": action.note,
        })
        actions.append(payload)
    return actions


def normalize_adjusted_actions(base_actions: list[dict[str, Any]], changes: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    actions = [{**action} for action in base_actions]
    changes = changes or []
    for change in changes:
        action_id = change.get("action_id")
        action_name = change.get("name")
        operation = change.get("operation", "update")
        index = next(
            (
                i for i, action in enumerate(actions)
                if (action_id and action.get("id") == action_id) or (action_name and action.get("name") == action_name)
            ),
            None,
        )
        if operation == "remove" and index is not None:
            actions.pop(index)
            continue
        if operation == "add":
            actions.append({
                "id": action_id,
                "name": action_name or "新增康复动作",
                "sets": change.get("sets", 1),
                "reps": change.get("reps", 1),
                "note": change.get("note"),
            })
            continue
        if index is not None:
            for field in ("sets", "reps", "note", "frequency", "difficulty_level"):
                if field in change and change[field] is not None:
                    actions[index][field] = change[field]
    return actions


def build_auto_adjustment(db: Session, prescription: models.PrescriptionModel) -> dict[str, Any]:
    since = datetime.utcnow().date() - timedelta(days=14)
    checkins = (
        db.query(models.TrainingCheckinModel)
        .filter(
            models.TrainingCheckinModel.user_id == prescription.user_id,
            models.TrainingCheckinModel.prescription_id == prescription.id,
            models.TrainingCheckinModel.trained_on >= since,
        )
        .all()
    )
    base_actions = actions_for_prescription(db, prescription.id)
    completion_days = {item.trained_on for item in checkins}
    completion_rate = len(completion_days) / 14 if checkins else 0
    avg_pain_change = _avg([(item.pain_after or 0) - (item.pain_before or 0) for item in checkins if item.pain_before is not None and item.pain_after is not None])

    changes = []
    reasons = []
    if avg_pain_change is not None and avg_pain_change > 1:
        reasons.append("训练后疼痛评分有上升趋势，建议降低幅度并延长休息。")
        for action in base_actions:
            changes.append({
                "operation": "update",
                "action_id": action.get("id"),
                "name": action.get("name"),
                "sets": max(1, (action.get("sets") or 1) - 1),
                "note": "因疼痛趋势上升，系统建议减少一组并控制在无痛范围。",
            })
    elif completion_rate >= 0.6 and (avg_pain_change is None or avg_pain_change <= 0):
        reasons.append("近期完成率较好且疼痛未加重，可小幅进阶训练。")
        for action in base_actions[:2]:
            changes.append({
                "operation": "update",
                "action_id": action.get("id"),
                "name": action.get("name"),
                "sets": min((action.get("sets") or 1) + 1, 5),
                "note": "完成率稳定，系统建议小幅进阶，仍需保持无痛原则。",
            })
    else:
        reasons.append("近期数据不足或变化不明显，建议维持当前方案并继续记录。")

    adjusted_actions = normalize_adjusted_actions(base_actions, changes)
    return {
        "reason": "；".join(reasons),
        "summary": f"系统基于近14天训练数据生成调整建议：完成率约 {int(completion_rate * 100)}%。",
        "action_changes": changes,
        "adjusted_actions": adjusted_actions,
    }


def apply_adjustment(db: Session, adjustment: models.PrescriptionAdjustmentModel) -> models.PrescriptionModel:
    source = adjustment.prescription
    adjusted_actions = adjustment.adjusted_actions or []
    new_prescription = models.PrescriptionModel(
        user_id=source.user_id,
        patient_profile_id=source.patient_profile_id,
        patient_name=source.patient_name,
        patient_age=source.patient_age,
        symptoms=source.symptoms,
        history=source.history,
        summary=adjustment.summary or source.summary,
        raw_response={
            "source_prescription_id": source.id,
            "adjustment_id": adjustment.id,
            "adjustment_source": adjustment.source,
            "reason": adjustment.reason,
        },
    )
    db.add(new_prescription)
    db.commit()
    db.refresh(new_prescription)

    for action in adjusted_actions:
        db.add(models.ActionModel(
            prescription_id=new_prescription.id,
            name=action.get("name") or "未命名动作",
            sets=action.get("sets"),
            reps=action.get("reps"),
            note=action.get("note") or action.get("description"),
        ))
    adjustment.status = "applied"
    adjustment.created_prescription_id = new_prescription.id
    adjustment.decided_at = datetime.utcnow()
    db.commit()
    db.refresh(adjustment)
    db.refresh(new_prescription)
    return new_prescription


def _avg(values: list[int | float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 2)

