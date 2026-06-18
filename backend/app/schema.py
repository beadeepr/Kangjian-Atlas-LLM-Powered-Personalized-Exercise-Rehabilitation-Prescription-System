from pydantic import BaseModel
from datetime import date
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
    role: Optional[str] = None
    gender: Optional[str] = None
    age: Optional[int] = None


class LoginResponse(BaseModel):
    message: str
    token: str
    user: UserResponse


class PatientProfileBase(BaseModel):
    name: str
    gender: Optional[str] = None
    age: Optional[int] = None
    phone: Optional[str] = None
    height_cm: Optional[int] = None
    weight_kg: Optional[int] = None
    pain_regions: Optional[List[str]] = None
    history: Optional[str] = None
    allergy_history: Optional[str] = None
    surgery_history: Optional[str] = None
    rehab_goal: Optional[str] = None
    note: Optional[str] = None


class PatientProfileCreateRequest(PatientProfileBase):
    pass


class PatientProfileUpdateRequest(BaseModel):
    name: Optional[str] = None
    gender: Optional[str] = None
    age: Optional[int] = None
    phone: Optional[str] = None
    height_cm: Optional[int] = None
    weight_kg: Optional[int] = None
    pain_regions: Optional[List[str]] = None
    history: Optional[str] = None
    allergy_history: Optional[str] = None
    surgery_history: Optional[str] = None
    rehab_goal: Optional[str] = None
    note: Optional[str] = None


class PatientProfileResponse(PatientProfileBase):
    id: int
    user_id: int


class TrainingCheckinBase(BaseModel):
    patient_profile_id: Optional[int] = None
    prescription_id: Optional[int] = None
    action_id: Optional[str] = None
    action_name: str
    trained_on: date
    duration_minutes: Optional[int] = None
    completed_sets: Optional[int] = None
    completed_reps: Optional[int] = None
    pain_before: Optional[int] = None
    pain_after: Optional[int] = None
    difficulty: Optional[int] = None
    score: Optional[int] = None
    note: Optional[str] = None


class TrainingCheckinCreateRequest(TrainingCheckinBase):
    pass


class TrainingCheckinUpdateRequest(BaseModel):
    patient_profile_id: Optional[int] = None
    prescription_id: Optional[int] = None
    action_id: Optional[str] = None
    action_name: Optional[str] = None
    trained_on: Optional[date] = None
    duration_minutes: Optional[int] = None
    completed_sets: Optional[int] = None
    completed_reps: Optional[int] = None
    pain_before: Optional[int] = None
    pain_after: Optional[int] = None
    difficulty: Optional[int] = None
    score: Optional[int] = None
    note: Optional[str] = None


class TrainingCheckinResponse(TrainingCheckinBase):
    id: int
    user_id: int


class TrainingTrendPoint(BaseModel):
    date: date
    checkin_count: int
    total_duration_minutes: int
    avg_pain_before: Optional[float] = None
    avg_pain_after: Optional[float] = None
    avg_score: Optional[float] = None


class TrainingTrendResponse(BaseModel):
    start_date: date
    end_date: date
    points: List[TrainingTrendPoint]


class TrainingVisualizationResponse(BaseModel):
    total_checkins: int
    total_duration_minutes: int
    active_days: int
    avg_score: Optional[float] = None
    avg_pain_change: Optional[float] = None
    trend: TrainingTrendResponse


class PrescriptionRequest(BaseModel):
    patient_profile_id: Optional[int] = None
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


class ActionUpdateRequest(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    sets: Optional[int] = None
    reps: Optional[int] = None
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
    patient_profile_id: Optional[int] = None
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
