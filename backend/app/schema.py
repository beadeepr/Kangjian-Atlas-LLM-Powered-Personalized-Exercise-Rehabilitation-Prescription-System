from pydantic import BaseModel
from typing import List, Optional


class PrescriptionRequest(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    symptoms: str
    history: Optional[str] = None
    pain_regions: Optional[List[str]] = None
    mobility_score: Optional[int] = None


class ActionItem(BaseModel):
    name: str
    sets: int
    reps: int
    note: Optional[str]


class PrescriptionResponse(BaseModel):
    id: Optional[int] = None
    patient_name: Optional[str] = None
    patient_age: Optional[int] = None
    summary: str
    actions: List[ActionItem]
    raw_response: Optional[dict] = None


class PoseCorrectionRequest(BaseModel):
    action_id: Optional[str] = None
    keypoints: Optional[List[List[float]]] = None
    visibility: Optional[List[float]] = None
    timestamp: Optional[int] = None


class PoseCorrectionResponse(BaseModel):
    feedback: List[str]
    score: Optional[int] = None
    status: Optional[str] = None
