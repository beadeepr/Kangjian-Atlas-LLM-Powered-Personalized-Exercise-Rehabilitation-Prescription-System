from sqlalchemy.orm import Session
from . import models, schema


def get_actions_by_prescription(db: Session, prescription_id: int):
    return db.query(models.ActionModel).filter(models.ActionModel.prescription_id == prescription_id).all()


def get_prescription(db: Session, prescription_id: int):
    return db.query(models.PrescriptionModel).filter(models.PrescriptionModel.id == prescription_id).first()


def list_prescriptions(db: Session):
    return db.query(models.PrescriptionModel).order_by(models.PrescriptionModel.created_at.desc()).all()


def create_prescription(db: Session, prescription: schema.PrescriptionRequest):
    from .knowledge import select_actions_for_prescription
    from .doubao import generate_prescription_summary, DoubaoError

    selected_actions = select_actions_for_prescription(
        symptoms=prescription.symptoms,
        pain_regions=prescription.pain_regions,
        history=prescription.history,
        mobility_score=prescription.mobility_score,
    )
    action_names = [action.name for action in selected_actions]

    try:
        summary = generate_prescription_summary(
            patient_name=prescription.name or "患者",
            age=prescription.age,
            symptoms=prescription.symptoms,
            history=prescription.history,
            actions=action_names,
            pain_regions=prescription.pain_regions,
            mobility_score=prescription.mobility_score,
        )
    except DoubaoError:
        # Fallback to basic summary if Doubao fails
        summary = f"基于主诉 {prescription.symptoms} 的康复处方。推荐动作：{'; '.join(action_names) or '暂无'}。"

    db_prescription = models.PrescriptionModel(
        patient_name=prescription.name,
        patient_age=prescription.age,
        symptoms=prescription.symptoms,
        history=prescription.history,
        summary=summary
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

    action_id = request.action_id or ""
    keypoints = request.keypoints or []
    visibility = request.visibility or []

    if not keypoints or len(keypoints) < 33:
        result = {
            "feedback": ["请全身入镜，确保摄像头能拍到完整身体"],
            "score": 0,
            "status": "error",
        }
    elif action_id not in {"wall_squat", "neck_side_bend"}:
        result = {
            "feedback": ["暂不支持该动作"],
            "score": 0,
            "status": "error",
        }
    else:
        result = analyze_pose(action_id, keypoints, visibility)

    db_feedback = models.PoseFeedbackModel(
        request_data={
            "action_id": action_id,
            "keypoints": keypoints,
            "visibility": visibility,
            "timestamp": request.timestamp,
        },
        feedback=result["feedback"],
    )
    db.add(db_feedback)
    db.commit()
    db.refresh(db_feedback)
    return result
