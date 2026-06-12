from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .crud import create_prescription, create_pose_feedback, get_actions_by_prescription, get_prescription
from .database import SessionLocal
from .knowledge import load_action_library
from .schema import PrescriptionRequest, PrescriptionResponse, PoseCorrectionRequest, PoseCorrectionResponse
from . import models

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
    prescriptions = db.query(models.PrescriptionModel).all()
    result = []
    for prescription in prescriptions:
        actions = get_actions_by_prescription(db, prescription.id)
        result.append(PrescriptionResponse(
            summary=prescription.summary,
            actions=[
                {"name": action.name, "sets": action.sets, "reps": action.reps, "note": action.note}
                for action in actions
            ]
        ))
    return result


@router.get("/actions")
def list_actions():
    return load_action_library()
