from sqlalchemy.orm import Session
from . import models, schema


def get_actions_by_prescription(db: Session, prescription_id: int):
    return db.query(models.ActionModel).filter(models.ActionModel.prescription_id == prescription_id).all()


def get_prescription(db: Session, prescription_id: int):
    return db.query(models.PrescriptionModel).filter(models.PrescriptionModel.id == prescription_id).first()


def list_prescriptions(db: Session):
    return db.query(models.PrescriptionModel).order_by(models.PrescriptionModel.created_at.desc()).all()


def create_prescription(db: Session, prescription: schema.PrescriptionRequest):
    from .knowledge import load_action_library
    from .doubao import generate_prescription_summary, DoubaoError

    actions = load_action_library()
    selected_actions = [action for action in actions if action.reps > 0][:3]
    action_names = [action.name for action in selected_actions]

    try:
        result = generate_prescription_summary(
            patient_name=prescription.name or "患者",
            age=prescription.age,
            symptoms=prescription.symptoms,
            history=prescription.history,
            actions=action_names,
        )
        if isinstance(result, dict):
            summary = result.get('text') or f"基于主诉 {prescription.symptoms} 的康复处方。推荐动作：{'; '.join(action_names) or '暂无'}。"
            raw_response = result.get('raw')
        else:
            summary = str(result)
            raw_response = None
    except DoubaoError:
        # Fallback to basic summary if Doubao fails
        summary = f"基于主诉 {prescription.symptoms} 的康复处方。推荐动作：{'; '.join(action_names) or '暂无'}。"
        raw_response = None

    db_prescription = models.PrescriptionModel(
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
    feedback = ["请收下巴，头部前屈过多。", "膝盖角度合适，继续保持。"]
    db_feedback = models.PoseFeedbackModel(
        request_data=request.keypoints,
        feedback=feedback
    )
    db.add(db_feedback)
    db.commit()
    db.refresh(db_feedback)
    return db_feedback
