"""
Healthcare Tool Suite — Custom Agent Tools
============================================
Purpose: All external tools and custom Python functions available to the AI agents.
         Implements facility search, specialist lookup, distance calculation,
         emergency detection, appointment availability checks, and referral generation.
Dependencies: SQLAlchemy, pandas, geopy, config.settings, utils.database
"""

import csv
import json
import math
import uuid
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
import pandas as pd
from sqlalchemy.orm import Session

from config.settings import settings
from utils.database import (
    HealthcareFacility, Specialist, PatientSession,
    NavigationHistory, SessionLocal
)
from utils.logger import app_logger, audit_logger


# ─── Helper: Haversine distance formula ──────────────────────────────────────

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance in km between two geo-coordinates."""
    R = 6371.0  # Earth's radius in km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


# ─── Tool 1: Facility Search ─────────────────────────────────────────────────

def search_healthcare_facilities(
    district: str,
    state: str,
    facility_type: Optional[str] = None,
    department: Optional[str] = None,
    requires_emergency: bool = False,
    requires_24x7: bool = False,
    government_only: bool = False,
    max_results: int = 10,
) -> dict[str, Any]:
    """
    Tool: Search Healthcare Facilities
    -----------------------------------
    Searches the healthcare facility database by location, type, and capability.

    Args:
        district: Patient's district name
        state: Patient's state name
        facility_type: hospital | PHC | CHC | clinic | lab | pharmacy
        department: Required department (e.g., 'Cardiology', 'Orthopedics')
        requires_emergency: Filter for facilities with emergency care
        requires_24x7: Filter for 24×7 facilities
        government_only: Show only government facilities (free/subsidized)
        max_results: Maximum number of results to return

    Returns:
        dict with facilities list, total_found, search_criteria
    """
    db: Session = SessionLocal()
    try:
        query = db.query(HealthcareFacility).filter(
            HealthcareFacility.is_active == True,
            HealthcareFacility.state.ilike(f"%{state}%"),
        )

        # District filter — try exact match first, then broader
        district_matches = query.filter(
            HealthcareFacility.district.ilike(f"%{district}%")
        )
        if district_matches.count() == 0:
            app_logger.warning(f"No facilities found in district: {district}. Broadening to state level.")
        else:
            query = district_matches

        if facility_type:
            query = query.filter(HealthcareFacility.facility_type.ilike(f"%{facility_type}%"))
        if requires_emergency:
            query = query.filter(HealthcareFacility.has_emergency == True)
        if requires_24x7:
            query = query.filter(HealthcareFacility.is_24x7 == True)
        if government_only:
            query = query.filter(HealthcareFacility.is_government == True)

        facilities = query.order_by(
            HealthcareFacility.rating.desc(),
            HealthcareFacility.distance_km_from_block.asc()
        ).limit(max_results).all()

        # Department filter (in-memory, JSON array check)
        if department and facilities:
            dept_lower = department.lower()
            facilities = [
                f for f in facilities
                if any(dept_lower in str(d).lower() for d in (f.departments or []))
                   or any(dept_lower in str(s).lower() for s in (f.specialties or []))
            ] or facilities  # fallback: return all if no department match

        result = []
        for f in facilities:
            result.append({
                "id": f.id,
                "name": f.name,
                "type": f.facility_type,
                "district": f.district,
                "state": f.state,
                "address": f.address,
                "phone": f.phone,
                "is_government": f.is_government,
                "is_24x7": f.is_24x7,
                "has_emergency": f.has_emergency,
                "has_ambulance": f.has_ambulance,
                "has_icu": f.has_icu,
                "available_beds": f.available_beds,
                "departments": f.departments,
                "services": f.services,
                "distance_km": f.distance_km_from_block,
                "avg_wait_minutes": f.avg_wait_time_minutes,
                "consultation_fee": f.consultation_fee,
                "rating": f.rating,
                "accreditation": f.accreditation,
                "languages_spoken": f.languages_spoken,
            })

        app_logger.info(f"Facility search: district={district}, type={facility_type}, found={len(result)}")
        return {
            "success": True,
            "total_found": len(result),
            "facilities": result,
            "search_criteria": {
                "district": district, "state": state,
                "facility_type": facility_type, "department": department,
                "requires_emergency": requires_emergency,
                "requires_24x7": requires_24x7,
                "government_only": government_only,
            }
        }
    except Exception as e:
        app_logger.error(f"Facility search error: {e}")
        return {"success": False, "error": str(e), "facilities": []}
    finally:
        db.close()


# ─── Tool 2: Specialist Finder ───────────────────────────────────────────────

def find_specialists(
    specialty: str,
    district: str,
    state: str,
    telemedicine_only: bool = False,
    max_results: int = 8,
) -> dict[str, Any]:
    """
    Tool: Find Healthcare Specialists
    ------------------------------------
    Finds specialists/doctors by specialty and location.

    Args:
        specialty: Medical specialty (e.g., Cardiologist, Gynecologist, Pediatrician)
        district: Patient's district
        state: Patient's state
        telemedicine_only: Filter for telemedicine-capable specialists
        max_results: Maximum results

    Returns:
        dict with specialists list and availability information
    """
    db: Session = SessionLocal()
    try:
        query = (
            db.query(Specialist)
            .join(HealthcareFacility, Specialist.facility_id == HealthcareFacility.id)
            .filter(
                Specialist.is_active == True,
                Specialist.specialty.ilike(f"%{specialty}%"),
                HealthcareFacility.state.ilike(f"%{state}%"),
                HealthcareFacility.is_active == True,
            )
        )

        # Try district first, fall back to state-level
        district_query = query.filter(HealthcareFacility.district.ilike(f"%{district}%"))
        if district_query.count() > 0:
            query = district_query

        if telemedicine_only:
            query = query.filter(Specialist.telemedicine_available == True)

        specialists = query.limit(max_results).all()
        result = []
        for s in specialists:
            result.append({
                "id": s.id,
                "name": s.name,
                "specialty": s.specialty,
                "sub_specialty": s.sub_specialty,
                "qualification": s.qualification,
                "experience_years": s.experience_years,
                "facility_name": s.facility.name if s.facility else "N/A",
                "facility_district": s.facility.district if s.facility else district,
                "phone": s.phone,
                "available_days": s.available_days,
                "available_slots": s.available_slots,
                "consultation_fee": s.consultation_fee,
                "telemedicine_available": s.telemedicine_available,
                "languages": s.languages,
            })

        app_logger.info(f"Specialist search: specialty={specialty}, district={district}, found={len(result)}")
        return {"success": True, "total_found": len(result), "specialists": result}
    except Exception as e:
        app_logger.error(f"Specialist search error: {e}")
        return {"success": False, "error": str(e), "specialists": []}
    finally:
        db.close()


# ─── Tool 3: Emergency Escalation Detector ────────────────────────────────────

# Keywords that signal potentially urgent healthcare situations
EMERGENCY_KEYWORDS = [
    "chest pain", "heart attack", "stroke", "unconscious", "not breathing",
    "severe bleeding", "seizure", "convulsion", "difficulty breathing",
    "anaphylaxis", "allergic reaction", "snake bite", "poisoning",
    "trauma", "accident", "burn", "fracture with bleeding", "high fever child",
    "premature labor", "pregnancy emergency", "eclampsia", "diabetic coma",
    "mental health crisis", "suicide", "self harm",
    "face drooping", "arm weakness", "slurred speech",
    "sudden weakness", "vision loss sudden", "loss of consciousness",
]

def assess_urgency(symptoms_text: str, additional_context: str = "") -> dict[str, Any]:
    """
    Tool: Assess Urgency Level
    ----------------------------
    Keyword-based urgency screening for patient symptom descriptions.
    NOTE: This is a NAVIGATION SUPPORT TOOL only — not a medical diagnosis tool.

    Args:
        symptoms_text: Free-text description of patient symptoms/complaint
        additional_context: Any additional context from assessment agent

    Returns:
        dict with urgency_level, matched_keywords, recommended_action, disclaimer
    """
    text_lower = ((symptoms_text or "") + " " + (additional_context or "")).lower()

    matched = [kw for kw in EMERGENCY_KEYWORDS if kw in text_lower]

    if matched:
        urgency_level = "emergency"
        recommended_action = (
            f"IMMEDIATE ACTION REQUIRED. Call emergency services: "
            f"Ambulance {settings.AMBULANCE_SERVICE} | "
            f"Emergency {settings.EMERGENCY_HOTLINE}. "
            f"Do NOT delay seeking emergency care."
        )
        referral_type = "emergency_department"
    elif any(w in text_lower for w in ["severe", "very high", "unbearable", "cannot move", "vomiting blood"]):
        urgency_level = "high"
        recommended_action = "Seek care within the next few hours at the nearest hospital with emergency services."
        referral_type = "urgent_care"
    elif any(w in text_lower for w in ["fever", "pain", "cough", "vomiting", "diarrhea", "wound"]):
        urgency_level = "medium"
        recommended_action = "Schedule an appointment at a PHC, CHC, or clinic today or tomorrow."
        referral_type = "primary_care"
    else:
        urgency_level = "low"
        recommended_action = "Schedule a routine appointment at the nearest healthcare facility at your convenience."
        referral_type = "routine_care"

    return {
        "success": True,
        "urgency_level": urgency_level,
        "matched_emergency_keywords": matched,
        "recommended_action": recommended_action,
        "referral_type": referral_type,
        "disclaimer": (
            "⚠️ IMPORTANT DISCLAIMER: This assessment is a navigation support tool only. "
            "It is NOT a medical diagnosis and does NOT replace evaluation by a qualified "
            "healthcare professional. Always consult a doctor for medical advice."
        ),
        "emergency_contacts": {
            "ambulance": settings.AMBULANCE_SERVICE,
            "emergency": settings.EMERGENCY_HOTLINE,
            "health_helpline": settings.HEALTH_HELPLINE,
        }
    }


# ─── Tool 4: Department/Specialist Mapper ────────────────────────────────────

SYMPTOM_DEPARTMENT_MAP = {
    "heart": ["Cardiology", "Internal Medicine"],
    "chest": ["Cardiology", "Pulmonology", "Internal Medicine"],
    "lung": ["Pulmonology", "Internal Medicine"],
    "breathing": ["Pulmonology", "Emergency Medicine"],
    "stomach": ["Gastroenterology", "General Surgery", "Internal Medicine"],
    "liver": ["Gastroenterology", "Hepatology"],
    "kidney": ["Nephrology", "Urology"],
    "bone": ["Orthopedics", "Trauma Surgery"],
    "joint": ["Orthopedics", "Rheumatology"],
    "fracture": ["Orthopedics", "Emergency Medicine"],
    "skin": ["Dermatology", "General Medicine"],
    "eye": ["Ophthalmology"],
    "ear": ["ENT (Ear, Nose & Throat)"],
    "dental": ["Dentistry"],
    "brain": ["Neurology", "Neurosurgery"],
    "nerve": ["Neurology"],
    "mental": ["Psychiatry", "Psychology"],
    "depression": ["Psychiatry", "Psychology"],
    "child": ["Pediatrics"],
    "infant": ["Pediatrics", "Neonatology"],
    "pregnancy": ["Obstetrics & Gynecology"],
    "women": ["Obstetrics & Gynecology", "General Medicine"],
    "cancer": ["Oncology"],
    "diabetes": ["Endocrinology", "Internal Medicine"],
    "thyroid": ["Endocrinology"],
    "blood": ["Hematology", "Internal Medicine"],
    "urine": ["Urology", "Nephrology"],
    "surgical": ["General Surgery"],
    "fever": ["General Medicine", "Internal Medicine"],
    "tb": ["Pulmonology", "Infectious Disease"],
    "tuberculosis": ["Pulmonology", "Infectious Disease"],
    "malaria": ["Infectious Disease", "Internal Medicine"],
}

def map_symptoms_to_departments(symptoms_text: str) -> dict[str, Any]:
    """
    Tool: Map Symptoms to Departments
    ------------------------------------
    Maps patient symptom keywords to appropriate medical departments/specialties.

    Args:
        symptoms_text: Free-text patient complaint description

    Returns:
        dict with recommended_departments, confidence_scores
    """
    text_lower = symptoms_text.lower()
    department_scores: dict[str, int] = {}

    for keyword, departments in SYMPTOM_DEPARTMENT_MAP.items():
        if keyword in text_lower:
            for dept in departments:
                department_scores[dept] = department_scores.get(dept, 0) + 1

    if not department_scores:
        return {
            "success": True,
            "recommended_departments": ["General Medicine", "Internal Medicine"],
            "confidence": "low",
            "note": "No specific keyword match found. Recommending General Medicine as first point of contact.",
            "disclaimer": "This mapping is for navigation guidance only, not a clinical recommendation."
        }

    # Sort by score descending
    sorted_depts = sorted(department_scores.items(), key=lambda x: x[1], reverse=True)
    top_departments = [d[0] for d in sorted_depts[:3]]

    return {
        "success": True,
        "recommended_departments": top_departments,
        "all_matches": dict(sorted_depts),
        "confidence": "high" if sorted_depts[0][1] >= 2 else "medium",
        "disclaimer": "This mapping is for navigation guidance only, not a clinical recommendation."
    }


# ─── Tool 5: Appointment Availability Checker ────────────────────────────────

def check_appointment_availability(
    facility_id: str,
    specialist_id: Optional[str] = None,
    preferred_date: Optional[str] = None,
) -> dict[str, Any]:
    """
    Tool: Check Appointment Availability
    ---------------------------------------
    Checks appointment slots at a facility or with a specific specialist.

    Args:
        facility_id: Facility UUID
        specialist_id: Optional specialist UUID for specific doctor
        preferred_date: Optional preferred date (YYYY-MM-DD)

    Returns:
        dict with available_slots, booking_instructions, wait_time
    """
    db: Session = SessionLocal()
    try:
        facility = db.query(HealthcareFacility).filter_by(id=facility_id).first()
        if not facility:
            return {"success": False, "error": "Facility not found"}

        result = {
            "success": True,
            "facility_name": facility.name,
            "facility_phone": facility.phone,
            "is_walk_in_available": facility.is_24x7 or facility.has_emergency,
            "avg_wait_time_minutes": facility.avg_wait_time_minutes or 30,
        }

        if specialist_id:
            specialist = db.query(Specialist).filter_by(id=specialist_id).first()
            if specialist:
                result["specialist_name"] = specialist.name
                result["specialty"] = specialist.specialty
                result["available_days"] = specialist.available_days or []
                result["available_slots"] = specialist.available_slots or []
                result["consultation_fee"] = specialist.consultation_fee
                result["telemedicine_available"] = specialist.telemedicine_available
                result["booking_instruction"] = (
                    f"Call {specialist.phone or facility.phone} to book an appointment with "
                    f"Dr. {specialist.name} ({specialist.specialty})."
                )
        else:
            result["booking_instruction"] = (
                f"Call {facility.phone} or visit {facility.name} directly. "
                f"{'Walk-in available 24×7.' if facility.is_24x7 else 'Appointments recommended.'}"
            )

        return result
    except Exception as e:
        app_logger.error(f"Appointment check error: {e}")
        return {"success": False, "error": str(e)}
    finally:
        db.close()


# ─── Tool 6: Referral Letter Generator ───────────────────────────────────────

def generate_referral_summary(
    patient_context: str,
    referring_facility: str,
    target_facility: str,
    target_department: str,
    urgency_level: str,
    reason_for_referral: str,
    session_id: str,
) -> dict[str, Any]:
    """
    Tool: Generate Referral Navigation Summary
    --------------------------------------------
    Creates a structured navigation referral summary.
    NOTE: This is a navigation guidance document, NOT a clinical referral letter.
          A qualified healthcare professional must validate and issue formal referrals.

    Returns:
        dict with referral_summary text and metadata
    """
    referral_id = f"REF-{uuid.uuid4().hex[:8].upper()}"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    summary = f"""
NAVIGATION REFERRAL SUMMARY
============================
Reference ID  : {referral_id}
Generated At  : {timestamp}
Session ID    : {session_id}

PATIENT CONTEXT
---------------
{patient_context}

NAVIGATION DETAILS
------------------
Referring From  : {referring_facility}
Referred To     : {target_facility}
Department      : {target_department}
Urgency Level   : {urgency_level.upper()}
Reason          : {reason_for_referral}

DISCLAIMER
----------
⚠️ This is an AI-generated NAVIGATION SUPPORT SUMMARY only.
   It is NOT a clinical referral and does NOT replace a formal referral
   issued by a qualified healthcare professional.
   Please present this summary at the facility reception.
   The receiving facility will conduct their own clinical assessment.

EMERGENCY CONTACTS
------------------
Ambulance       : {settings.AMBULANCE_SERVICE}
Emergency       : {settings.EMERGENCY_HOTLINE}
Health Helpline : {settings.HEALTH_HELPLINE}
""".strip()

    app_logger.info(f"Referral generated: {referral_id} | Session: {session_id}")
    return {
        "success": True,
        "referral_id": referral_id,
        "referral_summary": summary,
        "urgency_level": urgency_level,
        "target_facility": target_facility,
        "target_department": target_department,
        "generated_at": timestamp,
    }


# ─── Tool 7: Navigation History Logger ───────────────────────────────────────

def log_navigation_step(
    session_id: str,
    step_number: int,
    agent_name: str,
    action_taken: str,
    result_summary: str,
    facilities_considered: list,
    recommended_facility_id: Optional[str],
    confidence_score: float,
    decision_factors: list,
    sources_used: list,
) -> dict[str, Any]:
    """
    Tool: Log Navigation History Step
    ------------------------------------
    Persists a navigation step to the database for audit trail and history.
    """
    db: Session = SessionLocal()
    try:
        step = NavigationHistory(
            session_id=session_id,
            step_number=step_number,
            agent_name=agent_name,
            action_taken=action_taken,
            result_summary=result_summary,
            facilities_considered=facilities_considered,
            recommended_facility_id=recommended_facility_id,
            confidence_score=confidence_score,
            decision_factors=decision_factors,
            sources_used=sources_used,
        )
        db.add(step)
        db.commit()
        return {"success": True, "step_id": step.id}
    except Exception as e:
        db.rollback()
        app_logger.error(f"Navigation log error: {e}")
        return {"success": False, "error": str(e)}
    finally:
        db.close()
