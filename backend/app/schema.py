from pydantic import BaseModel
from typing import List, Optional


class UserCreateRequest(BaseModel):
    account: str
    password: str
    nickname: str
    gender: Optional[str] = None
    age: Optional[int] = None


class UserLoginRequest(BaseModel):
    account: str
    password: str


class UserResponse(BaseModel):
    id: int
    account: str
    nickname: str
    gender: Optional[str] = None
    age: Optional[int] = None


class LoginResponse(BaseModel):
    message: str
    token: str
    user: UserResponse


class PrescriptionRequest(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    symptoms: str
    history: Optional[str] = None
    pain_regions: Optional[List[str]] = None
    mobility_score: Optional[int] = None


class ActionItem(BaseModel):
    id: Optional[str] = None
    name: str
    sets: int
    reps: int
    note: Optional[str] = None
    description: Optional[str] = None
    frequency: Optional[str] = None
    contraindications: Optional[str] = None
    progression: Optional[str] = None
    regression: Optional[str] = None
    body_regions: Optional[List[str]] = None
    target_conditions: Optional[List[str]] = None


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
    score: int = 0
    status: str = "warning"
