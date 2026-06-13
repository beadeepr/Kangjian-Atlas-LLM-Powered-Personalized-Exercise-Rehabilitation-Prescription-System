from sqlalchemy.orm import Session
from . import models, schema
import base64
import hashlib
import hmac
import os


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
        gender=user.gender,
        age=user.age,
    )


def get_user_by_account(db: Session, account: str):
    return db.query(models.UserModel).filter(models.UserModel.account == account).first()


def create_user(db: Session, request: schema.UserCreateRequest) -> schema.UserResponse:
    user = models.UserModel(
        account=request.account,
        password_hash=_hash_password(request.password),
        nickname=request.nickname,
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


def create_prescription(db: Session, prescription: schema.PrescriptionRequest, user_id: int | None = None):
    from .knowledge import load_prompt_template, render_prescription_summary, select_actions_for_prescription
    from .doubao import generate_prescription_summary

    selected_actions = select_actions_for_prescription(
        symptoms=prescription.symptoms,
        pain_regions=prescription.pain_regions,
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
    } if isinstance(result, dict) else None

    db_prescription = models.PrescriptionModel(
        user_id=user_id,
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
