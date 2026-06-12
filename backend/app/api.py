from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .crud import (
    create_prescription,
    create_pose_feedback,
    get_actions_by_prescription,
    get_prescription,
    list_prescriptions as crud_list_prescriptions,
)
from .database import SessionLocal
from .deepseek import search_deepseek, DeepSeekError
from .schema import PrescriptionRequest, PrescriptionResponse, ActionItem, PoseCorrectionRequest, PoseCorrectionResponse

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/generate_prescription", response_model=PrescriptionResponse)
def generate_prescription(req: PrescriptionRequest, db: Session = Depends(get_db)):
    if not req.symptoms:
        raise HTTPException(status_code=400, detail="symptoms required")
    prescription = create_prescription(db, req)
    actions = get_actions_by_prescription(db, prescription.id)
    return PrescriptionResponse(
        id=prescription.id,
        patient_name=prescription.patient_name,
        patient_age=prescription.patient_age,
        summary=prescription.summary,
        actions=[
            {"name": action.name, "sets": action.sets, "reps": action.reps, "note": action.note}
            for action in actions
        ]
    )


@router.get("/prescriptions/{prescription_id}", response_model=PrescriptionResponse)
def read_prescription(prescription_id: int, db: Session = Depends(get_db)):
    prescription = get_prescription(db, prescription_id)
    if not prescription:
        raise HTTPException(status_code=404, detail="Prescription not found")
    actions = get_actions_by_prescription(db, prescription.id)
    return PrescriptionResponse(
        id=prescription.id,
        patient_name=prescription.patient_name,
        patient_age=prescription.patient_age,
        summary=prescription.summary,
        actions=[
            {"name": action.name, "sets": action.sets, "reps": action.reps, "note": action.note}
            for action in actions
        ]
    )


@router.post("/correct_pose", response_model=PoseCorrectionResponse)
def correct_pose(req: PoseCorrectionRequest, db: Session = Depends(get_db)):
    feedback_record = create_pose_feedback(db, req)
    return PoseCorrectionResponse(feedback=feedback_record.feedback)


@router.get("/prescriptions", response_model=list[PrescriptionResponse])
def list_prescriptions(db: Session = Depends(get_db)):
    prescriptions = crud_list_prescriptions(db)
    result = []
    for prescription in prescriptions:
        actions = get_actions_by_prescription(db, prescription.id)
        result.append(PrescriptionResponse(
            id=prescription.id,
            patient_name=prescription.patient_name,
            patient_age=prescription.patient_age,
            summary=prescription.summary,
            actions=[
                {"name": action.name, "sets": action.sets, "reps": action.reps, "note": action.note}
                for action in actions
            ]
        ))
    return result


@router.get("/actions", response_model=list[ActionItem])
def list_actions():
    from .knowledge import load_action_library
    return load_action_library()


@router.post("/deepseek_search")
def deepseek_search(req: dict):
    query = req.get("query")
    if not query:
        raise HTTPException(status_code=400, detail="query is required")
    try:
        return search_deepseek(query, top_k=req.get("top_k", 3))
    except DeepSeekError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
