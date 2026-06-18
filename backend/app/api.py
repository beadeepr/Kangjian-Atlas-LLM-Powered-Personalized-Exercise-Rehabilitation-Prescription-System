from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy.orm import Session
from datetime import date, timedelta
import re
import os
import json
from .auth import AuthError, create_access_token, decode_access_token
from . import models
from .crud import (
    authenticate_user,
    build_training_trends,
    create_patient_profile,
    create_prescription,
    create_pose_feedback,
    create_training_checkin,
    create_user,
    delete_patient_profile,
    delete_training_checkin,
    get_actions_by_prescription,
    get_patient_profile,
    get_prescription,
    get_training_checkin,
    get_user_by_account,
    list_patient_profiles,
    list_prescriptions as crud_list_prescriptions,
    list_training_checkins,
    update_patient_profile,
    update_training_checkin,
)
from .database import SessionLocal
from .schema import (
    ActionItem,
    ActionUpdateRequest,
    LoginResponse,
    PatientProfileCreateRequest,
    PatientProfileResponse,
    PatientProfileUpdateRequest,
    PoseCorrectionRequest,
    PoseCorrectionResponse,
    PrescriptionRequest,
    PrescriptionResponse,
    TrainingCheckinCreateRequest,
    TrainingCheckinResponse,
    TrainingCheckinUpdateRequest,
    TrainingTrendPoint,
    TrainingTrendResponse,
    TrainingVisualizationResponse,
    UserCreateRequest,
    UserLoginRequest,
    UserResponse,
)

router = APIRouter()


def action_response_items(actions):
    from .knowledge import load_action_library

    library_by_name = {item.name: item for item in load_action_library()}
    result = []
    for action in actions:
        item = library_by_name.get(action.name)
        if item:
            data = item.model_dump() if hasattr(item, "model_dump") else item.dict()
            data["sets"] = action.sets
            data["reps"] = action.reps
            data["note"] = action.note
            result.append(data)
        else:
            result.append({"name": action.name, "sets": action.sets, "reps": action.reps, "note": action.note})
    return result


def patient_profile_response(profile):
    return PatientProfileResponse(
        id=profile.id,
        user_id=profile.user_id,
        name=profile.name,
        gender=profile.gender,
        age=profile.age,
        phone=profile.phone,
        height_cm=profile.height_cm,
        weight_kg=profile.weight_kg,
        pain_regions=profile.pain_regions,
        history=profile.history,
        allergy_history=profile.allergy_history,
        surgery_history=profile.surgery_history,
        rehab_goal=profile.rehab_goal,
        note=profile.note,
    )


def training_checkin_response(checkin):
    return TrainingCheckinResponse(
        id=checkin.id,
        user_id=checkin.user_id,
        patient_profile_id=checkin.patient_profile_id,
        prescription_id=checkin.prescription_id,
        action_id=checkin.action_id,
        action_name=checkin.action_name,
        trained_on=checkin.trained_on,
        duration_minutes=checkin.duration_minutes,
        completed_sets=checkin.completed_sets,
        completed_reps=checkin.completed_reps,
        pain_before=checkin.pain_before,
        pain_after=checkin.pain_after,
        difficulty=checkin.difficulty,
        score=checkin.score,
        note=checkin.note,
    )


def clean_patient_profile_payload(req, partial: bool = False):
    raw_data = req.model_dump(exclude_unset=partial) if hasattr(req, "model_dump") else req.dict(exclude_unset=partial)
    name = raw_data.get("name")
    if name is not None:
        name = name.strip()
    if not partial and not name:
        raise HTTPException(status_code=400, detail="patient name required")
    if name is not None and not name:
        raise HTTPException(status_code=400, detail="patient name required")
    age = raw_data.get("age")
    height_cm = raw_data.get("height_cm")
    weight_kg = raw_data.get("weight_kg")
    if age is not None and not 0 < age <= 120:
        raise HTTPException(status_code=400, detail="age must be between 1 and 120")
    if height_cm is not None and not 30 <= height_cm <= 250:
        raise HTTPException(status_code=400, detail="height_cm must be between 30 and 250")
    if weight_kg is not None and not 2 <= weight_kg <= 300:
        raise HTTPException(status_code=400, detail="weight_kg must be between 2 and 300")

    cleaned = {
        "name": name,
        "gender": raw_data.get("gender").strip() if raw_data.get("gender") else None,
        "age": age,
        "phone": raw_data.get("phone").strip() if raw_data.get("phone") else None,
        "height_cm": height_cm,
        "weight_kg": weight_kg,
        "pain_regions": raw_data.get("pain_regions"),
        "history": raw_data.get("history").strip() if raw_data.get("history") else None,
        "allergy_history": raw_data.get("allergy_history").strip() if raw_data.get("allergy_history") else None,
        "surgery_history": raw_data.get("surgery_history").strip() if raw_data.get("surgery_history") else None,
        "rehab_goal": raw_data.get("rehab_goal").strip() if raw_data.get("rehab_goal") else None,
        "note": raw_data.get("note").strip() if raw_data.get("note") else None,
    }
    if partial:
        return {field: value for field, value in cleaned.items() if field in raw_data}
    return cleaned


def clean_training_checkin_payload(req, partial: bool = False):
    raw_data = req.model_dump(exclude_unset=partial) if hasattr(req, "model_dump") else req.dict(exclude_unset=partial)
    action_name = raw_data.get("action_name")
    if action_name is not None:
        action_name = action_name.strip()
    if not partial and not action_name:
        raise HTTPException(status_code=400, detail="action_name required")
    if action_name is not None and not action_name:
        raise HTTPException(status_code=400, detail="action_name required")
    if not partial and raw_data.get("trained_on") is None:
        raise HTTPException(status_code=400, detail="trained_on required")

    _validate_number_range(raw_data, "duration_minutes", 0, 600)
    _validate_number_range(raw_data, "completed_sets", 0, 100)
    _validate_number_range(raw_data, "completed_reps", 0, 1000)
    _validate_number_range(raw_data, "pain_before", 0, 10)
    _validate_number_range(raw_data, "pain_after", 0, 10)
    _validate_number_range(raw_data, "difficulty", 1, 10)
    _validate_number_range(raw_data, "score", 0, 100)

    cleaned = {
        "patient_profile_id": raw_data.get("patient_profile_id"),
        "prescription_id": raw_data.get("prescription_id"),
        "action_id": raw_data.get("action_id").strip() if raw_data.get("action_id") else None,
        "action_name": action_name,
        "trained_on": raw_data.get("trained_on"),
        "duration_minutes": raw_data.get("duration_minutes"),
        "completed_sets": raw_data.get("completed_sets"),
        "completed_reps": raw_data.get("completed_reps"),
        "pain_before": raw_data.get("pain_before"),
        "pain_after": raw_data.get("pain_after"),
        "difficulty": raw_data.get("difficulty"),
        "score": raw_data.get("score"),
        "note": raw_data.get("note").strip() if raw_data.get("note") else None,
    }
    if partial:
        return {field: value for field, value in cleaned.items() if field in raw_data}
    return cleaned


def _validate_number_range(data, field: str, min_value: int, max_value: int):
    value = data.get(field)
    if value is not None and not min_value <= value <= max_value:
        raise HTTPException(status_code=400, detail=f"{field} must be between {min_value} and {max_value}")


def validate_training_links(db: Session, user_id: int, patient_profile_id: int | None, prescription_id: int | None):
    profile = None
    prescription = None
    if patient_profile_id is not None:
        profile = get_patient_profile(db, profile_id=patient_profile_id, user_id=user_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Patient profile not found")
    if prescription_id is not None:
        prescription = get_prescription(db, prescription_id, user_id=user_id)
        if not prescription:
            raise HTTPException(status_code=404, detail="Prescription not found")
        if (
            patient_profile_id is not None
            and prescription.patient_profile_id is not None
            and prescription.patient_profile_id != patient_profile_id
        ):
            raise HTTPException(status_code=400, detail="prescription does not belong to this patient profile")
    return profile, prescription


def resolve_training_links(db: Session, user_id: int, payload: dict):
    patient_profile_id = payload.get("patient_profile_id")
    prescription_id = payload.get("prescription_id")
    _, prescription = validate_training_links(db, user_id, patient_profile_id, prescription_id)
    if patient_profile_id is None and prescription and prescription.patient_profile_id is not None:
        patient_profile_id = prescription.patient_profile_id
        validate_training_links(db, user_id, patient_profile_id, prescription_id)
        payload = {**payload, "patient_profile_id": patient_profile_id}
    return payload


def normalize_trend_dates(days: int, start_date: date | None, end_date: date | None):
    if days < 1 or days > 180:
        raise HTTPException(status_code=400, detail="days must be between 1 and 180")
    resolved_end = end_date or date.today()
    resolved_start = start_date or (resolved_end - timedelta(days=days - 1))
    if resolved_start > resolved_end:
        raise HTTPException(status_code=400, detail="start_date cannot be after end_date")
    if (resolved_end - resolved_start).days > 179:
        raise HTTPException(status_code=400, detail="date range cannot exceed 180 days")
    return resolved_start, resolved_end


def clean_action_payload(req: ActionItem | ActionUpdateRequest, partial: bool = False):
    raw_data = req.model_dump(exclude_unset=partial) if hasattr(req, "model_dump") else req.dict(exclude_unset=partial)
    action_id = raw_data.get("id")
    name = raw_data.get("name")
    if action_id is not None:
        action_id = action_id.strip()
    if name is not None:
        name = name.strip()
    if not partial and not action_id:
        raise HTTPException(status_code=400, detail="action id required")
    if not partial and not name:
        raise HTTPException(status_code=400, detail="action name required")
    if action_id is not None and not re.fullmatch(r"[a-zA-Z0-9_-]{2,64}", action_id):
        raise HTTPException(status_code=400, detail="action id must be 2-64 letters, numbers, underscores or hyphens")
    if name is not None and not name:
        raise HTTPException(status_code=400, detail="action name required")
    _validate_number_range(raw_data, "sets", 1, 20)
    _validate_number_range(raw_data, "reps", 1, 200)

    cleaned = {
        "id": action_id,
        "name": name,
        "target_conditions": raw_data.get("target_conditions") or [],
        "body_regions": raw_data.get("body_regions") or [],
        "sets": raw_data.get("sets"),
        "reps": raw_data.get("reps"),
        "frequency": raw_data.get("frequency").strip() if raw_data.get("frequency") else None,
        "description": raw_data.get("description").strip() if raw_data.get("description") else None,
        "note": raw_data.get("note").strip() if raw_data.get("note") else None,
        "contraindications": raw_data.get("contraindications").strip() if raw_data.get("contraindications") else None,
        "progression": raw_data.get("progression").strip() if raw_data.get("progression") else None,
        "regression": raw_data.get("regression").strip() if raw_data.get("regression") else None,
    }
    if partial:
        cleaned = {field: value for field, value in cleaned.items() if field in raw_data}
    if not partial:
        cleaned["sets"] = cleaned["sets"] if cleaned["sets"] is not None else 1
        cleaned["reps"] = cleaned["reps"] if cleaned["reps"] is not None else 1
    return {field: value for field, value in cleaned.items() if value is not None}


def action_item_from_payload(payload: dict):
    return ActionItem(
        id=payload.get("id"),
        name=payload.get("name"),
        sets=payload.get("sets", 1),
        reps=payload.get("reps", 1),
        note=payload.get("note") or payload.get("description"),
        description=payload.get("description"),
        frequency=payload.get("frequency"),
        contraindications=payload.get("contraindications"),
        progression=payload.get("progression"),
        regression=payload.get("regression"),
        body_regions=payload.get("body_regions", []),
        target_conditions=payload.get("target_conditions", []),
    )


def prescription_export_payload(prescription, actions):
    action_items = action_response_items(actions)
    return {
        "id": prescription.id,
        "patient_profile_id": prescription.patient_profile_id,
        "patient_name": prescription.patient_name,
        "patient_age": prescription.patient_age,
        "symptoms": prescription.symptoms,
        "history": prescription.history,
        "summary": prescription.summary,
        "actions": action_items,
        "created_at": prescription.created_at.isoformat() if prescription.created_at else None,
        "updated_at": prescription.updated_at.isoformat() if prescription.updated_at else None,
    }


def render_prescription_export(payload: dict, export_format: str):
    if export_format == "json":
        return json.dumps(payload, ensure_ascii=False, indent=2), "application/json", "json"

    lines = [
        "# 康复处方",
        "",
        f"- 处方编号：{payload.get('id')}",
        f"- 患者姓名：{payload.get('patient_name') or '未填写'}",
        f"- 患者年龄：{payload.get('patient_age') if payload.get('patient_age') is not None else '未填写'}",
        f"- 主诉：{payload.get('symptoms') or '未填写'}",
        f"- 既往病史：{payload.get('history') or '无'}",
        f"- 生成时间：{payload.get('created_at') or '未知'}",
        "",
        "## 总体建议",
        "",
        payload.get("summary") or "暂无摘要",
        "",
        "## 训练动作",
        "",
    ]
    for index, action in enumerate(payload.get("actions") or [], start=1):
        lines.extend([
            f"{index}. {action.get('name') or '未命名动作'}",
            f"   - 组数：{action.get('sets')}",
            f"   - 次数：{action.get('reps')}",
            f"   - 频次：{action.get('frequency') or '按耐受频次'}",
            f"   - 说明：{action.get('description') or action.get('note') or '暂无'}",
            f"   - 禁忌：{action.get('contraindications') or '暂无'}",
            f"   - 进阶：{action.get('progression') or '暂无'}",
            f"   - 降阶：{action.get('regression') or '暂无'}",
            "",
        ])
    lines.extend([
        "## 安全提示",
        "",
        "本处方仅用于康复训练建议和课程项目演示，不能替代医生面诊。若出现剧烈疼痛、麻木无力、头晕或症状加重，应立即停止训练并及时就医。",
    ])

    text = "\n".join(lines)
    if export_format == "txt":
        text = re.sub(r"^#+\s*", "", text, flags=re.M)
        text = text.replace("   - ", "  - ")
        return text, "text/plain; charset=utf-8", "txt"
    return text, "text/markdown; charset=utf-8", "md"


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _resolve_user_from_token(authorization: str | None, db: Session):
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    try:
        payload = decode_access_token(token)
        user_id = int(payload.get("sub"))
    except (AuthError, TypeError, ValueError):
        return None

    return db.query(models.UserModel).filter_by(id=user_id).first()


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _resolve_user_from_token(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail="invalid or expired token")
    return user


def get_admin_user(current_user=Depends(get_current_user)):
    if not is_admin_account(current_user):
        raise HTTPException(status_code=403, detail="admin permission required")
    return current_user


def is_admin_account(user):
    admin_accounts = {
        account.strip().lower()
        for account in os.getenv("ADMIN_ACCOUNTS", "admin").split(",")
        if account.strip()
    }
    return getattr(user, "role", "user") == "admin" or user.account.lower() in admin_accounts


def get_optional_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    return _resolve_user_from_token(authorization, db)


@router.post("/register", response_model=UserResponse, status_code=201)
def register(req: UserCreateRequest, db: Session = Depends(get_db)):
    account = req.account.strip()
    password = req.password.strip()
    nickname = req.nickname.strip()

    if not account:
        raise HTTPException(status_code=400, detail="account required")
    if not password:
        raise HTTPException(status_code=400, detail="password required")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="password must be at least 6 characters")
    if not nickname:
        raise HTTPException(status_code=400, detail="nickname required")
    if req.age is not None and not 0 < req.age <= 120:
        raise HTTPException(status_code=400, detail="age must be between 1 and 120")
    if get_user_by_account(db, account):
        raise HTTPException(status_code=409, detail="account already exists")

    cleaned = UserCreateRequest(
        account=account,
        password=password,
        nickname=nickname,
        gender=req.gender.strip() if req.gender else None,
        age=req.age,
    )
    return create_user(db, cleaned)


@router.post("/login", response_model=LoginResponse)
def login(req: UserLoginRequest, db: Session = Depends(get_db)):
    result = authenticate_user(
        db,
        UserLoginRequest(
            account=req.account.strip(),
            password=req.password.strip(),
        ),
    )
    if not result:
        raise HTTPException(status_code=401, detail="invalid account or password")
    return LoginResponse(
        message="login success",
        token=create_access_token(user_id=result.id, account=result.account),
        user=UserResponse(
            id=result.id,
            account=result.account,
            nickname=result.nickname,
            role="admin" if is_admin_account(result) else result.role,
            gender=result.gender,
            age=result.age,
        ),
    )


@router.get("/patient_profiles", response_model=list[PatientProfileResponse])
def list_patient_profile_api(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    profiles = list_patient_profiles(db, user_id=current_user.id)
    return [patient_profile_response(profile) for profile in profiles]


@router.post("/patient_profiles", response_model=PatientProfileResponse, status_code=201)
def create_patient_profile_api(
    req: PatientProfileCreateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    cleaned = clean_patient_profile_payload(req)
    profile = create_patient_profile(
        db,
        PatientProfileCreateRequest(**cleaned),
        user_id=current_user.id,
    )
    return patient_profile_response(profile)


@router.get("/patient_profiles/{profile_id}", response_model=PatientProfileResponse)
def read_patient_profile_api(
    profile_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    profile = get_patient_profile(db, profile_id=profile_id, user_id=current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Patient profile not found")
    return patient_profile_response(profile)


@router.put("/patient_profiles/{profile_id}", response_model=PatientProfileResponse)
def update_patient_profile_api(
    profile_id: int,
    req: PatientProfileUpdateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    profile = get_patient_profile(db, profile_id=profile_id, user_id=current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Patient profile not found")
    cleaned = clean_patient_profile_payload(req, partial=True)
    if not cleaned:
        raise HTTPException(status_code=400, detail="no fields to update")
    profile = update_patient_profile(db, profile, PatientProfileUpdateRequest(**cleaned))
    return patient_profile_response(profile)


@router.delete("/patient_profiles/{profile_id}")
def delete_patient_profile_api(
    profile_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    profile = get_patient_profile(db, profile_id=profile_id, user_id=current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Patient profile not found")
    delete_patient_profile(db, profile)
    return {"message": "patient profile deleted"}


@router.get("/training_checkins", response_model=list[TrainingCheckinResponse])
def list_training_checkin_api(
    patient_profile_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if patient_profile_id is not None:
        validate_training_links(db, current_user.id, patient_profile_id, None)
    checkins = list_training_checkins(
        db,
        user_id=current_user.id,
        patient_profile_id=patient_profile_id,
        start_date=start_date,
        end_date=end_date,
    )
    return [training_checkin_response(checkin) for checkin in checkins]


@router.post("/training_checkins", response_model=TrainingCheckinResponse, status_code=201)
def create_training_checkin_api(
    req: TrainingCheckinCreateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    cleaned = clean_training_checkin_payload(req)
    cleaned = resolve_training_links(db, current_user.id, cleaned)
    checkin = create_training_checkin(
        db,
        TrainingCheckinCreateRequest(**cleaned),
        user_id=current_user.id,
    )
    return training_checkin_response(checkin)


@router.get("/training_checkins/trends", response_model=TrainingTrendResponse)
def read_training_trends_api(
    patient_profile_id: int | None = None,
    days: int = 14,
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    start_date, end_date = normalize_trend_dates(days, start_date, end_date)
    if patient_profile_id is not None:
        validate_training_links(db, current_user.id, patient_profile_id, None)
    points = build_training_trends(
        db,
        user_id=current_user.id,
        start_date=start_date,
        end_date=end_date,
        patient_profile_id=patient_profile_id,
    )
    return TrainingTrendResponse(
        start_date=start_date,
        end_date=end_date,
        points=[TrainingTrendPoint(**point) for point in points],
    )


@router.get("/training_checkins/visualization", response_model=TrainingVisualizationResponse)
def read_training_visualization_api(
    patient_profile_id: int | None = None,
    days: int = 30,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    start_date, end_date = normalize_trend_dates(days, None, None)
    if patient_profile_id is not None:
        validate_training_links(db, current_user.id, patient_profile_id, None)
    checkins = list_training_checkins(
        db,
        user_id=current_user.id,
        patient_profile_id=patient_profile_id,
        start_date=start_date,
        end_date=end_date,
    )
    points = build_training_trends(
        db,
        user_id=current_user.id,
        start_date=start_date,
        end_date=end_date,
        patient_profile_id=patient_profile_id,
    )
    pain_changes = [
        checkin.pain_after - checkin.pain_before
        for checkin in checkins
        if checkin.pain_before is not None and checkin.pain_after is not None
    ]
    scores = [checkin.score for checkin in checkins if checkin.score is not None]
    return TrainingVisualizationResponse(
        total_checkins=len(checkins),
        total_duration_minutes=sum(checkin.duration_minutes or 0 for checkin in checkins),
        active_days=len({checkin.trained_on for checkin in checkins}),
        avg_score=round(sum(scores) / len(scores), 1) if scores else None,
        avg_pain_change=round(sum(pain_changes) / len(pain_changes), 1) if pain_changes else None,
        trend=TrainingTrendResponse(
            start_date=start_date,
            end_date=end_date,
            points=[TrainingTrendPoint(**point) for point in points],
        ),
    )


@router.get("/training_checkins/{checkin_id}", response_model=TrainingCheckinResponse)
def read_training_checkin_api(
    checkin_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    checkin = get_training_checkin(db, checkin_id=checkin_id, user_id=current_user.id)
    if not checkin:
        raise HTTPException(status_code=404, detail="Training checkin not found")
    return training_checkin_response(checkin)


@router.put("/training_checkins/{checkin_id}", response_model=TrainingCheckinResponse)
def update_training_checkin_api(
    checkin_id: int,
    req: TrainingCheckinUpdateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    checkin = get_training_checkin(db, checkin_id=checkin_id, user_id=current_user.id)
    if not checkin:
        raise HTTPException(status_code=404, detail="Training checkin not found")
    cleaned = clean_training_checkin_payload(req, partial=True)
    if not cleaned:
        raise HTTPException(status_code=400, detail="no fields to update")
    cleaned = resolve_training_links(
        db,
        current_user.id,
        {
            "patient_profile_id": cleaned.get("patient_profile_id", checkin.patient_profile_id),
            "prescription_id": cleaned.get("prescription_id", checkin.prescription_id),
            **cleaned,
        },
    )
    checkin = update_training_checkin(db, checkin, TrainingCheckinUpdateRequest(**cleaned))
    return training_checkin_response(checkin)


@router.delete("/training_checkins/{checkin_id}")
def delete_training_checkin_api(
    checkin_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    checkin = get_training_checkin(db, checkin_id=checkin_id, user_id=current_user.id)
    if not checkin:
        raise HTTPException(status_code=404, detail="Training checkin not found")
    delete_training_checkin(db, checkin)
    return {"message": "training checkin deleted"}


@router.get("/admin/actions", response_model=list[ActionItem])
def admin_list_actions(
    q: str | None = None,
    body_region: str | None = None,
    condition: str | None = None,
    current_user=Depends(get_admin_user),
):
    from .knowledge import load_action_catalog

    actions = load_action_catalog()
    keyword = q.strip().lower() if q else None
    region = body_region.strip() if body_region else None
    target_condition = condition.strip() if condition else None

    if keyword:
        actions = [
            action for action in actions
            if keyword in " ".join([
                str(action.get("id") or ""),
                str(action.get("name") or ""),
                str(action.get("description") or ""),
                str(action.get("note") or ""),
                " ".join(action.get("body_regions") or []),
                " ".join(action.get("target_conditions") or []),
            ]).lower()
        ]
    if region:
        actions = [action for action in actions if region in (action.get("body_regions") or [])]
    if target_condition:
        actions = [action for action in actions if target_condition in (action.get("target_conditions") or [])]

    return [action_item_from_payload(action) for action in actions]


@router.get("/admin/actions/meta")
def admin_action_meta(current_user=Depends(get_admin_user)):
    from .knowledge import load_action_catalog

    actions = load_action_catalog()
    body_regions = sorted({
        region
        for action in actions
        for region in (action.get("body_regions") or [])
    })
    target_conditions = sorted({
        condition
        for action in actions
        for condition in (action.get("target_conditions") or [])
    })
    return {
        "total": len(actions),
        "body_regions": body_regions,
        "target_conditions": target_conditions,
    }


@router.post("/admin/actions", response_model=ActionItem, status_code=201)
def admin_create_action(req: ActionItem, current_user=Depends(get_admin_user)):
    from .knowledge import create_action_payload

    payload = clean_action_payload(req)
    try:
        action = create_action_payload(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return action_item_from_payload(action)


@router.get("/admin/actions/{action_id}", response_model=ActionItem)
def admin_read_action(action_id: str, current_user=Depends(get_admin_user)):
    from .knowledge import get_action_payload

    action = get_action_payload(action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    return action_item_from_payload(action)


@router.put("/admin/actions/{action_id}", response_model=ActionItem)
def admin_update_action(action_id: str, req: ActionUpdateRequest, current_user=Depends(get_admin_user)):
    from .knowledge import update_action_payload

    payload = clean_action_payload(req, partial=True)
    if not payload:
        raise HTTPException(status_code=400, detail="no fields to update")
    try:
        action = update_action_payload(action_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    return action_item_from_payload(action)


@router.delete("/admin/actions/{action_id}")
def admin_delete_action(action_id: str, current_user=Depends(get_admin_user)):
    from .knowledge import delete_action_payload

    deleted = delete_action_payload(action_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Action not found")
    return {"message": "action deleted"}


@router.get("/admin/test_report")
def admin_test_report(current_user=Depends(get_admin_user)):
    from .test_reports import load_latest_report

    report = load_latest_report()
    if not report:
        raise HTTPException(status_code=404, detail="No test report found. Run backend/run_backend_tests.py first.")
    return report


@router.get("/deployment/info")
def deployment_info():
    from .database import check_database
    from .doubao import DOUBAO_BASE_URL, DOUBAO_MODEL_ID

    return {
        "app": "康健图谱 API",
        "environment": os.getenv("APP_ENV", "development"),
        "demo_mode": os.getenv("DEMO_MODE", "false").lower() == "true",
        "database": "ok" if check_database() else "error",
        "cors_origins_configured": bool(os.getenv("CORS_ORIGINS")),
        "doubao_base_url": DOUBAO_BASE_URL,
        "doubao_model_configured": bool(DOUBAO_MODEL_ID),
        "doubao_api_key_configured": bool(os.getenv("DOUBAO_API_KEY")),
        "admin_accounts_configured": bool(os.getenv("ADMIN_ACCOUNTS")),
    }


@router.post("/generate_prescription", response_model=PrescriptionResponse)
def generate_prescription(
    req: PrescriptionRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_optional_user),
):
    from .validators import validate_pain_regions, validate_symptoms

    if not req.symptoms:
        raise HTTPException(status_code=400, detail="symptoms required")

    patient_name = req.name
    patient_age = req.age
    patient_history = req.history
    pain_regions = req.pain_regions
    patient_profile_id = None
    if req.patient_profile_id is not None:
        if not current_user:
            raise HTTPException(status_code=401, detail="login required to use patient profile")
        profile = get_patient_profile(db, profile_id=req.patient_profile_id, user_id=current_user.id)
        if not profile:
            raise HTTPException(status_code=404, detail="Patient profile not found")
        patient_profile_id = profile.id
        patient_name = patient_name or profile.name
        patient_age = patient_age if patient_age is not None else profile.age
        patient_history = patient_history or profile.history
        pain_regions = pain_regions or profile.pain_regions
    if current_user:
        patient_name = patient_name or current_user.nickname
        patient_age = patient_age if patient_age is not None else current_user.age

    pain_region_error = validate_pain_regions(pain_regions)
    if pain_region_error:
        raise HTTPException(status_code=400, detail=pain_region_error)
    symptom_error = validate_symptoms(req.symptoms, pain_regions)
    if symptom_error:
        raise HTTPException(status_code=400, detail=symptom_error)

    req = PrescriptionRequest(
        patient_profile_id=patient_profile_id,
        name=patient_name,
        age=patient_age,
        symptoms=req.symptoms,
        history=patient_history,
        pain_regions=pain_regions,
        mobility_score=req.mobility_score,
    )
    prescription = create_prescription(
        db,
        req,
        user_id=current_user.id if current_user else None,
        patient_profile_id=patient_profile_id,
    )
    actions = get_actions_by_prescription(db, prescription.id)
    return PrescriptionResponse(
        id=prescription.id,
        patient_profile_id=prescription.patient_profile_id,
        patient_name=prescription.patient_name,
        patient_age=prescription.patient_age,
        summary=prescription.summary,
        actions=action_response_items(actions),
        raw_response=prescription.raw_response,
    )


@router.get("/prescriptions/{prescription_id}/export")
def export_prescription(
    prescription_id: int,
    format: str = "md",
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    export_format = format.lower()
    if export_format not in {"md", "txt", "json"}:
        raise HTTPException(status_code=400, detail="format must be one of: md, txt, json")

    prescription = get_prescription(db, prescription_id, user_id=current_user.id)
    if not prescription:
        raise HTTPException(status_code=404, detail="Prescription not found")
    actions = get_actions_by_prescription(db, prescription.id)
    payload = prescription_export_payload(prescription, actions)
    content, media_type, extension = render_prescription_export(payload, export_format)
    filename = f"prescription_{prescription.id}.{extension}"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/prescriptions/{prescription_id}", response_model=PrescriptionResponse)
def read_prescription(
    prescription_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    prescription = get_prescription(db, prescription_id, user_id=current_user.id)
    if not prescription:
        raise HTTPException(status_code=404, detail="Prescription not found")
    actions = get_actions_by_prescription(db, prescription.id)
    return PrescriptionResponse(
        id=prescription.id,
        patient_profile_id=prescription.patient_profile_id,
        patient_name=prescription.patient_name,
        patient_age=prescription.patient_age,
        summary=prescription.summary,
        actions=action_response_items(actions),
        raw_response=prescription.raw_response,
    )


@router.post("/correct_pose", response_model=PoseCorrectionResponse)
def correct_pose(req: PoseCorrectionRequest, db: Session = Depends(get_db)):
    result = create_pose_feedback(db, req)
    return PoseCorrectionResponse(
        feedback=result["feedback"],
        score=result.get("score"),
        status=result.get("status"),
    )


@router.get("/prescriptions", response_model=list[PrescriptionResponse])
def list_prescriptions(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    prescriptions = crud_list_prescriptions(db, user_id=current_user.id)
    result = []
    for prescription in prescriptions:
        actions = get_actions_by_prescription(db, prescription.id)
        result.append(PrescriptionResponse(
            id=prescription.id,
            patient_profile_id=prescription.patient_profile_id,
            patient_name=prescription.patient_name,
            patient_age=prescription.patient_age,
            summary=prescription.summary,
            actions=action_response_items(actions),
            raw_response=prescription.raw_response,
        ))
    return result


@router.get("/actions", response_model=list[ActionItem])
def list_actions():
    from .knowledge import load_action_library
    return load_action_library()


@router.post("/test_doubao")
def test_doubao():
    """Test Doubao API connection."""
    from .doubao import generate_prescription_summary, DoubaoError
    try:
        result = generate_prescription_summary(
            patient_name="测试患者",
            age=30,
            symptoms="腰痛",
            history="无",
            actions=[
                {"id": "mckenzie_press_up", "name": "麦肯基俯卧撑", "sets": 3, "reps": 10},
                {"id": "glute_bridge", "name": "臀桥训练", "sets": 3, "reps": 12},
            ],
            pain_regions=["腰部"],
            mobility_score=5,
        )
        return {"status": "success", "summary": result}
    except DoubaoError as exc:
        return {"status": "error", "detail": str(exc)}
