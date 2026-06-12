from pydantic import BaseModel
from typing import List, Optional


class PrescriptionRequest(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    symptoms: str
    history: Optional[str] = None


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
    # For MVP accept keypoints or base64 image; here we accept simple keypoints placeholder
    keypoints: Optional[List[List[float]]]


class PoseCorrectionResponse(BaseModel):
    feedback: List[str]
