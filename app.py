"""
Rural Healthcare AI Navigation System — Main Streamlit Application
===================================================================
Purpose: Production-ready Streamlit web interface for the Rural Healthcare
         Access & Referral Coordination System.

Architecture:
    Streamlit UI → SupervisorAgent → [Assessment | Discovery | RAG |
                                      Referral | Appointment | Emergency]
                                    → Tools → Database/RAG/LLM

Features:
  - Multi-agent conversational interface
  - Real-time urgency indicators
  - Facility comparison panel
  - Referral document download
  - Navigation history timeline
  - Emergency escalation banner
  - Government scheme information
  - Accessibility: high-contrast mode, font size control
  - Responsible AI disclaimers

Usage:
    streamlit run app.py

Dependencies:
    See requirements.txt
"""

import os
import sys
import uuid
import time
import json
from datetime import datetime
from pathlib import Path

import streamlit as st
from streamlit.components.v1 import html as st_html

# Ensure project root is in path
ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR))

# ─── Page Configuration ───────────────────────────────────────────────────────
st.set_page_config(
    page_title="Rural Healthcare AI Navigator",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": "https://nhm.gov.in",
        "Report a bug": None,
        "About": (
            "# Rural Healthcare AI Navigation System\n"
            "Version 1.0.0 | Powered by Agentic AI\n\n"
            "⚠️ **Disclaimer**: This is a navigation support tool only. "
            "It does NOT provide medical diagnoses or replace healthcare professionals.\n\n"
            "**Emergency**: Call 108 | Health Helpline: 104"
        )
    }
)

# ─── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Main theme colors */
    :root {
        --primary-green: #1a7f4b;
        --secondary-blue: #1565C0;
        --emergency-red: #c62828;
        --warning-amber: #e65100;
        --success-green: #2e7d32;
        --bg-light: #f8f9fa;
        --card-border: #dee2e6;
    }

    /* Header */
    .main-header {
        background: linear-gradient(135deg, #1a7f4b 0%, #1565C0 100%);
        color: white;
        padding: 1.2rem 2rem;
        border-radius: 12px;
        margin-bottom: 1rem;
        text-align: center;
    }
    .main-header h1 { font-size: 1.8rem; margin: 0; color: white; }
    .main-header p { margin: 0.3rem 0 0; opacity: 0.9; font-size: 0.9rem; }

    /* Chat bubbles */
    .chat-user {
        background: #e3f2fd;
        border-left: 4px solid #1565C0;
        padding: 0.8rem 1rem;
        border-radius: 0 12px 12px 12px;
        margin: 0.5rem 0;
        max-width: 85%;
        margin-left: auto;
        color: #0d2b4e !important;
    }
    .chat-user * { color: #0d2b4e !important; }
    .chat-assistant {
        background: #f1f8e9;
        border-left: 4px solid #1a7f4b;
        padding: 0.8rem 1rem;
        border-radius: 12px 12px 12px 0;
        margin: 0.5rem 0;
        max-width: 90%;
        color: #1b3a1f !important;
    }
    .chat-assistant * { color: #1b3a1f !important; }
    .chat-emergency {
        background: #ffebee;
        border-left: 4px solid #c62828;
        padding: 0.8rem 1rem;
        border-radius: 12px;
        margin: 0.5rem 0;
        border: 2px solid #c62828;
        color: #4a0000 !important;
    }
    .chat-emergency * { color: #4a0000 !important; }

    /* Urgency badges */
    .badge-low { background: #e8f5e9; color: #2e7d32; padding: 2px 10px; border-radius: 12px; font-size: 0.8rem; font-weight: bold; }
    .badge-medium { background: #fff3e0; color: #e65100; padding: 2px 10px; border-radius: 12px; font-size: 0.8rem; font-weight: bold; }
    .badge-high { background: #fce4ec; color: #880e4f; padding: 2px 10px; border-radius: 12px; font-size: 0.8rem; font-weight: bold; }
    .badge-emergency { background: #c62828; color: white; padding: 2px 12px; border-radius: 12px; font-size: 0.85rem; font-weight: bold; animation: pulse 1.5s infinite; }
    @keyframes pulse { 0%,100%{opacity:1;} 50%{opacity:0.6;} }

    /* Emergency banner */
    .emergency-banner {
        background: #c62828;
        color: white;
        padding: 1rem 1.5rem;
        border-radius: 8px;
        margin: 0.5rem 0;
        font-size: 1.1rem;
        font-weight: bold;
        text-align: center;
    }

    /* Facility card */
    .facility-card {
        background: white;
        border: 1px solid var(--card-border);
        border-radius: 10px;
        padding: 1rem;
        margin: 0.5rem 0;
        box-shadow: 0 1px 4px rgba(0,0,0,0.08);
    }
    .facility-card.top-pick {
        border: 2px solid var(--primary-green);
        background: #f0fff4;
    }

    /* Workflow tracker */
    .workflow-step { padding: 0.4rem 0; display: flex; align-items: center; }
    .workflow-step .icon { margin-right: 8px; font-size: 1.1rem; }
    .step-done { color: #2e7d32; font-weight: 600; }
    .step-active { color: #1565C0; font-weight: 600; }
    .step-pending { color: #9e9e9e; }

    /* Disclaimer box */
    .disclaimer-box {
        background: #fff8e1;
        border: 1px solid #ffc107;
        border-radius: 8px;
        padding: 0.8rem;
        font-size: 0.82rem;
        color: #5d4037;
        margin: 0.5rem 0;
    }

    /* Referral summary */
    .referral-box {
        background: #e8f5e9;
        border: 1px solid #4caf50;
        border-radius: 8px;
        padding: 1rem;
        font-family: monospace;
        font-size: 0.82rem;
        white-space: pre-wrap;
    }

    /* Source citation */
    .source-tag {
        display: inline-block;
        background: #e3f2fd;
        border-radius: 4px;
        padding: 2px 6px;
        font-size: 0.75rem;
        color: #1565C0;
        margin: 2px;
    }

    /* Quick action buttons */
    .stButton > button {
        border-radius: 20px;
        font-weight: 600;
        transition: all 0.2s;
    }

    /* Hide Streamlit default footer */
    footer { visibility: hidden; }
    #MainMenu { visibility: hidden; }
</style>
""", unsafe_allow_html=True)


# ─── Session State Initialization ────────────────────────────────────────────

def init_session_state():
    """Initialize all Streamlit session state variables."""
    defaults = {
        "supervisor": None,
        "messages": [],                    # list of (role, text, metadata)
        "session_id": str(uuid.uuid4()),
        "initialized": False,
        "emergency_active": False,
        "current_stage": "greeting",
        "workflow_summary": {},
        "top_facility": None,
        "referral_text": None,
        "referral_id": None,
        "show_referral": False,
        "show_knowledge_panel": False,
        "high_contrast": False,
        "district": "",
        "state_name": "",
        "government_only": False,
        "api_configured": False,
        "system_ready": False,
        "init_error": None,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def initialize_system():
    """Lazy initialization of SupervisorAgent."""
    if st.session_state.supervisor is not None:
        return True
    try:
        from agents.supervisor_agent import SupervisorAgent
        from config.settings import settings
        warnings = settings.validate()
        if warnings:
            st.session_state.init_error = "\n".join(warnings)
        st.session_state.supervisor = SupervisorAgent()
        st.session_state.system_ready = True
        st.session_state.initialized = True
        # Seed database with sample data
        _seed_sample_data()
        return True
    except Exception as e:
        st.session_state.init_error = str(e)
        st.session_state.system_ready = False
        return False


def _seed_sample_data():
    """Seed database with sample healthcare facilities for demonstration."""
    from utils.database import SessionLocal, HealthcareFacility, Specialist
    db = SessionLocal()
    try:
        # Only seed if empty
        if db.query(HealthcareFacility).count() > 0:
            return

        facilities_data = [
            {
                "id": str(uuid.uuid4()),
                "name": "District Government Hospital Nashik",
                "facility_type": "hospital",
                "district": "Nashik",
                "state": "Maharashtra",
                "address": "Old Agra Rd, Nashik, Maharashtra 422001",
                "phone": "0253-2577750",
                "is_government": True,
                "is_24x7": True,
                "has_emergency": True,
                "has_ambulance": True,
                "has_icu": True,
                "bed_count": 500,
                "available_beds": 120,
                "departments": ["General Medicine", "Surgery", "Orthopedics", "Gynecology", "Pediatrics", "Cardiology", "ENT", "Ophthalmology"],
                "specialties": ["Emergency Medicine", "ICU"],
                "services": ["OPD", "IPD", "Laboratory", "Radiology", "Blood Bank", "Dialysis"],
                "languages_spoken": ["Hindi", "Marathi", "English"],
                "distance_km_from_block": 12.5,
                "avg_wait_time_minutes": 45,
                "consultation_fee": 0.0,
                "rating": 4.1,
                "accreditation": "NABH",
                "is_active": True,
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Primary Health Centre Igatpuri",
                "facility_type": "PHC",
                "district": "Nashik",
                "state": "Maharashtra",
                "address": "Main Road, Igatpuri, Nashik District",
                "phone": "02553-244001",
                "is_government": True,
                "is_24x7": False,
                "has_emergency": False,
                "has_ambulance": False,
                "has_icu": False,
                "bed_count": 6,
                "available_beds": 3,
                "departments": ["General Medicine", "Maternal & Child Health"],
                "specialties": [],
                "services": ["OPD", "Immunization", "ANC", "Family Planning", "Free Medicines"],
                "languages_spoken": ["Hindi", "Marathi"],
                "distance_km_from_block": 3.2,
                "avg_wait_time_minutes": 20,
                "consultation_fee": 0.0,
                "rating": 3.8,
                "accreditation": None,
                "is_active": True,
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Community Health Centre Dindori",
                "facility_type": "CHC",
                "district": "Nashik",
                "state": "Maharashtra",
                "address": "Dindori Road, Nashik, Maharashtra",
                "phone": "02557-233500",
                "is_government": True,
                "is_24x7": True,
                "has_emergency": True,
                "has_ambulance": True,
                "has_icu": False,
                "bed_count": 30,
                "available_beds": 8,
                "departments": ["General Medicine", "Surgery", "Gynecology", "Pediatrics"],
                "specialties": ["Obstetrics"],
                "services": ["OPD", "IPD", "Laboratory", "X-Ray", "Ambulance"],
                "languages_spoken": ["Hindi", "Marathi"],
                "distance_km_from_block": 7.8,
                "avg_wait_time_minutes": 30,
                "consultation_fee": 0.0,
                "rating": 3.9,
                "accreditation": None,
                "is_active": True,
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Ruby Hall Clinic Nashik",
                "facility_type": "hospital",
                "district": "Nashik",
                "state": "Maharashtra",
                "address": "Gangapur Road, Nashik, Maharashtra 422005",
                "phone": "0253-6612345",
                "is_government": False,
                "is_24x7": True,
                "has_emergency": True,
                "has_ambulance": True,
                "has_icu": True,
                "bed_count": 200,
                "available_beds": 35,
                "departments": ["Cardiology", "Neurology", "Oncology", "Orthopedics", "Nephrology", "Gastroenterology"],
                "specialties": ["Cardiac Surgery", "Neurosurgery"],
                "services": ["OPD", "IPD", "ICU", "Cath Lab", "MRI", "CT Scan", "NICU"],
                "languages_spoken": ["Hindi", "Marathi", "English"],
                "distance_km_from_block": 18.0,
                "avg_wait_time_minutes": 20,
                "consultation_fee": 500.0,
                "rating": 4.6,
                "accreditation": "NABH",
                "is_active": True,
            },
            {
                "id": str(uuid.uuid4()),
                "name": "District Government Hospital Aurangabad",
                "facility_type": "hospital",
                "district": "Aurangabad",
                "state": "Maharashtra",
                "address": "Paithan Road, Aurangabad, Maharashtra 431001",
                "phone": "0240-2334500",
                "is_government": True,
                "is_24x7": True,
                "has_emergency": True,
                "has_ambulance": True,
                "has_icu": True,
                "bed_count": 600,
                "available_beds": 150,
                "departments": ["General Medicine", "Surgery", "Orthopedics", "Gynecology", "Pediatrics", "Psychiatry", "Dermatology"],
                "specialties": ["Trauma Surgery"],
                "services": ["OPD", "IPD", "ICU", "Laboratory", "Blood Bank", "Dialysis", "Physiotherapy"],
                "languages_spoken": ["Hindi", "Marathi", "Urdu", "English"],
                "distance_km_from_block": 8.0,
                "avg_wait_time_minutes": 60,
                "consultation_fee": 0.0,
                "rating": 4.0,
                "accreditation": "NABH",
                "is_active": True,
            },
        ]

        for f_data in facilities_data:
            facility = HealthcareFacility(**f_data)
            db.add(facility)

        # Add sample specialists
        db.flush()
        # Get facility IDs
        facilities = db.query(HealthcareFacility).all()
        if facilities:
            specialists_data = [
                {
                    "id": str(uuid.uuid4()),
                    "facility_id": facilities[0].id,
                    "name": "Dr. Priya Sharma",
                    "specialty": "Cardiology",
                    "qualification": "MBBS, MD (Medicine), DM (Cardiology)",
                    "experience_years": 12,
                    "phone": "0253-2577750",
                    "available_days": ["Monday", "Wednesday", "Friday"],
                    "available_slots": ["09:00-12:00", "14:00-16:00"],
                    "consultation_fee": 0.0,
                    "telemedicine_available": True,
                    "languages": ["Hindi", "Marathi", "English"],
                    "is_active": True,
                },
                {
                    "id": str(uuid.uuid4()),
                    "facility_id": facilities[0].id,
                    "name": "Dr. Ramesh Patil",
                    "specialty": "Orthopedics",
                    "qualification": "MBBS, MS (Orthopedics)",
                    "experience_years": 8,
                    "phone": "0253-2577750",
                    "available_days": ["Tuesday", "Thursday", "Saturday"],
                    "available_slots": ["10:00-13:00"],
                    "consultation_fee": 0.0,
                    "telemedicine_available": False,
                    "languages": ["Hindi", "Marathi"],
                    "is_active": True,
                },
                {
                    "id": str(uuid.uuid4()),
                    "facility_id": facilities[3].id if len(facilities) > 3 else facilities[0].id,
                    "name": "Dr. Anjali Desai",
                    "specialty": "Gynecology",
                    "qualification": "MBBS, MS (Obstetrics & Gynecology)",
                    "experience_years": 15,
                    "phone": "0253-6612345",
                    "available_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
                    "available_slots": ["09:00-12:00", "17:00-19:00"],
                    "consultation_fee": 500.0,
                    "telemedicine_available": True,
                    "languages": ["Hindi", "Marathi", "English"],
                    "is_active": True,
                },
            ]
            for s_data in specialists_data:
                specialist = Specialist(**s_data)
                db.add(specialist)

        db.commit()
    except Exception as e:
        db.rollback()
    finally:
        db.close()


# ─── UI Components ────────────────────────────────────────────────────────────

def render_header():
    """Render the main header banner."""
    st.markdown("""
    <div class="main-header">
        <h1>🏥 Rural Healthcare AI Navigation System</h1>
        <p>Helping patients find the right healthcare facility, specialist, and pathway</p>
        <p style="font-size:0.78rem; opacity:0.8;">
            ⚠️ Navigation Support Only — NOT a medical diagnosis system | 
            Emergency: <strong>108</strong> | Health Helpline: <strong>104</strong>
        </p>
    </div>
    """, unsafe_allow_html=True)


def render_emergency_banner():
    """Show prominent emergency banner when emergency is active."""
    if st.session_state.emergency_active:
        st.markdown("""
        <div class="emergency-banner">
            🚨 EMERGENCY DETECTED — Call <strong>108</strong> (Ambulance) IMMEDIATELY!
            &nbsp;|&nbsp; Health Helpline: <strong>104</strong>
        </div>
        """, unsafe_allow_html=True)


def render_disclaimer():
    """Render responsible AI disclaimer."""
    st.markdown("""
    <div class="disclaimer-box">
        <strong>⚠️ Important Disclaimer:</strong> This AI system is a <strong>navigation support tool only</strong>.
        It does NOT provide medical diagnoses, prescribe medications, or replace qualified healthcare professionals.
        Always consult a licensed doctor for medical decisions. For emergencies, call <strong>108</strong> immediately.
    </div>
    """, unsafe_allow_html=True)


def render_sidebar():
    """Render the sidebar with controls and workflow tracker."""
    with st.sidebar:
        st.markdown("## 🗺️ Navigation Panel")

        # ── Emergency Quick Access ──
        st.error("🚨 **Emergency?** Call **108** now!")

        st.markdown("---")

        # ── Location Input ──
        st.markdown("### 📍 Your Location")
        district = st.text_input(
            "District",
            value=st.session_state.district,
            placeholder="e.g., Nashik, Pune, Aurangabad",
            key="district_input"
        )
        state_name = st.selectbox(
            "State",
            options=["", "Maharashtra", "Karnataka", "Tamil Nadu", "Rajasthan",
                     "Uttar Pradesh", "Madhya Pradesh", "Gujarat", "Bihar",
                     "West Bengal", "Andhra Pradesh", "Telangana", "Kerala",
                     "Odisha", "Punjab", "Haryana", "Jharkhand", "Chhattisgarh",
                     "Assam", "Uttarakhand", "Himachal Pradesh"],
            index=0,
            key="state_input"
        )

        if st.button("📍 Update Location", use_container_width=True):
            if district and state_name:
                st.session_state.district = district
                st.session_state.state_name = state_name
                if st.session_state.supervisor:
                    st.session_state.supervisor.handle_user_location_update(district, state_name)
                st.success(f"✅ Location set: {district}, {state_name}")
            else:
                st.warning("Please enter both district and state.")

        st.markdown("---")

        # ── Preferences ──
        st.markdown("### ⚙️ Preferences")
        govt_only = st.checkbox(
            "🏛️ Government facilities only (free care)",
            value=st.session_state.government_only,
            key="govt_only_checkbox"
        )
        if govt_only != st.session_state.government_only:
            st.session_state.government_only = govt_only
            if st.session_state.supervisor:
                st.session_state.supervisor.set_government_only(govt_only)

        st.markdown("---")

        # ── Workflow Progress ──
        st.markdown("### 📋 Workflow Progress")
        if st.session_state.supervisor:
            summary = st.session_state.supervisor.get_workflow_summary()
            stages = [
                ("Assessment", "assessment", "🔍"),
                ("Facility Discovery", "discovery", "🏥"),
                ("Referral Plan", "referral", "📄"),
                ("Appointment", "appointment", "📅"),
            ]
            for stage_label, stage_key, icon in stages:
                is_done = stage_key in summary.get("workflow_steps", [])
                is_active = summary.get("stage", "").startswith(stage_key)
                css_class = "step-done" if is_done else ("step-active" if is_active else "step-pending")
                status = "✅" if is_done else ("🔄" if is_active else "⏳")
                st.markdown(
                    f'<div class="workflow-step {css_class}">{icon} {status} {stage_label}</div>',
                    unsafe_allow_html=True
                )

            if summary.get("emergency_triggered"):
                st.error("🚨 Emergency escalation triggered")
            if summary.get("referral_id"):
                st.success(f"✅ Referral: {summary['referral_id']}")

        st.markdown("---")

        # ── Quick Actions ──
        st.markdown("### 🔧 Quick Actions")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 New Session", use_container_width=True):
                _reset_session()
                st.rerun()
        with col2:
            if st.button("📚 Knowledge", use_container_width=True):
                if st.session_state.supervisor:
                    st.session_state.supervisor.trigger_knowledge_mode()
                st.session_state.show_knowledge_panel = True
                st.rerun()

        # ── Emergency Contacts ──
        st.markdown("---")
        st.markdown("### 📞 Emergency Contacts")
        st.markdown("""
        | Service | Number |
        |---------|--------|
        | 🚑 Ambulance | **102 / 108** |
        | ⚕️ Health Helpline | **104** |
        | 🚔 Police | **100** |
        | 🔥 Fire | **101** |
        | 🧠 Mental Health | **9152987821** |
        """)


def render_chat_message(role: str, text: str, metadata: dict = None):
    """Render a single chat message with appropriate styling."""
    metadata = metadata or {}
    urgency = metadata.get("urgency_level", "low")
    is_emergency = metadata.get("emergency", False) or urgency == "emergency"

    if role == "user":
        st.markdown(f'<div class="chat-user">👤 <strong>You</strong><br>{text}</div>',
                   unsafe_allow_html=True)
    elif role == "assistant":
        if is_emergency:
            st.markdown(f'<div class="chat-emergency">🚨 <strong>Emergency Response</strong><br>{text}</div>',
                       unsafe_allow_html=True)
        else:
            agent_name = metadata.get("agent", "Healthcare AI")
            agent_icon = {
                "PatientAssessmentAgent": "🔍",
                "FacilityDiscoveryAgent": "🏥",
                "ReferralPlanningAgent": "📄",
                "RAGKnowledgeAgent": "📚",
                "AppointmentCoordinationAgent": "📅",
                "EmergencyEscalationAgent": "🚨",
                "SupervisorAgent": "🤖",
            }.get(agent_name, "🤖")
            st.markdown(
                f'<div class="chat-assistant">{agent_icon} <strong>{agent_name.replace("Agent", " Agent")}</strong><br>{text}</div>',
                unsafe_allow_html=True
            )

        # Show sources if RAG result
        if metadata.get("sources"):
            sources_html = "".join(
                f'<span class="source-tag">📄 {s}</span>' for s in metadata["sources"]
            )
            st.markdown(f'<div style="margin-top:4px;">{sources_html}</div>', unsafe_allow_html=True)

        # Show decision factors if available
        if metadata.get("decision_factors") and not is_emergency:
            with st.expander("💡 Why this recommendation?", expanded=False):
                for factor in metadata["decision_factors"]:
                    st.markdown(f"• {factor}")


def render_facility_panel(facilities: list, top_facility: dict = None):
    """Render discovered facilities in a card grid."""
    if not facilities:
        return
    st.markdown("### 🏥 Discovered Healthcare Facilities")
    for i, facility in enumerate(facilities[:5]):
        is_top = facility.get("id") == (top_facility.get("id") if top_facility else None)
        card_class = "facility-card top-pick" if is_top else "facility-card"
        top_badge = "🏆 TOP RECOMMENDATION" if is_top else ""
        govt_badge = "🏛️ Government (Free)" if facility.get("is_government") else "🏥 Private"
        emergency_badge = "🚨 Emergency" if facility.get("has_emergency") else ""
        rating = f"⭐ {facility.get('rating', 'N/A')}" if facility.get("rating") else ""

        st.markdown(f"""
        <div class="{card_class}">
            <strong>{top_badge} {facility.get('name', 'N/A')}</strong><br>
            <small>{govt_badge} | {facility.get('type', '').upper()} | {emergency_badge} {rating}</small><br>
            <small>📍 {facility.get('district', 'N/A')} | 📞 {facility.get('phone', 'N/A')}</small><br>
            <small>🛏️ {facility.get('available_beds', 'N/A')} beds | ⏱️ {facility.get('avg_wait_minutes', 'N/A')} min wait</small>
        </div>
        """, unsafe_allow_html=True)


def render_referral_panel():
    """Render referral summary with download button."""
    if st.session_state.referral_text:
        st.markdown("### 📄 Navigation Referral Summary")
        st.markdown(
            f'<div class="referral-box">{st.session_state.referral_text}</div>',
            unsafe_allow_html=True
        )
        st.download_button(
            label="⬇️ Download Referral Summary",
            data=st.session_state.referral_text,
            file_name=f"referral_{st.session_state.referral_id or 'summary'}.txt",
            mime="text/plain",
            use_container_width=True,
        )


def _reset_session():
    """Reset session state for a new navigation session."""
    keys_to_keep = {"high_contrast"}
    for key in list(st.session_state.keys()):
        if key not in keys_to_keep:
            del st.session_state[key]


# ─── Main Application ─────────────────────────────────────────────────────────

def main():
    init_session_state()
    render_header()
    render_emergency_banner()

    # ── Initialize system ────────────────────────────────────────────────
    if not st.session_state.initialized:
        with st.spinner("🔄 Initializing Healthcare AI System..."):
            success = initialize_system()
        if not success:
            st.error(
                f"⚠️ System initialization failed: {st.session_state.init_error or 'Unknown error'}\n\n"
                "Please check your API key configuration in the `.env` file."
            )
            with st.expander("🔧 Configuration Help"):
                st.code("""
# .env file setup
GOOGLE_API_KEY=your_google_gemini_api_key    # OR
OPENAI_API_KEY=your_openai_api_key           # OR
GROQ_API_KEY=your_groq_api_key               # (free tier)

LLM_PROVIDER=google  # google | openai | groq
LLM_MODEL=gemini-1.5-flash
                """)
            st.info(
                "💡 Get a free Google Gemini API key at: https://ai.google.dev\n\n"
                "For emergency health information: Call **104** (National Health Helpline)"
            )
            return

    if st.session_state.init_error:
        st.warning(f"⚠️ Configuration Warning: {st.session_state.init_error}")

    render_sidebar()
    render_disclaimer()

    # ── Main Content Tabs ────────────────────────────────────────────────
    tab_chat, tab_facilities, tab_referral, tab_info = st.tabs([
        "💬 Navigation Chat", "🏥 Facilities", "📄 Referral", "ℹ️ About"
    ])

    with tab_chat:
        _render_chat_tab()

    with tab_facilities:
        _render_facilities_tab()

    with tab_referral:
        _render_referral_tab()

    with tab_info:
        _render_info_tab()


def _render_chat_tab():
    """Render the main chat interface."""
    supervisor = st.session_state.supervisor

    # Greeting message on first load
    if not st.session_state.messages:
        greeting = (
            "👋 **Welcome to the Rural Healthcare AI Navigation System!**\n\n"
            "I'm here to help you find the right healthcare facility, specialist, "
            "or referral pathway in your area.\n\n"
            "**How can I help you today?**\n\n"
            "You can tell me:\n"
            "- Your location (district and state)\n"
            "- What healthcare service you need\n"
            "- Any symptoms or health concerns (for navigation purposes only)\n\n"
            "Example: *'I'm in Nashik, Maharashtra and I need to see a cardiologist'*\n\n"
            "⚠️ **Note**: If this is a medical emergency, please call **108** immediately!"
        )
        st.session_state.messages.append(("assistant", greeting, {}))

    # Display chat history
    chat_container = st.container()
    with chat_container:
        for role, text, metadata in st.session_state.messages:
            render_chat_message(role, text, metadata)

    # ── Quick suggestion buttons ──
    if len(st.session_state.messages) <= 2:
        st.markdown("**Quick Start:**")
        cols = st.columns(3)
        suggestions = [
            "I need to find a government hospital in my district",
            "What is Ayushman Bharat PMJAY scheme?",
            "I need an appointment with a gynecologist",
        ]
        for i, (col, sug) in enumerate(zip(cols, suggestions)):
            with col:
                if st.button(sug, key=f"suggestion_{i}", use_container_width=True):
                    _handle_chat_input(sug)
                    st.rerun()

    # ── Input area ──
    st.markdown("---")
    col_input, col_send = st.columns([5, 1])
    with col_input:
        user_input = st.chat_input(
            "Describe your healthcare need or ask a question... (Emergency? Call 108 now!)"
        )

    if user_input:
        _handle_chat_input(user_input)
        st.rerun()


def _handle_chat_input(user_message: str):
    """Process user message through the supervisor agent."""
    supervisor = st.session_state.supervisor
    if not supervisor:
        return

    # Add user message to chat
    st.session_state.messages.append(("user", user_message, {}))

    # Process through supervisor
    with st.spinner("🤖 Processing your request..."):
        try:
            result = supervisor.process_message(user_message)
        except Exception as e:
            result = {
                "response_text": (
                    f"I encountered a technical issue. Please try again.\n\n"
                    f"For immediate help: Call **104** (Health Helpline) or **108** (Ambulance).\n\n"
                    f"Technical details: {str(e)}"
                ),
                "agent": "SupervisorAgent",
                "emergency": False,
            }

    # Update session state
    st.session_state.emergency_active = result.get("emergency", False)
    st.session_state.current_stage = result.get("stage", "assessment")
    st.session_state.workflow_summary = result.get("workflow_summary", {})

    # Cache top facility and referral
    if result.get("top_recommendation"):
        st.session_state.top_facility = result["top_recommendation"]
    if result.get("referral_summary"):
        st.session_state.referral_text = result.get("referral_summary")
        st.session_state.referral_id = result.get("referral_id")

    # Add assistant response to chat
    metadata = {
        "agent": result.get("agent", "SupervisorAgent"),
        "urgency_level": result.get("urgency_level", "low"),
        "emergency": result.get("emergency", False),
        "decision_factors": result.get("decision_factors", []),
        "sources": result.get("sources", []),
        "human_review_required": result.get("human_review_required", False),
    }
    st.session_state.messages.append(("assistant", result["response_text"], metadata))


def _render_facilities_tab():
    """Render the facilities comparison tab."""
    st.markdown("## 🏥 Healthcare Facility Discovery")

    if st.session_state.supervisor:
        facilities = st.session_state.supervisor.discovery_agent.state.get("discovered_facilities", [])
        top_facility = st.session_state.top_facility

        if facilities:
            render_facility_panel(facilities, top_facility)
            if top_facility:
                st.markdown("### 🏆 Top Recommendation Details")
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Facility Name", top_facility.get("name", "N/A"))
                    st.metric("Type", top_facility.get("type", "N/A").upper())
                    st.metric("Government", "Yes ✅" if top_facility.get("is_government") else "No")
                with col2:
                    st.metric("Available Beds", top_facility.get("available_beds", "N/A"))
                    st.metric("Distance", f"{top_facility.get('distance_km', 'N/A')} km")
                    st.metric("Rating", f"{top_facility.get('rating', 'N/A')} / 5.0")

                st.markdown(f"📞 **Phone**: {top_facility.get('phone', 'N/A')}")
                st.markdown(f"📍 **Address**: {top_facility.get('address', 'N/A')}")

                if top_facility.get("departments"):
                    st.markdown("**Available Departments:**")
                    dept_cols = st.columns(3)
                    for i, dept in enumerate(top_facility["departments"]):
                        dept_cols[i % 3].markdown(f"• {dept}")
        else:
            st.info(
                "💡 No facilities discovered yet. Start a navigation session in the Chat tab "
                "and provide your location to discover nearby healthcare facilities."
            )

        # Manual search
        st.markdown("---")
        st.markdown("### 🔍 Manual Facility Search")
        search_col1, search_col2, search_col3 = st.columns(3)
        with search_col1:
            search_district = st.text_input("District", placeholder="e.g., Nashik")
        with search_col2:
            search_state = st.selectbox("State", ["Maharashtra", "Karnataka", "Tamil Nadu", "Uttar Pradesh", "Gujarat"])
        with search_col3:
            search_type = st.selectbox("Facility Type", ["Any", "hospital", "PHC", "CHC", "clinic"])

        if st.button("🔍 Search Facilities", use_container_width=True):
            if search_district:
                from tools.healthcare_tools import search_healthcare_facilities
                with st.spinner("Searching..."):
                    result = search_healthcare_facilities(
                        district=search_district,
                        state=search_state,
                        facility_type=None if search_type == "Any" else search_type,
                        max_results=10,
                    )
                if result.get("facilities"):
                    render_facility_panel(result["facilities"])
                else:
                    st.warning("No facilities found for this search.")
    else:
        st.warning("System not initialized. Please refresh the page.")


def _render_referral_tab():
    """Render the referral summary tab."""
    st.markdown("## 📄 Navigation Referral Summary")

    if st.session_state.referral_text:
        render_referral_panel()
        st.markdown("---")
        st.info(
            "**Next Steps:**\n"
            "1. Download or screenshot this referral summary\n"
            "2. Present it at the facility reception\n"
            "3. Carry your Aadhaar card and health card\n"
            "4. The facility will conduct their own clinical assessment\n\n"
            "⚠️ This is a NAVIGATION summary only, not a clinical referral."
        )
    else:
        st.info(
            "📋 Your referral summary will appear here after completing the "
            "navigation workflow in the Chat tab."
        )
        st.markdown("### 📝 What a Referral Summary Includes:")
        st.markdown("""
        - Reference ID for tracking
        - Your location and healthcare need
        - Recommended facility and department
        - Urgency level assessment
        - Step-by-step action plan
        - Documents to carry
        - Government scheme eligibility
        - Emergency contact numbers
        """)


def _render_info_tab():
    """Render the about/information tab."""
    st.markdown("## ℹ️ About This System")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        ### 🤖 AI Agents in this System

        | Agent | Role |
        |-------|------|
        | 🔍 Assessment Agent | Understands your healthcare need |
        | 🏥 Discovery Agent | Finds nearby healthcare facilities |
        | 📄 Referral Agent | Creates navigation referral plan |
        | 📚 RAG Knowledge Agent | Answers healthcare questions |
        | 📅 Appointment Agent | Guides on appointment booking |
        | 🚨 Emergency Agent | Handles urgent situations |
        | 🎯 Supervisor Agent | Orchestrates all agents |
        """)

    with col2:
        st.markdown("""
        ### 🏛️ Government Health Schemes

        **Ayushman Bharat PMJAY**
        - Free treatment up to ₹5 lakh/year
        - For BPL & low-income families
        - 1,400+ treatment packages

        **NHM Free Services**
        - Free medicines at PHC/CHC/District Hospitals
        - Free diagnostics under NHM
        - Free maternal & child health services

        **ASHA/ANM Services**
        - Community health worker support
        - Free home visits
        - Referral coordination
        """)

    st.markdown("---")
    st.markdown("""
    ### ⚠️ Responsible AI Disclaimer

    This system has been designed with the following principles:
    - **No diagnosis**: We do NOT diagnose any medical condition
    - **No prescription**: We do NOT recommend any medicines
    - **Navigation only**: We help you find the right facility and pathway
    - **Human oversight**: All urgent cases are flagged for human review
    - **Privacy**: No personal health information is stored without consent
    - **Transparency**: Every recommendation includes decision factors
    - **Emergency first**: Emergency situations are always escalated immediately
    """)

    st.markdown("---")
    st.markdown("""
    ### 📊 Technology Stack
    - **AI Framework**: LangChain + Multi-Agent Architecture
    - **LLM**: Google Gemini (preferred) / OpenAI / Groq
    - **RAG**: ChromaDB + Google Embedding
    - **Database**: SQLite (SQLAlchemy ORM)
    - **Interface**: Streamlit
    - **Logging**: Structured JSON logging + HIPAA-compatible audit trail
    """)


# ─── Entry Point ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    main()
