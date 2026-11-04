"""
Healthcare Facilities & Data Models
=====================================
Purpose: SQLite database models for healthcare facilities, specialists,
         patient sessions, and navigation history.
Dependencies: SQLAlchemy, config.settings
"""

from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import (
    create_engine, Column, String, Integer, Float, Boolean,
    DateTime, Text, ForeignKey, Index, JSON
)
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker, Session
from config.settings import settings
import uuid


# ─── Engine & Session ────────────────────────────────────────────────────────
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=settings.DB_ECHO,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Session:
    """Dependency injection helper — yields a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ─── Models ──────────────────────────────────────────────────────────────────

class HealthcareFacility(Base):
    """Healthcare facility entity (hospitals, PHCs, CHCs, clinics, labs)."""
    __tablename__ = "healthcare_facilities"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(200), nullable=False)
    facility_type = Column(String(50), nullable=False)  # hospital|PHC|CHC|clinic|lab|pharmacy
    district = Column(String(100), nullable=False)
    state = Column(String(100), nullable=False)
    address = Column(Text)
    latitude = Column(Float)
    longitude = Column(Float)
    phone = Column(String(20))
    email = Column(String(100))
    website = Column(String(200))
    is_government = Column(Boolean, default=True)
    is_24x7 = Column(Boolean, default=False)
    has_emergency = Column(Boolean, default=False)
    has_ambulance = Column(Boolean, default=False)
    has_icu = Column(Boolean, default=False)
    bed_count = Column(Integer, default=0)
    available_beds = Column(Integer, default=0)
    departments = Column(JSON, default=list)          # ["General", "Orthopedics", ...]
    specialties = Column(JSON, default=list)
    services = Column(JSON, default=list)
    languages_spoken = Column(JSON, default=list)
    distance_km_from_block = Column(Float)
    avg_wait_time_minutes = Column(Integer)
    consultation_fee = Column(Float, default=0.0)
    rating = Column(Float, default=0.0)
    accreditation = Column(String(50))               # NABH | NABL | None
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    specialists = relationship("Specialist", back_populates="facility")

    # Indexes for performance
    __table_args__ = (
        Index("idx_facility_district", "district"),
        Index("idx_facility_type", "facility_type"),
        Index("idx_facility_state_district", "state", "district"),
    )


class Specialist(Base):
    """Specialist/doctor entity linked to a healthcare facility."""
    __tablename__ = "specialists"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    facility_id = Column(String, ForeignKey("healthcare_facilities.id"), nullable=False)
    name = Column(String(200), nullable=False)
    specialty = Column(String(100), nullable=False)
    sub_specialty = Column(String(100))
    qualification = Column(String(200))
    experience_years = Column(Integer)
    registration_number = Column(String(50))
    phone = Column(String(20))
    email = Column(String(100))
    available_days = Column(JSON, default=list)      # ["Monday", "Wednesday", ...]
    available_slots = Column(JSON, default=list)     # ["09:00-12:00", ...]
    consultation_fee = Column(Float, default=0.0)
    telemedicine_available = Column(Boolean, default=False)
    languages = Column(JSON, default=list)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    facility = relationship("HealthcareFacility", back_populates="specialists")

    __table_args__ = (
        Index("idx_specialist_specialty", "specialty"),
        Index("idx_specialist_facility", "facility_id"),
    )


class PatientSession(Base):
    """Anonymous patient navigation session (no PII stored by default)."""
    __tablename__ = "patient_sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_token = Column(String(64), unique=True, nullable=False)
    district = Column(String(100))
    state = Column(String(100))
    chief_complaint_category = Column(String(100))  # non-PII category only
    urgency_level = Column(String(20))              # low | medium | high | emergency
    navigation_status = Column(String(30), default="active")  # active|completed|escalated
    agent_invocations = Column(JSON, default=list)
    referral_generated = Column(Boolean, default=False)
    escalated_to_emergency = Column(Boolean, default=False)
    human_review_requested = Column(Boolean, default=False)
    feedback_score = Column(Integer)                 # 1-5 stars
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    navigation_steps = relationship("NavigationHistory", back_populates="session",
                                    cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_session_token", "session_token"),
        Index("idx_session_district", "district"),
        Index("idx_session_urgency", "urgency_level"),
    )


class NavigationHistory(Base):
    """Step-by-step navigation history for a patient session."""
    __tablename__ = "navigation_history"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey("patient_sessions.id"), nullable=False)
    step_number = Column(Integer, nullable=False)
    agent_name = Column(String(100), nullable=False)
    action_taken = Column(String(200), nullable=False)
    result_summary = Column(Text)
    facilities_considered = Column(JSON, default=list)
    recommended_facility_id = Column(String, ForeignKey("healthcare_facilities.id"))
    confidence_score = Column(Float)
    decision_factors = Column(JSON, default=list)     # explainability
    sources_used = Column(JSON, default=list)         # RAG sources
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    session = relationship("PatientSession", back_populates="navigation_steps")

    __table_args__ = (
        Index("idx_nav_session_step", "session_id", "step_number"),
    )


class SystemMetrics(Base):
    """Operational metrics for monitoring & observability."""
    __tablename__ = "system_metrics"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    metric_name = Column(String(100), nullable=False)
    metric_value = Column(Float, nullable=False)
    metric_unit = Column(String(50))
    tags = Column(JSON, default=dict)
    recorded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_metric_name_time", "metric_name", "recorded_at"),
    )


def init_db() -> None:
    """Initialize database — creates all tables if they do not exist."""
    Base.metadata.create_all(bind=engine)
