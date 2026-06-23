from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()


def now():
    return datetime.utcnow()


class PrescriptionModel(Base):
    __tablename__ = 'prescriptions'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    patient_profile_id = Column(Integer, ForeignKey('patient_profiles.id'), nullable=True, index=True)
    patient_name = Column(String(128), nullable=True)
    patient_age = Column(Integer, nullable=True)
    symptoms = Column(Text, nullable=False)
    history = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    raw_response = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)

    actions = relationship('ActionModel', back_populates='prescription', cascade='all, delete-orphan')
    user = relationship('UserModel', back_populates='prescriptions')
    patient_profile = relationship('PatientProfileModel', back_populates='prescriptions')
    training_checkins = relationship('TrainingCheckinModel', back_populates='prescription')


class ActionModel(Base):
    __tablename__ = 'actions'

    id = Column(Integer, primary_key=True, index=True)
    prescription_id = Column(Integer, ForeignKey('prescriptions.id'), nullable=False)
    name = Column(String(128), nullable=False)
    sets = Column(Integer, nullable=True)
    reps = Column(Integer, nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)

    prescription = relationship('PrescriptionModel', back_populates='actions')


class PoseFeedbackModel(Base):
    __tablename__ = 'pose_feedback'

    id = Column(Integer, primary_key=True, index=True)
    request_data = Column(JSON, nullable=True)
    feedback = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=now)


class UserModel(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    account = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    nickname = Column(String(64), nullable=False)
    role = Column(String(32), nullable=False, default='user')
    gender = Column(String(16), nullable=True)
    age = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)

    prescriptions = relationship('PrescriptionModel', back_populates='user')
    patient_profiles = relationship('PatientProfileModel', back_populates='user', cascade='all, delete-orphan')
    training_checkins = relationship('TrainingCheckinModel', back_populates='user', cascade='all, delete-orphan')
    imaging_reports = relationship('ImagingReportModel', back_populates='user', cascade='all, delete-orphan')
    feedback_items = relationship('UserFeedbackModel', back_populates='user', cascade='all, delete-orphan')


class PatientProfileModel(Base):
    __tablename__ = 'patient_profiles'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    gender = Column(String(16), nullable=True)
    age = Column(Integer, nullable=True)
    phone = Column(String(32), nullable=True)
    height_cm = Column(Integer, nullable=True)
    weight_kg = Column(Integer, nullable=True)
    pain_regions = Column(JSON, nullable=True)
    history = Column(Text, nullable=True)
    allergy_history = Column(Text, nullable=True)
    surgery_history = Column(Text, nullable=True)
    rehab_goal = Column(Text, nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)

    user = relationship('UserModel', back_populates='patient_profiles')
    prescriptions = relationship('PrescriptionModel', back_populates='patient_profile')
    training_checkins = relationship('TrainingCheckinModel', back_populates='patient_profile')
    imaging_reports = relationship('ImagingReportModel', back_populates='patient_profile', cascade='all, delete-orphan')


class ImagingReportModel(Base):
    __tablename__ = 'imaging_reports'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    patient_profile_id = Column(Integer, ForeignKey('patient_profiles.id'), nullable=True, index=True)
    report_type = Column(String(64), nullable=True)
    file_name = Column(String(256), nullable=True)
    file_path = Column(String(512), nullable=True)
    ocr_text = Column(Text, nullable=True)
    ocr_status = Column(String(32), nullable=False, default='pending')
    risk_level = Column(String(32), nullable=False, default='unknown')
    red_flags = Column(JSON, nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)

    user = relationship('UserModel', back_populates='imaging_reports')
    patient_profile = relationship('PatientProfileModel', back_populates='imaging_reports')


class TrainingCheckinModel(Base):
    __tablename__ = 'training_checkins'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    patient_profile_id = Column(Integer, ForeignKey('patient_profiles.id'), nullable=True, index=True)
    prescription_id = Column(Integer, ForeignKey('prescriptions.id'), nullable=True, index=True)
    action_id = Column(String(128), nullable=True)
    action_name = Column(String(128), nullable=False)
    trained_on = Column(Date, nullable=False, index=True)
    duration_minutes = Column(Integer, nullable=True)
    completed_sets = Column(Integer, nullable=True)
    completed_reps = Column(Integer, nullable=True)
    pain_before = Column(Integer, nullable=True)
    pain_after = Column(Integer, nullable=True)
    difficulty = Column(Integer, nullable=True)
    score = Column(Integer, nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)

    user = relationship('UserModel', back_populates='training_checkins')
    patient_profile = relationship('PatientProfileModel', back_populates='training_checkins')
    prescription = relationship('PrescriptionModel', back_populates='training_checkins')


class UserFeedbackModel(Base):
    __tablename__ = 'user_feedback'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    category = Column(String(64), nullable=False, default='general')
    rating = Column(Integer, nullable=True)
    content = Column(Text, nullable=False)
    contact = Column(String(128), nullable=True)
    source = Column(String(64), nullable=True)
    status = Column(String(32), nullable=False, default='open', index=True)
    admin_note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)

    user = relationship('UserModel', back_populates='feedback_items')
