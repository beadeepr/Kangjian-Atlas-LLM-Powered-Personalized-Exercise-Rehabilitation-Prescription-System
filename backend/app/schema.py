from pydantic import BaseModel
from typing import List, Optional


class PrescriptionRequest(BaseModel):
    name: Optional[str]
    age: Optional[int]
    symptoms: str
    history: Optional[str]


class ActionItem(BaseModel):
    name: str
    sets: int
    reps: int
    note: Optional[str]


class PrescriptionResponse(BaseModel):
    summary: str
    actions: List[ActionItem]


class PoseCorrectionRequest(BaseModel):
    # For MVP accept keypoints or base64 image; here we accept simple keypoints placeholder
    keypoints: Optional[List[List[float]]]


class PoseCorrectionResponse(BaseModel):
    feedback: List[str]
