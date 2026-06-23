from sqlalchemy.orm import Session
from . import models, schema
import base64
import hashlib
import hmac
import os
from datetime import date, timedelta


PASSWORD_ALGORITHM = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 120000


def _hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_ITERATIONS,
    )
    salt_text = base64.b64encode(salt).decode("ascii")
    digest_text = base64.b64encode(digest).decode("ascii")
    return f"{PASSWORD_ALGORITHM}${PASSWORD_ITERATIONS}${salt_text}${digest_text}"


def _verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations_text, salt_text, digest_text = password_hash.split("$", 3)
        if algorithm != PASSWORD_ALGORITHM:
            return False
        salt = base64.b64decode(salt_text.encode("ascii"))
        expected_digest = base64.b64decode(digest_text.encode("ascii"))
        actual_digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            int(iterations_text),
        )
        return hmac.compare_digest(actual_digest, expected_digest)
    except Exception:
        return False


def _user_response(user: models.UserModel) -> schema.UserResponse:
    return schema.UserResponse(
        id=user.id,
        account=user.account,
        nickname=user.nickname,
        role=user.role,
        gender=user.gender,
        age=user.age,
    )


def get_user_by_account(db: Session, account: str):
    return db.query(models.UserModel).filter(models.UserModel.account == account).first()


def create_user(db: Session, request: schema.UserCreateRequest) -> schema.UserResponse:
    admin_accounts = {
        account.strip().lower()
        for account in os.getenv("ADMIN_ACCOUNTS", "admin").split(",")
        if account.strip()
    }
    user = models.UserModel(
        account=request.account,
        password_hash=_hash_password(request.password),
        nickname=request.nickname,
        role="admin" if request.account.lower() in admin_accounts else "user",
        gender=request.gender,
        age=request.age,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _user_response(user)


def authenticate_user(db: Session, request: schema.UserLoginRequest):
    user = get_user_by_account(db, request.account)
    if not user or not _verify_password(request.password, user.password_hash):
        return None
    return user


def list_patient_profiles(db: Session, user_id: int):
    return (
        db.query(models.PatientProfileModel)
        .filter(models.PatientProfileModel.user_id == user_id)
        .order_by(models.PatientProfileModel.updated_at.desc())
        .all()
    )


def get_patient_profile(db: Session, profile_id: int, user_id: int):
    return (
        db.query(models.PatientProfileModel)
        .filter(
            models.PatientProfileModel.id == profile_id,
            models.PatientProfileModel.user_id == user_id,
        )
        .first()
    )


def create_patient_profile(db: Session, request: schema.PatientProfileCreateRequest, user_id: int):
    profile = models.PatientProfileModel(
        user_id=user_id,
        name=request.name,
        gender=request.gender,
        age=request.age,
        phone=request.phone,
        height_cm=request.height_cm,
        weight_kg=request.weight_kg,
        pain_regions=request.pain_regions,
        history=request.history,
        allergy_history=request.allergy_history,
        surgery_history=request.surgery_history,
        rehab_goal=request.rehab_goal,
        note=request.note,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def update_patient_profile(
    db: Session,
    profile: models.PatientProfileModel,
    request: schema.PatientProfileUpdateRequest,
):
    data = request.model_dump(exclude_unset=True) if hasattr(request, "model_dump") else request.dict(exclude_unset=True)
    for field, value in data.items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return profile


def delete_patient_profile(db: Session, profile: models.PatientProfileModel):
    db.delete(profile)
    db.commit()


def list_imaging_reports(db: Session, user_id: int, patient_profile_id: int | None = None):
    query = db.query(models.ImagingReportModel).filter(models.ImagingReportModel.user_id == user_id)
    if patient_profile_id is not None:
        query = query.filter(models.ImagingReportModel.patient_profile_id == patient_profile_id)
    return query.order_by(models.ImagingReportModel.created_at.desc()).all()


def get_imaging_report(db: Session, report_id: int, user_id: int):
    return (
        db.query(models.ImagingReportModel)
        .filter(
            models.ImagingReportModel.id == report_id,
            models.ImagingReportModel.user_id == user_id,
        )
        .first()
    )


def create_imaging_report(
    db: Session,
    request: schema.ImagingReportCreateRequest,
    user_id: int,
    file_path: str | None,
    ocr_status: str,
    risk_level: str,
    red_flags: list[dict],
):
    report = models.ImagingReportModel(
        user_id=user_id,
        patient_profile_id=request.patient_profile_id,
        report_type=request.report_type,
        file_name=request.file_name,
        file_path=file_path,
        ocr_text=request.ocr_text,
        ocr_status=ocr_status,
        risk_level=risk_level,
        red_flags=red_flags,
        note=request.note,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def list_training_checkins(
    db: Session,
    user_id: int,
    patient_profile_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
):
    query = db.query(models.TrainingCheckinModel).filter(models.TrainingCheckinModel.user_id == user_id)
    if patient_profile_id is not None:
        query = query.filter(models.TrainingCheckinModel.patient_profile_id == patient_profile_id)
    if start_date is not None:
        query = query.filter(models.TrainingCheckinModel.trained_on >= start_date)
    if end_date is not None:
        query = query.filter(models.TrainingCheckinModel.trained_on <= end_date)
    return query.order_by(models.TrainingCheckinModel.trained_on.desc(), models.TrainingCheckinModel.id.desc()).all()


def get_training_checkin(db: Session, checkin_id: int, user_id: int):
    return (
        db.query(models.TrainingCheckinModel)
        .filter(
            models.TrainingCheckinModel.id == checkin_id,
            models.TrainingCheckinModel.user_id == user_id,
        )
        .first()
    )


def create_training_checkin(db: Session, request: schema.TrainingCheckinCreateRequest, user_id: int):
    checkin = models.TrainingCheckinModel(
        user_id=user_id,
        patient_profile_id=request.patient_profile_id,
        prescription_id=request.prescription_id,
        action_id=request.action_id,
        action_name=request.action_name,
        trained_on=request.trained_on,
        duration_minutes=request.duration_minutes,
        completed_sets=request.completed_sets,
        completed_reps=request.completed_reps,
        pain_before=request.pain_before,
        pain_after=request.pain_after,
        difficulty=request.difficulty,
        score=request.score,
        note=request.note,
    )
    db.add(checkin)
    db.commit()
    db.refresh(checkin)
    return checkin


def update_training_checkin(
    db: Session,
    checkin: models.TrainingCheckinModel,
    request: schema.TrainingCheckinUpdateRequest,
):
    data = request.model_dump(exclude_unset=True) if hasattr(request, "model_dump") else request.dict(exclude_unset=True)
    for field, value in data.items():
        setattr(checkin, field, value)
    db.commit()
    db.refresh(checkin)
    return checkin


def delete_training_checkin(db: Session, checkin: models.TrainingCheckinModel):
    db.delete(checkin)
    db.commit()


def build_training_trends(
    db: Session,
    user_id: int,
    start_date: date,
    end_date: date,
    patient_profile_id: int | None = None,
):
    checkins = list_training_checkins(
        db,
        user_id=user_id,
        patient_profile_id=patient_profile_id,
        start_date=start_date,
        end_date=end_date,
    )
    grouped: dict[date, list[models.TrainingCheckinModel]] = {}
    for checkin in checkins:
        grouped.setdefault(checkin.trained_on, []).append(checkin)

    points = []
    current = start_date
    while current <= end_date:
        items = grouped.get(current, [])
        points.append(_training_trend_point(current, items))
        current += timedelta(days=1)
    return points


def _average(values):
    values = [value for value in values if value is not None]
    if not values:
        return None
    return round(sum(values) / len(values), 1)


def _training_trend_point(day: date, checkins: list[models.TrainingCheckinModel]):
    return {
        "date": day,
        "checkin_count": len(checkins),
        "total_duration_minutes": sum(item.duration_minutes or 0 for item in checkins),
        "avg_pain_before": _average([item.pain_before for item in checkins]),
        "avg_pain_after": _average([item.pain_after for item in checkins]),
        "avg_score": _average([item.score for item in checkins]),
    }


def _action_to_dict(action: schema.ActionItem):
    if hasattr(action, "model_dump"):
        return action.model_dump()
    return action.dict()


def get_actions_by_prescription(db: Session, prescription_id: int):
    return db.query(models.ActionModel).filter(models.ActionModel.prescription_id == prescription_id).all()


def get_prescription(db: Session, prescription_id: int, user_id: int | None = None):
    query = db.query(models.PrescriptionModel).filter(models.PrescriptionModel.id == prescription_id)
    if user_id is not None:
        query = query.filter(models.PrescriptionModel.user_id == user_id)
    return query.first()


def list_prescriptions(db: Session, user_id: int | None = None):
    query = db.query(models.PrescriptionModel)
    if user_id is not None:
        query = query.filter(models.PrescriptionModel.user_id == user_id)
    return query.order_by(models.PrescriptionModel.created_at.desc()).all()


def create_prescription(
    db: Session,
    prescription: schema.PrescriptionRequest,
    user_id: int | None = None,
    patient_profile_id: int | None = None,
):
    from .knowledge import load_prompt_template, render_prescription_summary, select_actions_for_prescription
    from .doubao import generate_prescription_summary
    from .safety import evaluate_prescription_safety

    selected_actions = select_actions_for_prescription(
        symptoms=prescription.symptoms,
        pain_regions=prescription.pain_regions,
        history=prescription.history,
        mobility_score=prescription.mobility_score,
    )
    selected_actions, safety = evaluate_prescription_safety(
        selected_actions,
        symptoms=prescription.symptoms,
        history=prescription.history,
        mobility_score=prescription.mobility_score,
    )
    action_payload = [_action_to_dict(action) for action in selected_actions]

    result = generate_prescription_summary(
        patient_name=prescription.name or "患者",
        age=prescription.age,
        symptoms=prescription.symptoms,
        history=prescription.history,
        actions=action_payload,
        pain_regions=prescription.pain_regions,
        mobility_score=prescription.mobility_score,
        prompt_template=load_prompt_template(),
    )
    parsed = result.get("json") if isinstance(result, dict) else None
    model_summary = parsed.get("summary") if isinstance(parsed, dict) else None
    summary = model_summary or result.get("text") or render_prescription_summary(
        name=prescription.name,
        age=prescription.age,
        symptoms=prescription.symptoms,
        history=prescription.history,
        actions=selected_actions,
        mobility_score=prescription.mobility_score,
    )
    raw_response = {
        "model_text": result.get("text"),
        "model_json": parsed,
        "raw": result.get("raw"),
        "safety": safety,
    } if isinstance(result, dict) else None

    db_prescription = models.PrescriptionModel(
        user_id=user_id,
        patient_profile_id=patient_profile_id,
        patient_name=prescription.name,
        patient_age=prescription.age,
        symptoms=prescription.symptoms,
        history=prescription.history,
        summary=summary,
        raw_response=raw_response
    )
    db.add(db_prescription)
    db.commit()
    db.refresh(db_prescription)

    for action in selected_actions:
        db_action = models.ActionModel(
            prescription_id=db_prescription.id,
            name=action.name,
            sets=action.sets,
            reps=action.reps,
            note=action.note
        )
        db.add(db_action)
    db.commit()
    db.refresh(db_prescription)

    return db_prescription


def create_pose_feedback(db: Session, request: schema.PoseCorrectionRequest):
    from .algorithms import analyze_pose

    if not request.action_id:
        result = {
            "feedback": ["缺少动作类型，请先选择要跟练的动作。"],
            "score": 0,
            "status": "error",
        }
    elif not request.keypoints:
        result = {
            "feedback": ["缺少姿态关键点，请重新采集视频帧。"],
            "score": 0,
            "status": "error",
        }
    elif len(request.keypoints) < 33:
        result = {
            "feedback": ["姿态关键点不足，请确保全身进入画面。"],
            "score": 0,
            "status": "error",
        }
    else:
        result = analyze_pose(
            action_id=request.action_id,
            keypoints=request.keypoints,
            visibility=request.visibility or [1.0] * len(request.keypoints),
        )

    db_feedback = models.PoseFeedbackModel(
        request_data={
            "action_id": request.action_id,
            "keypoints": request.keypoints,
            "visibility": request.visibility,
            "timestamp": request.timestamp,
        },
        feedback=result.get("feedback", [])
    )
    db.add(db_feedback)
    db.commit()
    db.refresh(db_feedback)
    return result
