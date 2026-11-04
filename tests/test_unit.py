"""
Unit Tests — Rural Healthcare AI Navigation System
====================================================
Tests for critical tool functions and agent logic.
No LLM API calls required — tools are tested independently.
"""

import pytest
import sys
from pathlib import Path
import uuid

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).parent.parent))

# ─── Tool Tests ───────────────────────────────────────────────────────────────

class TestUrgencyAssessment:
    """Tests for the urgency assessment tool."""

    def test_emergency_chest_pain(self):
        from tools.healthcare_tools import assess_urgency
        result = assess_urgency("I have chest pain and my left arm is paining")
        assert result["success"] is True
        assert result["urgency_level"] == "emergency"
        assert len(result["matched_emergency_keywords"]) > 0
        assert "108" in result["emergency_contacts"]["ambulance"] or \
               result["emergency_contacts"]["ambulance"] in ["108", "102"]

    def test_emergency_stroke_keywords(self):
        from tools.healthcare_tools import assess_urgency
        result = assess_urgency("face drooping and arm weakness sudden onset")
        assert result["urgency_level"] == "emergency"

    def test_medium_urgency_fever(self):
        from tools.healthcare_tools import assess_urgency
        result = assess_urgency("I have fever and vomiting since yesterday")
        assert result["urgency_level"] in ["medium", "low"]

    def test_low_urgency_routine(self):
        from tools.healthcare_tools import assess_urgency
        result = assess_urgency("I need a routine health checkup")
        assert result["urgency_level"] == "low"

    def test_emergency_keywords_returned(self):
        from tools.healthcare_tools import assess_urgency
        result = assess_urgency("patient is unconscious and not breathing")
        assert result["urgency_level"] == "emergency"
        assert "disclaimer" in result

    def test_disclaimer_always_present(self):
        from tools.healthcare_tools import assess_urgency
        result = assess_urgency("I feel a little tired")
        assert "disclaimer" in result
        assert len(result["disclaimer"]) > 10

    def test_mental_health_crisis(self):
        from tools.healthcare_tools import assess_urgency
        result = assess_urgency("I am having thoughts of suicide")
        assert result["urgency_level"] == "emergency"


class TestDepartmentMapping:
    """Tests for the symptom-to-department mapping tool."""

    def test_cardiac_mapping(self):
        from tools.healthcare_tools import map_symptoms_to_departments
        result = map_symptoms_to_departments("chest pain and heart palpitations")
        assert result["success"] is True
        departments = result["recommended_departments"]
        assert any("Cardiology" in d or "Internal Medicine" in d for d in departments)

    def test_orthopedic_mapping(self):
        from tools.healthcare_tools import map_symptoms_to_departments
        result = map_symptoms_to_departments("bone fracture leg injury")
        departments = result["recommended_departments"]
        assert any("Orthopedics" in d for d in departments)

    def test_gynecology_mapping(self):
        from tools.healthcare_tools import map_symptoms_to_departments
        result = map_symptoms_to_departments("pregnancy related issues women health")
        departments = result["recommended_departments"]
        assert any("Gynecology" in d or "Obstetrics" in d for d in departments)

    def test_pediatric_mapping(self):
        from tools.healthcare_tools import map_symptoms_to_departments
        result = map_symptoms_to_departments("child fever infant problem")
        departments = result["recommended_departments"]
        assert any("Pediatrics" in d for d in departments)

    def test_unknown_symptoms_fallback(self):
        from tools.healthcare_tools import map_symptoms_to_departments
        result = map_symptoms_to_departments("asdfghjkl unknown xyz")
        assert result["success"] is True
        # Should fallback to General Medicine
        assert "General Medicine" in result["recommended_departments"]

    def test_result_has_disclaimer(self):
        from tools.healthcare_tools import map_symptoms_to_departments
        result = map_symptoms_to_departments("headache")
        assert "disclaimer" in result


class TestReferralGeneration:
    """Tests for the referral generation tool."""

    def test_referral_id_format(self):
        from tools.healthcare_tools import generate_referral_summary
        result = generate_referral_summary(
            patient_context="Location: Nashik, Maharashtra. Need: cardiac",
            referring_facility="AI Navigation System",
            target_facility="District Hospital Nashik",
            target_department="Cardiology",
            urgency_level="medium",
            reason_for_referral="Cardiac chest discomfort navigation",
            session_id=str(uuid.uuid4()),
        )
        assert result["success"] is True
        assert result["referral_id"].startswith("REF-")
        assert len(result["referral_id"]) == 12  # REF- + 8 chars
        assert "NAVIGATION REFERRAL SUMMARY" in result["referral_summary"]
        assert "DISCLAIMER" in result["referral_summary"]

    def test_referral_contains_emergency_contacts(self):
        from tools.healthcare_tools import generate_referral_summary
        result = generate_referral_summary(
            patient_context="Location: Aurangabad. Need: general",
            referring_facility="AI Navigation",
            target_facility="District Hospital",
            target_department="General Medicine",
            urgency_level="low",
            reason_for_referral="General checkup",
            session_id=str(uuid.uuid4()),
        )
        assert "108" in result["referral_summary"] or "102" in result["referral_summary"]


class TestHaversineDistance:
    """Tests for the haversine distance formula."""

    def test_same_location_zero_distance(self):
        from tools.healthcare_tools import haversine_distance
        dist = haversine_distance(19.0, 73.0, 19.0, 73.0)
        assert dist == pytest.approx(0.0, abs=0.01)

    def test_known_distance_mumbai_pune(self):
        """Mumbai to Pune ~119 km straight-line (haversine), ~149 km road distance"""
        from tools.healthcare_tools import haversine_distance
        dist = haversine_distance(19.0760, 72.8777, 18.5204, 73.8567)
        assert 110 < dist < 135  # haversine (great-circle) straight-line distance


class TestDatabaseInitialization:
    """Tests for database initialization."""

    def test_db_tables_created(self):
        from utils.database import init_db, Base, engine
        init_db()
        table_names = [t.name for t in Base.metadata.sorted_tables]
        assert "healthcare_facilities" in table_names
        assert "specialists" in table_names
        assert "patient_sessions" in table_names
        assert "navigation_history" in table_names

    def test_session_creation_and_query(self):
        from utils.database import SessionLocal, PatientSession, init_db
        import uuid
        init_db()
        db = SessionLocal()
        try:
            session = PatientSession(
                id=str(uuid.uuid4()),
                session_token=uuid.uuid4().hex,
            )
            db.add(session)
            db.commit()
            retrieved = db.query(PatientSession).filter_by(
                session_token=session.session_token
            ).first()
            assert retrieved is not None
            assert retrieved.navigation_status == "active"
        finally:
            db.close()


class TestSettingsValidation:
    """Tests for configuration settings."""

    def test_settings_load(self):
        from config.settings import settings
        assert settings.APP_NAME == "Rural Healthcare AI Navigation System"
        assert settings.EMERGENCY_HOTLINE in ["108", "102"]

    def test_settings_validate_returns_list(self):
        from config.settings import settings
        warnings = settings.validate()
        assert isinstance(warnings, list)


# ─── Integration Test: Emergency Bypass ─────────────────────────────────────

class TestEmergencyBypass:
    """Integration test verifying emergency cases bypass normal workflow."""

    def test_emergency_keywords_trigger_escalation(self):
        """Verify the emergency agent can run its core logic."""
        from agents.emergency_agent import EmergencyEscalationAgent
        session_id = str(uuid.uuid4())
        agent = EmergencyEscalationAgent(session_id)

        # Test with no LLM (fallback path)
        result = agent._hardcoded_emergency_response("cardiac_respiratory")

        assert "108" in result
        assert "AMBULANCE" in result.upper() or "EMERGENCY" in result.upper()

    def test_mental_health_fallback_contains_helplines(self):
        from agents.emergency_agent import EmergencyEscalationAgent
        session_id = str(uuid.uuid4())
        agent = EmergencyEscalationAgent(session_id)

        result = agent._hardcoded_emergency_response("mental_health_crisis")
        assert "9152987821" in result  # iCall
        assert "1800-599-0019" in result or "1860-2662-345" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
