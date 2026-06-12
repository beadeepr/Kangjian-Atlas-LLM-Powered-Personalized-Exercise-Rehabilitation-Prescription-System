from sqlalchemy.orm import Session
from . import models, schema


def get_actions_by_prescription(db: Session, prescription_id: int):
    return db.query(models.ActionModel).filter(models.ActionModel.prescription_id == prescription_id).all()


def get_prescription(db: Session, prescription_id: int):
    return db.query(models.PrescriptionModel).filter(models.PrescriptionModel.id == prescription_id).first()


def create_prescription(db: Session, prescription: schema.PrescriptionRequest):
    from .knowledge import load_action_library

    actions = load_action_library()
    selected_actions = [action for action in actions if action.reps > 0][:3]
    db_prescription = models.PrescriptionModel(
        patient_name=prescription.name,
        patient_age=prescription.age,
        symptoms=prescription.symptoms,
        history=prescription.history,
        summary=f"基于主诉 {prescription.symptoms} 的初步康复处方"
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
