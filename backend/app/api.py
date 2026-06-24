from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy.orm import Session
from fastapi import WebSocket, WebSocketDisconnect
from datetime import date, datetime, timedelta
from pathlib import Path
import base64
import binascii
import hashlib
import re
import os
import json
from .auth import AuthError, create_access_token, decode_access_token
from . import models
from .crud import (
    authenticate_user,
    build_training_trends,
    create_patient_profile,
    create_imaging_report,
    create_prescription,
    create_pose_feedback,
    create_training_checkin,
    create_user,
    delete_patient_profile,
    delete_training_checkin,
    get_actions_by_prescription,
    get_imaging_report,
    get_patient_profile,
    get_prescription,
    get_training_checkin,
    get_user_by_account,
    list_imaging_reports,
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
    AdminDashboardResponse,
    AdminUserSummary,
    AROverlayRequest,
    AROverlayResponse,
    DoctorPatientLinkCreateRequest,
    DoctorPatientLinkResponse,
    FeedbackCreateRequest,
    FeedbackResponse,
    FeedbackUpdateRequest,
    ImagingReportCreateRequest,
    ImagingReportResponse,
    KnowledgeArticleListResponse,
    KnowledgeQARequest,
    KnowledgeQAResponse,
    LoginResponse,
    PatientProfileCreateRequest,
    PatientProfileResponse,
    PatientProfileUpdateRequest,
    PoseBatchRequest,
    PoseBatchResponse,
    PoseCorrectionRequest,
    PoseCorrectionResponse,
    PoseFrameRequest,
    PoseFrameResponse,
    PoseStreamSessionResponse,
    PrescriptionAdjustmentCreateRequest,
    PrescriptionAdjustmentDecisionRequest,
    PrescriptionAdjustmentResponse,
    PrescriptionRequest,
    PrescriptionResponse,
    PrescriptionReviewResponse,
    PrescriptionReviewShareRequest,
    PrescriptionReviewUpdateRequest,
    RAGSearchRequest,
    RAGSearchResponse,
    SkeletonFrameRequest,
    SkeletonFrameResponse,
    TrainingCheckinCreateRequest,
    TrainingCheckinResponse,
    TrainingCheckinUpdateRequest,
    TrainingReportActionSummary,
    TrainingReportResponse,
    TrainingTrendPoint,
    TrainingTrendResponse,
    TrainingVisualizationResponse,
    UserCreateRequest,
    UserLoginRequest,
    UserResponse,
    FatigueStatusResponse,
    VoiceCueRequest,
    VoiceCueResponse,
    WearableMetricCreateRequest,
    WearableMetricResponse,
    WebRTCOfferRequest,
    WebRTCOfferResponse,
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
        completed_sets=checkin.completed_sets,
        completed_reps=checkin.completed_reps,
        pain_before=checkin.pain_before,
        pain_after=checkin.pain_after,
        difficulty=checkin.difficulty,
        score=checkin.score,
        note=checkin.note,
    )


def imaging_report_response(report):
    return ImagingReportResponse(
        id=report.id,
        user_id=report.user_id,
        patient_profile_id=report.patient_profile_id,
        report_type=report.report_type,
        file_name=report.file_name,
        file_path=report.file_path,
        ocr_text=report.ocr_text,
        ocr_status=report.ocr_status,
        risk_level=report.risk_level,
        red_flags=report.red_flags,
        note=report.note,
        created_at=report.created_at,
    )


def save_imaging_report_file(user_id: int, file_name: str | None, file_content_base64: str | None) -> str | None:
    if not file_content_base64:
        return None
    if not file_name:
        raise HTTPException(status_code=400, detail="file_name required when file_content_base64 is provided")

    try:
        content = base64.b64decode(file_content_base64, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=400, detail="file_content_base64 is invalid")
    if not content:
        raise HTTPException(status_code=400, detail="uploaded file is empty")
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="uploaded file must be <= 5MB")

    safe_name = Path(file_name).name
    extension = Path(safe_name).suffix.lower()
    allowed_extensions = {".png", ".jpg", ".jpeg", ".pdf", ".txt"}
    if extension not in allowed_extensions:
        raise HTTPException(status_code=400, detail="only png, jpg, jpeg, pdf, txt reports are supported")

    digest = hashlib.sha256(content).hexdigest()[:16]
    content_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".pdf": "application/pdf",
        ".txt": "text/plain; charset=utf-8",
    }
    object_name = f"imaging_reports/{user_id}/{digest}{extension}"
    from .object_storage import save_object

    return save_object(content, object_name, content_types.get(extension, "application/octet-stream"))


def extract_text_report_content(file_name: str | None, file_content_base64: str | None) -> str | None:
    if not file_name or not file_content_base64:
        return None
    if Path(file_name).suffix.lower() != ".txt":
        return None
    try:
        content = base64.b64decode(file_content_base64, validate=True)
    except (binascii.Error, ValueError):
        return None
    text = content.decode("utf-8", errors="ignore").strip()
    return text or None


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
    allowed_difficulties = {"初级", "中级", "高级"}
    allowed_risks = {"低", "中", "高"}
    difficulty_level = raw_data.get("difficulty_level")
    risk_level = raw_data.get("risk_level")
    if difficulty_level is not None and difficulty_level not in allowed_difficulties:
        raise HTTPException(status_code=400, detail="difficulty_level must be 初级, 中级 or 高级")
    if risk_level is not None and risk_level not in allowed_risks:
        raise HTTPException(status_code=400, detail="risk_level must be 低, 中 or 高")

    cleaned = {
        "id": action_id,
        "name": name,
        "target_conditions": raw_data.get("target_conditions") or [],
        "body_regions": raw_data.get("body_regions") or [],
        "sets": raw_data.get("sets"),
        "reps": raw_data.get("reps"),
        "category": raw_data.get("category").strip() if raw_data.get("category") else None,
        "difficulty_level": difficulty_level,
        "stage": raw_data.get("stage").strip() if raw_data.get("stage") else None,
        "target_muscles": raw_data.get("target_muscles") or [],
        "equipment": raw_data.get("equipment") or [],
        "demo_media": raw_data.get("demo_media"),
        "image": raw_data.get("image").strip() if raw_data.get("image") else None,
        "video_url": raw_data.get("video_url").strip() if raw_data.get("video_url") else None,
        "video_hint": raw_data.get("video_hint").strip() if raw_data.get("video_hint") else None,
        "image_hint": raw_data.get("image_hint").strip() if raw_data.get("image_hint") else None,
        "steps": raw_data.get("steps") or [],
        "common_mistakes": raw_data.get("common_mistakes") or [],
        "correct_cues": raw_data.get("correct_cues") or [],
        "risk_level": risk_level,
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
    from .action_metadata import enrich_action_payload

    payload = enrich_action_payload(payload)
    return ActionItem(
        id=payload.get("id"),
        name=payload.get("name"),
        sets=payload.get("sets", 1),
        reps=payload.get("reps", 1),
        category=payload.get("category"),
        difficulty_level=payload.get("difficulty_level"),
        stage=payload.get("stage"),
        target_muscles=payload.get("target_muscles"),
        equipment=payload.get("equipment"),
        demo_media=payload.get("demo_media"),
        image=payload.get("image"),
        video_url=payload.get("video_url"),
        video_hint=payload.get("video_hint"),
        image_hint=payload.get("image_hint"),
        steps=payload.get("steps"),
        common_mistakes=payload.get("common_mistakes"),
        correct_cues=payload.get("correct_cues"),
        risk_level=payload.get("risk_level"),
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


def get_doctor_user(current_user=Depends(get_current_user)):
    if current_user.role not in {"doctor", "admin"}:
        raise HTTPException(status_code=403, detail="doctor permission required")
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


def clean_feedback_payload(req: FeedbackCreateRequest):
    category = (req.category or "general").strip() or "general"
    content = req.content.strip() if req.content else ""
    if not content:
        raise HTTPException(status_code=400, detail="feedback content required")
    if len(content) > 2000:
        raise HTTPException(status_code=400, detail="feedback content too long")
    if req.rating is not None and not 1 <= req.rating <= 5:
        raise HTTPException(status_code=400, detail="rating must be between 1 and 5")
    return {
        "category": category[:64],
        "rating": req.rating,
        "content": content,
        "contact": req.contact.strip()[:128] if req.contact else None,
        "source": req.source.strip()[:64] if req.source else None,
    }


def clean_feedback_update(req: FeedbackUpdateRequest):
    data = req.model_dump(exclude_unset=True) if hasattr(req, "model_dump") else req.dict(exclude_unset=True)
    allowed_status = {"open", "processing", "resolved", "closed"}
    if "status" in data and data["status"] is not None:
        data["status"] = data["status"].strip()
        if data["status"] not in allowed_status:
            raise HTTPException(status_code=400, detail="status must be one of: open, processing, resolved, closed")
    if "admin_note" in data and data["admin_note"] is not None:
        data["admin_note"] = data["admin_note"].strip()
    return data


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


@router.get("/imaging_reports", response_model=list[ImagingReportResponse])
def list_imaging_report_api(
    patient_profile_id: int | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if patient_profile_id is not None:
        profile = get_patient_profile(db, profile_id=patient_profile_id, user_id=current_user.id)
        if not profile:
            raise HTTPException(status_code=404, detail="Patient profile not found")
    reports = list_imaging_reports(db, user_id=current_user.id, patient_profile_id=patient_profile_id)
    return [imaging_report_response(report) for report in reports]


@router.post("/imaging_reports", response_model=ImagingReportResponse, status_code=201)
def create_imaging_report_api(
    req: ImagingReportCreateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from .validators import detect_red_flags

    if req.patient_profile_id is not None:
        profile = get_patient_profile(db, profile_id=req.patient_profile_id, user_id=current_user.id)
        if not profile:
            raise HTTPException(status_code=404, detail="Patient profile not found")
    if not req.file_content_base64 and not req.ocr_text:
        raise HTTPException(status_code=400, detail="file_content_base64 or ocr_text required")

    report_type = req.report_type.strip() if req.report_type else "影像报告"
    file_name = Path(req.file_name).name if req.file_name else None
    ocr_text = req.ocr_text.strip() if req.ocr_text else None
    extracted_text = None if ocr_text else extract_text_report_content(file_name, req.file_content_base64)
    ocr_text = ocr_text or extracted_text

    file_path = save_imaging_report_file(current_user.id, file_name, req.file_content_base64)
    red_flags = detect_red_flags(ocr_text or "")
    risk_level = "high" if red_flags else ("low" if ocr_text else "unknown")
    if req.ocr_text:
        ocr_status = "provided"
    elif extracted_text:
        ocr_status = "text_file_extracted"
    else:
        ocr_status = "pending_external_ocr"

    cleaned = ImagingReportCreateRequest(
        patient_profile_id=req.patient_profile_id,
        report_type=report_type,
        file_name=file_name,
        ocr_text=ocr_text,
        note=req.note.strip() if req.note else None,
    )
    report = create_imaging_report(
        db,
        cleaned,
        user_id=current_user.id,
        file_path=file_path,
        ocr_status=ocr_status,
        risk_level=risk_level,
        red_flags=red_flags,
    )
    return imaging_report_response(report)


@router.get("/imaging_reports/{report_id}", response_model=ImagingReportResponse)
def read_imaging_report_api(
    report_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    report = get_imaging_report(db, report_id=report_id, user_id=current_user.id)
    if not report:
        raise HTTPException(status_code=404, detail="Imaging report not found")
    return imaging_report_response(report)


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
        active_days=len({checkin.trained_on for checkin in checkins}),
        avg_score=round(sum(scores) / len(scores), 1) if scores else None,
        avg_pain_change=round(sum(pain_changes) / len(pain_changes), 1) if pain_changes else None,
        trend=TrainingTrendResponse(
            start_date=start_date,
            end_date=end_date,
            points=[TrainingTrendPoint(**point) for point in points],
        ),
    )


@router.get("/training_checkins/report", response_model=TrainingReportResponse)
def read_training_report_api(
    patient_profile_id: int | None = None,
    period: str = "weekly",
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from .progress_reports import build_training_report, normalize_report_dates

    try:
        period, start_date, end_date = normalize_report_dates(period, start_date, end_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if patient_profile_id is not None:
        validate_training_links(db, current_user.id, patient_profile_id, None)
    report = build_training_report(
        db,
        user_id=current_user.id,
        period=period,
        start_date=start_date,
        end_date=end_date,
        patient_profile_id=patient_profile_id,
    )
    return TrainingReportResponse(**report)


@router.get("/training_checkins/report/export")
def export_training_report_api(
    patient_profile_id: int | None = None,
    period: str = "weekly",
    start_date: date | None = None,
    end_date: date | None = None,
    format: str = "md",
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from .progress_reports import build_training_report, normalize_report_dates, render_training_report_markdown

    export_format = format.lower()
    if export_format not in {"md", "txt", "json"}:
        raise HTTPException(status_code=400, detail="format must be one of: md, txt, json")
    try:
        period, start_date, end_date = normalize_report_dates(period, start_date, end_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if patient_profile_id is not None:
        validate_training_links(db, current_user.id, patient_profile_id, None)
    report = build_training_report(
        db,
        user_id=current_user.id,
        period=period,
        start_date=start_date,
        end_date=end_date,
        patient_profile_id=patient_profile_id,
    )
    if export_format == "json":
        content = json.dumps(report, ensure_ascii=False, indent=2, default=str)
        media_type = "application/json; charset=utf-8"
        extension = "json"
    else:
        content = render_training_report_markdown(report)
        media_type = "text/markdown; charset=utf-8" if export_format == "md" else "text/plain; charset=utf-8"
        extension = export_format
    filename = f"training_report_{period}_{start_date}_{end_date}.{extension}"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
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


@router.post("/feedback", response_model=FeedbackResponse, status_code=201)
def submit_feedback(
    req: FeedbackCreateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_optional_user),
):
    from .admin_management import create_feedback, feedback_response

    payload = clean_feedback_payload(req)
    feedback = create_feedback(
        db,
        user_id=current_user.id if current_user else None,
        **payload,
    )
    return FeedbackResponse(**feedback_response(feedback))


@router.get("/admin/dashboard", response_model=AdminDashboardResponse)
def admin_dashboard(
    db: Session = Depends(get_db),
    current_user=Depends(get_admin_user),
):
    from .admin_management import build_admin_dashboard

    return AdminDashboardResponse(**build_admin_dashboard(db))


@router.get("/admin/users", response_model=list[AdminUserSummary])
def admin_list_users(
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user=Depends(get_admin_user),
):
    from .admin_management import list_admin_users

    return [AdminUserSummary(**item) for item in list_admin_users(db, q=q, limit=limit, offset=offset)]


@router.get("/admin/feedback", response_model=list[FeedbackResponse])
def admin_list_feedback(
    status: str | None = None,
    category: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user=Depends(get_admin_user),
):
    from .admin_management import feedback_response, list_feedback

    items = list_feedback(db, status=status, category=category, limit=limit, offset=offset)
    return [FeedbackResponse(**feedback_response(item)) for item in items]


@router.put("/admin/feedback/{feedback_id}", response_model=FeedbackResponse)
def admin_update_feedback(
    feedback_id: int,
    req: FeedbackUpdateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_admin_user),
):
    from .admin_management import feedback_response

    feedback = db.query(models.UserFeedbackModel).filter(models.UserFeedbackModel.id == feedback_id).first()
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")
    updates = clean_feedback_update(req)
    if not updates:
        raise HTTPException(status_code=400, detail="no fields to update")
    for field, value in updates.items():
        setattr(feedback, field, value)
    db.commit()
    db.refresh(feedback)
    return FeedbackResponse(**feedback_response(feedback))


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
    from .action_metadata import enrich_action_payload

    actions = [enrich_action_payload(action) for action in load_action_catalog()]
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
    categories = sorted({action.get("category") for action in actions if action.get("category")})
    difficulty_levels = sorted({action.get("difficulty_level") for action in actions if action.get("difficulty_level")})
    risk_levels = sorted({action.get("risk_level") for action in actions if action.get("risk_level")})
    return {
        "total": len(actions),
        "body_regions": body_regions,
        "target_conditions": target_conditions,
        "categories": categories,
        "difficulty_levels": difficulty_levels,
        "risk_levels": risk_levels,
    }


@router.post("/admin/actions", response_model=ActionItem, status_code=201)
def admin_create_action(req: ActionItem, current_user=Depends(get_admin_user)):
    from .knowledge import create_action_payload

    payload = clean_action_payload(req)
    try:
        action = create_action_payload(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    from .cache import cache_delete

    cache_delete("actions:v1")
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
    from .cache import cache_delete

    cache_delete("actions:v1")
    return action_item_from_payload(action)


@router.delete("/admin/actions/{action_id}")
def admin_delete_action(action_id: str, current_user=Depends(get_admin_user)):
    from .knowledge import delete_action_payload

    deleted = delete_action_payload(action_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Action not found")
    from .cache import cache_delete

    cache_delete("actions:v1")
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
    from .cache import check_redis
    from .database import check_database, database_backend
    from .doubao import DeepSeek_BASE_URL, DeepSeek_MODEL_ID
    from .object_storage import check_object_storage

    return {
        "app": "康健图谱 API",
        "environment": os.getenv("APP_ENV", "development"),
        "demo_mode": os.getenv("DEMO_MODE", "false").lower() == "true",
        "database": "ok" if check_database() else "error",
        "database_backend": database_backend(),
        "redis": check_redis(),
        "object_storage": check_object_storage(),
        "cors_origins_configured": bool(os.getenv("CORS_ORIGINS")),
        "deepseek_base_url": DeepSeek_BASE_URL,
        "deepseek_model_configured": bool(DeepSeek_MODEL_ID),
        "deepseek_api_key_configured": bool(os.getenv("DEEPSEEK_API_KEY") or os.getenv("DeepSeek_API_KEY")),
        "admin_accounts_configured": bool(os.getenv("ADMIN_ACCOUNTS")),
    }


@router.post("/generate_prescription", response_model=PrescriptionResponse)
def generate_prescription(
    req: PrescriptionRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_optional_user),
):
    from .validators import detect_red_flags, red_flag_error_message, validate_pain_regions, validate_symptoms

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

    red_flags = detect_red_flags(req.symptoms, patient_history)
    if red_flags:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "red_flag_detected",
                "message": red_flag_error_message(red_flags),
                "red_flags": red_flags,
            },
        )

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
    from .voice_feedback import build_voice_cue

    result = create_pose_feedback(db, req)
    return PoseCorrectionResponse(
        feedback=result["feedback"],
        score=result.get("score"),
        status=result.get("status"),
        voice_cue=build_voice_cue(
            result.get("feedback", []),
            status=result.get("status"),
            score=result.get("score"),
        ),
    )


def wearable_metric_response(metric):
    from .fatigue import metric_to_dict

    return WearableMetricResponse(**metric_to_dict(metric))


def _pose_frame_from_request(req: PoseFrameRequest):
    from .pose_runtime import PoseFrame
    import uuid

    return PoseFrame(
        action_id=req.action_id,
        frame_id=req.frame_id or str(uuid.uuid4()),
        timestamp=req.timestamp,
        image_base64=req.image_base64,
        keypoints=req.keypoints,
        visibility=req.visibility,
    )


@router.get("/pose/status")
def pose_status(current_user=Depends(get_current_user)):
    from .pose_runtime import pose_runtime_status

    return pose_runtime_status()


@router.post("/pose/stream/session", response_model=PoseStreamSessionResponse)
def create_pose_stream_session(current_user=Depends(get_current_user)):
    from .pose_runtime import stream_manager

    session = stream_manager.create_session()
    return PoseStreamSessionResponse(
        session_id=session.session_id,
        processed_frames=session.processed_frames,
        dropped_frames=session.dropped_frames,
        last_latency_ms=session.last_latency_ms,
    )


@router.delete("/pose/stream/session/{session_id}")
def close_pose_stream_session(session_id: str, current_user=Depends(get_current_user)):
    from .pose_runtime import stream_manager

    stream_manager.close_session(session_id)
    return {"message": "pose stream session closed"}


@router.post("/pose/infer_frame", response_model=PoseFrameResponse)
async def infer_pose_frame(req: PoseFrameRequest, current_user=Depends(get_current_user)):
    from .pose_runtime import stream_manager

    if not req.action_id:
        raise HTTPException(status_code=400, detail="action_id required")
    if not req.keypoints and not req.image_base64:
        raise HTTPException(status_code=400, detail="keypoints or image_base64 required")
    try:
        result = await stream_manager.process_frame(_pose_frame_from_request(req))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return PoseFrameResponse(**result)


@router.post("/pose/infer_batch", response_model=PoseBatchResponse)
async def infer_pose_batch(req: PoseBatchRequest, current_user=Depends(get_current_user)):
    from .pose_runtime import stream_manager

    if not req.frames:
        raise HTTPException(status_code=400, detail="frames required")
    if len(req.frames) > 30:
        raise HTTPException(status_code=400, detail="batch size cannot exceed 30")
    session = stream_manager.get_session(req.session_id)
    try:
        batch = await stream_manager.process_batch(
            [_pose_frame_from_request(frame) for frame in req.frames],
            session=session,
            max_concurrency=req.max_concurrency or 2,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return PoseBatchResponse(session_id=session.session_id, **batch)


@router.websocket("/pose/ws")
async def pose_stream_websocket(websocket: WebSocket):
    from .pose_runtime import PoseFrame, stream_manager

    await websocket.accept()
    session = stream_manager.create_session()
    await websocket.send_json({"type": "session", "session_id": session.session_id})
    try:
        while True:
            payload = await websocket.receive_json()
            if payload.get("type") == "close":
                await websocket.send_json({"type": "closed", "session_id": session.session_id})
                break
            frame = PoseFrame(
                action_id=payload.get("action_id") or "",
                frame_id=payload.get("frame_id") or str(session.processed_frames + 1),
                timestamp=payload.get("timestamp"),
                image_base64=payload.get("image_base64"),
                keypoints=payload.get("keypoints"),
                visibility=payload.get("visibility"),
            )
            try:
                result = await stream_manager.process_frame(frame, session=session)
                await websocket.send_json({"type": "feedback", "session_id": session.session_id, **result})
            except Exception as exc:
                session.dropped_frames += 1
                await websocket.send_json({"type": "error", "session_id": session.session_id, "detail": str(exc)})
    except WebSocketDisconnect:
        pass
    finally:
        stream_manager.close_session(session.session_id)


@router.post("/pose/webrtc/offer", response_model=WebRTCOfferResponse)
async def pose_webrtc_offer(req: WebRTCOfferRequest, current_user=Depends(get_current_user)):
    try:
        from aiortc import RTCPeerConnection, RTCSessionDescription
    except Exception:
        return WebRTCOfferResponse(
            status="unavailable",
            detail="aiortc is not installed. Install backend requirements and use WebSocket /api/pose/ws as fallback.",
        )

    peer = RTCPeerConnection()
    offer = RTCSessionDescription(sdp=req.sdp, type=req.type)
    await peer.setRemoteDescription(offer)
    answer = await peer.createAnswer()
    await peer.setLocalDescription(answer)
    return WebRTCOfferResponse(
        sdp=peer.localDescription.sdp,
        type=peer.localDescription.type,
        status="ready",
    )


@router.get("/visual/skeleton/spec")
def visual_skeleton_spec(current_user=Depends(get_current_user)):
    from .spatial import skeleton_spec

    return skeleton_spec()


@router.post("/visual/skeleton/frame", response_model=SkeletonFrameResponse)
def visual_skeleton_frame(req: SkeletonFrameRequest, current_user=Depends(get_current_user)):
    from .spatial import build_skeleton_frame

    if not req.keypoints:
        raise HTTPException(status_code=400, detail="keypoints required")
    return SkeletonFrameResponse(
        skeleton_3d=build_skeleton_frame(
            req.keypoints,
            req.visibility,
            action_id=req.action_id,
        )
    )


@router.post("/visual/ar/overlay", response_model=AROverlayResponse)
def visual_ar_overlay(req: AROverlayRequest, current_user=Depends(get_current_user)):
    from .spatial import build_ar_overlay

    if not req.keypoints:
        raise HTTPException(status_code=400, detail="keypoints required")
    if req.viewport_width is not None and not 120 <= req.viewport_width <= 7680:
        raise HTTPException(status_code=400, detail="viewport_width must be between 120 and 7680")
    if req.viewport_height is not None and not 120 <= req.viewport_height <= 7680:
        raise HTTPException(status_code=400, detail="viewport_height must be between 120 and 7680")
    return AROverlayResponse(
        ar_overlay=build_ar_overlay(
            req.action_id,
            req.keypoints,
            visibility=req.visibility,
            feedback=req.feedback,
            status=req.status,
            score=req.score,
            viewport_width=req.viewport_width,
            viewport_height=req.viewport_height,
            mirror=bool(req.mirror),
        )
    )


@router.post("/voice/cue", response_model=VoiceCueResponse)
def create_voice_cue(req: VoiceCueRequest, current_user=Depends(get_current_user)):
    from .voice_feedback import DEFAULT_VOICE, build_voice_cue

    feedback = req.feedback if req.feedback is not None else req.text
    cue = build_voice_cue(
        feedback,
        status=req.status,
        score=req.score,
        enabled=req.enabled if req.enabled is not None else True,
        voice=req.voice or DEFAULT_VOICE,
    )
    return VoiceCueResponse(**cue)


def _validate_wearable_payload(req: WearableMetricCreateRequest):
    ranges = {
        "heart_rate": (30, 220),
        "resting_heart_rate": (30, 120),
        "hrv_ms": (1, 250),
        "spo2": (70, 100),
        "steps": (0, 100000),
        "calories": (0, 10000),
        "perceived_exertion": (1, 10),
        "duration_minutes": (0, 600),
    }
    data = req.model_dump() if hasattr(req, "model_dump") else req.dict()
    for field, (min_value, max_value) in ranges.items():
        value = data.get(field)
        if value is not None and not min_value <= value <= max_value:
            raise HTTPException(status_code=400, detail=f"{field} must be between {min_value} and {max_value}")
    if req.skin_temperature_c is not None and not 30 <= req.skin_temperature_c <= 43:
        raise HTTPException(status_code=400, detail="skin_temperature_c must be between 30 and 43")


@router.post("/wearables/metrics", response_model=WearableMetricResponse, status_code=201)
def create_wearable_metric(
    req: WearableMetricCreateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from .fatigue import evaluate_fatigue

    _validate_wearable_payload(req)
    if req.patient_profile_id is not None:
        validate_training_links(db, current_user.id, req.patient_profile_id, None)
    if req.training_checkin_id is not None:
        checkin = get_training_checkin(db, checkin_id=req.training_checkin_id, user_id=current_user.id)
        if not checkin:
            raise HTTPException(status_code=404, detail="Training checkin not found")

    previous = (
        db.query(models.WearableMetricModel)
        .filter(models.WearableMetricModel.user_id == current_user.id)
        .order_by(models.WearableMetricModel.recorded_at.desc())
        .limit(20)
        .all()
    )
    evaluation = evaluate_fatigue(
        heart_rate=req.heart_rate,
        resting_heart_rate=req.resting_heart_rate,
        hrv_ms=req.hrv_ms,
        spo2=req.spo2,
        perceived_exertion=req.perceived_exertion,
        duration_minutes=req.duration_minutes,
        previous_metrics=previous,
    )
    metric = models.WearableMetricModel(
        user_id=current_user.id,
        patient_profile_id=req.patient_profile_id,
        training_checkin_id=req.training_checkin_id,
        device_type=req.device_type,
        heart_rate=req.heart_rate,
        resting_heart_rate=req.resting_heart_rate,
        hrv_ms=req.hrv_ms,
        spo2=req.spo2,
        steps=req.steps,
        calories=req.calories,
        skin_temperature_c=req.skin_temperature_c,
        perceived_exertion=req.perceived_exertion,
        duration_minutes=req.duration_minutes,
        fatigue_score=evaluation["fatigue_score"],
        risk_level=evaluation["risk_level"],
        signals=evaluation["signals"],
        recommendation=evaluation["recommendation"],
        recorded_at=req.recorded_at or datetime.utcnow(),
    )
    db.add(metric)
    db.commit()
    db.refresh(metric)
    return wearable_metric_response(metric)


@router.get("/wearables/metrics", response_model=list[WearableMetricResponse])
def list_wearable_metrics(
    patient_profile_id: int | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 200")
    if patient_profile_id is not None:
        validate_training_links(db, current_user.id, patient_profile_id, None)
    query = db.query(models.WearableMetricModel).filter(models.WearableMetricModel.user_id == current_user.id)
    if patient_profile_id is not None:
        query = query.filter(models.WearableMetricModel.patient_profile_id == patient_profile_id)
    metrics = query.order_by(models.WearableMetricModel.recorded_at.desc()).limit(limit).all()
    return [wearable_metric_response(metric) for metric in metrics]


@router.get("/wearables/fatigue/status", response_model=FatigueStatusResponse)
def read_fatigue_status(
    patient_profile_id: int | None = None,
    window_minutes: int = 30,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from .fatigue import summarize_recent_metrics

    if window_minutes < 1 or window_minutes > 720:
        raise HTTPException(status_code=400, detail="window_minutes must be between 1 and 720")
    if patient_profile_id is not None:
        validate_training_links(db, current_user.id, patient_profile_id, None)
    query = db.query(models.WearableMetricModel).filter(models.WearableMetricModel.user_id == current_user.id)
    if patient_profile_id is not None:
        query = query.filter(models.WearableMetricModel.patient_profile_id == patient_profile_id)
    metrics = query.order_by(models.WearableMetricModel.recorded_at.desc()).limit(100).all()
    return FatigueStatusResponse(**summarize_recent_metrics(metrics, window_minutes=window_minutes))


@router.post("/doctor_links", response_model=DoctorPatientLinkResponse, status_code=201)
def create_doctor_link(
    req: DoctorPatientLinkCreateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from .collaboration import is_doctor, link_response

    doctor = get_user_by_account(db, req.doctor_account.strip())
    if not doctor or not is_doctor(doctor):
        raise HTTPException(status_code=404, detail="Doctor not found")
    if req.patient_profile_id is not None:
        validate_training_links(db, current_user.id, req.patient_profile_id, None)
    existing = (
        db.query(models.DoctorPatientLinkModel)
        .filter(
            models.DoctorPatientLinkModel.user_id == current_user.id,
            models.DoctorPatientLinkModel.doctor_id == doctor.id,
            models.DoctorPatientLinkModel.patient_profile_id == req.patient_profile_id,
        )
        .first()
    )
    if existing:
        existing.status = "active"
        existing.patient_note = req.patient_note
        db.commit()
        db.refresh(existing)
        return DoctorPatientLinkResponse(**link_response(existing))
    link = models.DoctorPatientLinkModel(
        user_id=current_user.id,
        doctor_id=doctor.id,
        patient_profile_id=req.patient_profile_id,
        patient_note=req.patient_note,
        status="active",
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return DoctorPatientLinkResponse(**link_response(link))


@router.get("/doctor/patients", response_model=list[DoctorPatientLinkResponse])
def doctor_list_patients(
    db: Session = Depends(get_db),
    current_user=Depends(get_doctor_user),
):
    from .collaboration import link_response

    links = (
        db.query(models.DoctorPatientLinkModel)
        .filter(
            models.DoctorPatientLinkModel.doctor_id == current_user.id,
            models.DoctorPatientLinkModel.status == "active",
        )
        .order_by(models.DoctorPatientLinkModel.updated_at.desc())
        .all()
    )
    return [DoctorPatientLinkResponse(**link_response(link)) for link in links]


def _resolve_review_doctor(db: Session, req: PrescriptionReviewShareRequest):
    from .collaboration import is_doctor

    doctor = None
    if req.doctor_id is not None:
        doctor = db.query(models.UserModel).filter(models.UserModel.id == req.doctor_id).first()
    elif req.doctor_account:
        doctor = get_user_by_account(db, req.doctor_account.strip())
    if not doctor or not is_doctor(doctor):
        raise HTTPException(status_code=404, detail="Doctor not found")
    return doctor


@router.post("/prescriptions/{prescription_id}/reviews/share", response_model=PrescriptionReviewResponse, status_code=201)
def share_prescription_for_review(
    prescription_id: int,
    req: PrescriptionReviewShareRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from .collaboration import doctor_patient_link_exists, review_response

    prescription = get_prescription(db, prescription_id, user_id=current_user.id)
    if not prescription:
        raise HTTPException(status_code=404, detail="Prescription not found")
    doctor = _resolve_review_doctor(db, req)
    if not doctor_patient_link_exists(db, doctor.id, current_user.id, prescription.patient_profile_id):
        raise HTTPException(status_code=403, detail="doctor is not linked to this patient")
    review = models.PrescriptionReviewModel(
        prescription_id=prescription.id,
        user_id=current_user.id,
        doctor_id=doctor.id,
        patient_profile_id=prescription.patient_profile_id,
        status="pending",
        patient_note=req.patient_note,
        risk_level=(prescription.raw_response or {}).get("safety", {}).get("risk_level", "unknown"),
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return PrescriptionReviewResponse(**review_response(review))


@router.get("/doctor/reviews", response_model=list[PrescriptionReviewResponse])
def doctor_list_reviews(
    status: str | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_doctor_user),
):
    from .collaboration import review_response

    query = db.query(models.PrescriptionReviewModel).filter(models.PrescriptionReviewModel.doctor_id == current_user.id)
    if status:
        query = query.filter(models.PrescriptionReviewModel.status == status)
    reviews = query.order_by(models.PrescriptionReviewModel.updated_at.desc()).all()
    return [PrescriptionReviewResponse(**review_response(review)) for review in reviews]


@router.put("/doctor/reviews/{review_id}", response_model=PrescriptionReviewResponse)
def doctor_update_review(
    review_id: int,
    req: PrescriptionReviewUpdateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_doctor_user),
):
    from .collaboration import review_response

    allowed = {"approved", "changes_requested", "reviewed"}
    if req.status not in allowed:
        raise HTTPException(status_code=400, detail="status must be approved, changes_requested or reviewed")
    review = (
        db.query(models.PrescriptionReviewModel)
        .filter(
            models.PrescriptionReviewModel.id == review_id,
            models.PrescriptionReviewModel.doctor_id == current_user.id,
        )
        .first()
    )
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    review.status = req.status
    review.doctor_note = req.doctor_note
    review.risk_level = req.risk_level or review.risk_level
    review.reviewed_at = datetime.utcnow()
    db.commit()
    db.refresh(review)
    return PrescriptionReviewResponse(**review_response(review))


@router.post("/doctor/reviews/{review_id}/adjustments", response_model=PrescriptionAdjustmentResponse, status_code=201)
def doctor_create_adjustment(
    review_id: int,
    req: PrescriptionAdjustmentCreateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_doctor_user),
):
    from .collaboration import actions_for_prescription, adjustment_response, normalize_adjusted_actions

    review = (
        db.query(models.PrescriptionReviewModel)
        .filter(
            models.PrescriptionReviewModel.id == review_id,
            models.PrescriptionReviewModel.doctor_id == current_user.id,
        )
        .first()
    )
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    base_actions = actions_for_prescription(db, review.prescription_id)
    adjusted_actions = req.adjusted_actions or normalize_adjusted_actions(base_actions, req.action_changes)
    adjustment = models.PrescriptionAdjustmentModel(
        review_id=review.id,
        prescription_id=review.prescription_id,
        user_id=review.user_id,
        doctor_id=current_user.id,
        source="doctor",
        status="proposed",
        reason=req.reason,
        summary=req.summary or "医生基于处方审核提出调整建议。",
        action_changes=req.action_changes or [],
        adjusted_actions=adjusted_actions,
    )
    review.status = "changes_requested"
    db.add(adjustment)
    db.commit()
    db.refresh(adjustment)
    return PrescriptionAdjustmentResponse(**adjustment_response(adjustment))


@router.post("/prescriptions/{prescription_id}/adjustments/auto", response_model=PrescriptionAdjustmentResponse, status_code=201)
def create_auto_adjustment(
    prescription_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from .collaboration import adjustment_response, build_auto_adjustment

    prescription = get_prescription(db, prescription_id, user_id=current_user.id)
    if not prescription:
        raise HTTPException(status_code=404, detail="Prescription not found")
    proposal = build_auto_adjustment(db, prescription)
    adjustment = models.PrescriptionAdjustmentModel(
        prescription_id=prescription.id,
        user_id=current_user.id,
        source="system",
        status="proposed",
        reason=proposal["reason"],
        summary=proposal["summary"],
        action_changes=proposal["action_changes"],
        adjusted_actions=proposal["adjusted_actions"],
    )
    db.add(adjustment)
    db.commit()
    db.refresh(adjustment)
    return PrescriptionAdjustmentResponse(**adjustment_response(adjustment))


@router.get("/prescription_adjustments", response_model=list[PrescriptionAdjustmentResponse])
def list_prescription_adjustments(
    status: str | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from .collaboration import adjustment_response

    query = db.query(models.PrescriptionAdjustmentModel).filter(models.PrescriptionAdjustmentModel.user_id == current_user.id)
    if status:
        query = query.filter(models.PrescriptionAdjustmentModel.status == status)
    adjustments = query.order_by(models.PrescriptionAdjustmentModel.updated_at.desc()).all()
    return [PrescriptionAdjustmentResponse(**adjustment_response(item)) for item in adjustments]


@router.post("/prescription_adjustments/{adjustment_id}/decision", response_model=PrescriptionAdjustmentResponse)
def decide_prescription_adjustment(
    adjustment_id: int,
    req: PrescriptionAdjustmentDecisionRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from .collaboration import adjustment_response, apply_adjustment

    if req.decision not in {"apply", "reject"}:
        raise HTTPException(status_code=400, detail="decision must be apply or reject")
    adjustment = (
        db.query(models.PrescriptionAdjustmentModel)
        .filter(
            models.PrescriptionAdjustmentModel.id == adjustment_id,
            models.PrescriptionAdjustmentModel.user_id == current_user.id,
        )
        .first()
    )
    if not adjustment:
        raise HTTPException(status_code=404, detail="Adjustment not found")
    if adjustment.status != "proposed":
        raise HTTPException(status_code=400, detail="adjustment already decided")
    if req.decision == "reject":
        adjustment.status = "rejected"
        adjustment.decided_at = datetime.utcnow()
        db.commit()
        db.refresh(adjustment)
        return PrescriptionAdjustmentResponse(**adjustment_response(adjustment))
    apply_adjustment(db, adjustment)
    db.refresh(adjustment)
    return PrescriptionAdjustmentResponse(**adjustment_response(adjustment))


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
    from .cache import cache_get_json, cache_set_json
    from .knowledge import load_action_library

    cached = cache_get_json("actions:v1")
    if cached:
        return cached
    actions = load_action_library()
    cache_payload = [
        action.model_dump() if hasattr(action, "model_dump") else action.dict()
        for action in actions
    ]
    cache_set_json("actions:v1", cache_payload)
    return actions


@router.get("/knowledge/articles", response_model=KnowledgeArticleListResponse)
def list_knowledge_articles(
    q: str | None = None,
    body_region: str | None = None,
    limit: int = 10,
):
    from .education import build_knowledge_articles

    return KnowledgeArticleListResponse(
        items=build_knowledge_articles(q=q, body_region=body_region, limit=limit)
    )


@router.get("/knowledge/rag/status")
def knowledge_rag_status(current_user=Depends(get_current_user)):
    from .rag import rag_status

    return rag_status()


@router.post("/knowledge/rag/reindex")
def knowledge_rag_reindex(current_user=Depends(get_admin_user)):
    from .rag import reindex_knowledge

    return reindex_knowledge()


@router.post("/knowledge/rag/search", response_model=RAGSearchResponse)
def knowledge_rag_search(req: RAGSearchRequest, current_user=Depends(get_current_user)):
    from .rag import rag_status, retrieve_contexts

    if not req.query or not req.query.strip():
        raise HTTPException(status_code=400, detail="query required")
    status = rag_status()
    results = retrieve_contexts(
        query=req.query,
        limit=req.limit or 5,
        body_regions=req.body_regions,
        kind=req.kind,
    )
    return RAGSearchResponse(
        provider=status["provider"],
        collection=status["collection"],
        results=results,
    )


@router.post("/knowledge/qa", response_model=KnowledgeQAResponse)
def ask_knowledge_question(req: KnowledgeQARequest):
    from .education import answer_knowledge_question

    try:
        result = answer_knowledge_question(
            question=req.question,
            pain_regions=req.pain_regions,
            limit=req.limit or 4,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return KnowledgeQAResponse(**result)


@router.post("/test_deepseek")
def test_deepseek():
    """Test DeepSeek API connection."""
    from .doubao import DeepSeekError, generate_prescription_summary
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
    except DeepSeekError as exc:
        return {"status": "error", "detail": str(exc)}


@router.post("/test_doubao")
def test_doubao():
    """Backward-compatible alias for the DeepSeek API connection test."""
    return test_deepseek()
