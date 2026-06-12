from sqlalchemy.orm import Session
from . import models, schema


def _action_to_dict(action: schema.ActionItem):
    if hasattr(action, "model_dump"):
        return action.model_dump()
    return action.dict()


def get_actions_by_prescription(db: Session, prescription_id: int):
    return db.query(models.ActionModel).filter(models.ActionModel.prescription_id == prescription_id).all()


def get_prescription(db: Session, prescription_id: int):
    return db.query(models.PrescriptionModel).filter(models.PrescriptionModel.id == prescription_id).first()


def list_prescriptions(db: Session):
    return db.query(models.PrescriptionModel).order_by(models.PrescriptionModel.created_at.desc()).all()


def create_prescription(db: Session, prescription: schema.PrescriptionRequest):
    from .knowledge import load_prompt_template, render_prescription_summary, select_actions_for_request
    from .doubao import generate_prescription_summary

    selected_actions = select_actions_for_request(
        symptoms=prescription.symptoms,
        pain_regions=prescription.pain_regions,
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
