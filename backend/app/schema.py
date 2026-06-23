from pydantic import BaseModel
from datetime import date, datetime
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


class FeedbackCreateRequest(BaseModel):
    category: Optional[str] = "general"
    rating: Optional[int] = None
    content: str
    contact: Optional[str] = None
    source: Optional[str] = None


class FeedbackUpdateRequest(BaseModel):
    status: Optional[str] = None
    admin_note: Optional[str] = None


class FeedbackResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    user_account: Optional[str] = None
    user_nickname: Optional[str] = None
    category: str
    rating: Optional[int] = None
    content: str
    contact: Optional[str] = None
    source: Optional[str] = None
    status: str
    admin_note: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AdminDashboardResponse(BaseModel):
    totals: dict
    recent_activity: dict
    feedback_summary: dict
    action_library_summary: dict
    risk_summary: dict


class AdminUserSummary(BaseModel):
    id: int
    account: str
    nickname: str
    role: str
    gender: Optional[str] = None
    age: Optional[int] = None
    patient_profile_count: int
    prescription_count: int
    training_checkin_count: int
    imaging_report_count: int
    feedback_count: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


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


class ImagingReportCreateRequest(BaseModel):
    patient_profile_id: Optional[int] = None
    report_type: Optional[str] = None
    file_name: Optional[str] = None
    file_content_base64: Optional[str] = None
    ocr_text: Optional[str] = None
    note: Optional[str] = None


class ImagingReportResponse(BaseModel):
    id: int
    user_id: int
    patient_profile_id: Optional[int] = None
    report_type: Optional[str] = None
    file_name: Optional[str] = None
    file_path: Optional[str] = None
    ocr_text: Optional[str] = None
    ocr_status: str
    risk_level: str
    red_flags: Optional[List[dict]] = None
    note: Optional[str] = None
    created_at: Optional[datetime] = None


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


class TrainingReportActionSummary(BaseModel):
    action_name: str
    count: int
    total_duration_minutes: int
    avg_score: Optional[float] = None


class TrainingReportResponse(BaseModel):
    period: str
    start_date: date
    end_date: date
    patient_profile_id: Optional[int] = None
    total_checkins: int
    expected_days: int
    active_days: int
    completion_rate: float
    total_duration_minutes: int
    avg_duration_per_active_day: Optional[float] = None
    avg_score: Optional[float] = None
    avg_pain_before: Optional[float] = None
    avg_pain_after: Optional[float] = None
    avg_pain_change: Optional[float] = None
    vas_summary: str
    action_summaries: List[TrainingReportActionSummary]
    highlights: List[str]
    risks: List[str]
    recommendations: List[str]
    trend: TrainingTrendResponse


class KnowledgeArticleResponse(BaseModel):
    id: str
    title: str
    category: str
    body_regions: List[str]
    summary: str
    content: str
    related_actions: List[dict] = []
    prevention_tips: List[str] = []


class KnowledgeArticleListResponse(BaseModel):
    items: List[KnowledgeArticleResponse]


class KnowledgeQARequest(BaseModel):
    question: str
    pain_regions: Optional[List[str]] = None
    limit: Optional[int] = 4


class KnowledgeQAResponse(BaseModel):
    answer: str
    references: List[KnowledgeArticleResponse]
    suggested_actions: List[dict]
    safety_notes: List[str]


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
    category: Optional[str] = None
    difficulty_level: Optional[str] = None
    stage: Optional[str] = None
    target_muscles: Optional[List[str]] = None
    equipment: Optional[List[str]] = None
    demo_media: Optional[dict] = None
    image: Optional[str] = None
    video_url: Optional[str] = None
    video_hint: Optional[str] = None
    image_hint: Optional[str] = None
    steps: Optional[List[str]] = None
    common_mistakes: Optional[List[str]] = None
    correct_cues: Optional[List[str]] = None
    risk_level: Optional[str] = None
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
    category: Optional[str] = None
    difficulty_level: Optional[str] = None
    stage: Optional[str] = None
    target_muscles: Optional[List[str]] = None
    equipment: Optional[List[str]] = None
    demo_media: Optional[dict] = None
    image: Optional[str] = None
    video_url: Optional[str] = None
    video_hint: Optional[str] = None
    image_hint: Optional[str] = None
    steps: Optional[List[str]] = None
    common_mistakes: Optional[List[str]] = None
    correct_cues: Optional[List[str]] = None
    risk_level: Optional[str] = None
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
