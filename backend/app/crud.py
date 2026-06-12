from sqlalchemy.orm import Session
from . import models, schema


def get_actions_by_prescription(db: Session, prescription_id: int):
    return db.query(models.ActionModel).filter(models.ActionModel.prescription_id == prescription_id).all()


def get_prescription(db: Session, prescription_id: int):
    return db.query(models.PrescriptionModel).filter(models.PrescriptionModel.id == prescription_id).first()


def list_prescriptions(db: Session):
    return db.query(models.PrescriptionModel).order_by(models.PrescriptionModel.created_at.desc()).all()


def create_prescription(db: Session, prescription: schema.PrescriptionRequest):
    from .knowledge import load_action_library, render_prescription_summary
    from .deepseek import extract_titles, search_deepseek, DeepSeekError

    actions = load_action_library()
    selected_actions = [action for action in actions if action.reps > 0][:3]

    deepseek_summary = None
    try:
        result = search_deepseek(prescription.symptoms, top_k=3)
        titles = extract_titles(result)
        if titles:
            deepseek_summary = "；".join(titles)
    except DeepSeekError:
        deepseek_summary = None

    summary = render_prescription_summary(
        name=prescription.name,
        age=prescription.age,
        symptoms=prescription.symptoms,
        history=prescription.history,
        actions=selected_actions,
        deepseek_summary=deepseek_summary,
    )

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
    feedback = ["请收下巴，头部前屈过多。", "膝盖角度合适，继续保持。"]
    db_feedback = models.PoseFeedbackModel(
        request_data=request.keypoints,
        feedback=feedback
    )
    db.add(db_feedback)
    db.commit()
    db.refresh(db_feedback)
    return db_feedback
