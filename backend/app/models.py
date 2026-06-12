from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()


def now():
    return datetime.utcnow()


class PrescriptionModel(Base):
    __tablename__ = 'prescriptions'

    id = Column(Integer, primary_key=True, index=True)
    patient_name = Column(String(128), nullable=True)
    patient_age = Column(Integer, nullable=True)
    symptoms = Column(Text, nullable=False)
    history = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    raw_response = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)

    actions = relationship('ActionModel', back_populates='prescription', cascade='all, delete-orphan')


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
