"""
Agent 5: Appointment Coordination Agent
=========================================
Purpose: Helps patients prepare for appointments — checks availability,
         provides preparation guidance, appointment confirmation steps,
         and follow-up tracking.

Responsibilities:
  - Check facility/specialist appointment availability
  - Provide appointment booking guidance (phone + in-person)
  - Telemedicine appointment guidance
  - Pre-appointment preparation checklist
  - Post-appointment follow-up reminders
  - Track appointment status in session
"""

from typing import Any, Optional
from langchain_core.messages import SystemMessage, HumanMessage

from agents.llm_factory import get_llm
from tools.healthcare_tools import check_appointment_availability
from utils.logger import app_logger, audit_logger


SYSTEM_PROMPT = """You are an Appointment Coordination Assistant for rural healthcare navigation.

Your role is to help patients prepare for and schedule healthcare appointments.

WHEN COORDINATING APPOINTMENTS:
1. Check facility availability from the provided data
2. Guide patients on HOW to book (phone number, walk-in, online if available)
3. Provide pre-appointment preparation:
   - Documents to carry (Aadhaar, health card, records)
   - Fasting requirements (general guidance only, not specific medical advice)
   - Arrival time recommendation (arrive 30 minutes early for OPD)
4. For telemedicine: guide on app/phone setup
5. For follow-up appointments: note the importance of compliance

IMPORTANT:
- Do NOT confirm appointments yourself — you guide the patient to call/visit
- Always provide the facility phone number
- Note OPD timings when available
- Mention that government OPD services are FREE at PHC/CHC/District Hospitals
- If patient has difficulty traveling: highlight telemedicine or ASHA worker contact

Be warm, encouraging, and practical. Rural patients may have never visited a hospital before.
"""


class AppointmentCoordinationAgent:
    """
    Agent 5: Appointment Coordination Agent

    State maintained:
        - facility_checked
        - specialist_checked
        - availability_data
        - coordination_complete
    """

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.agent_name = "AppointmentCoordinationAgent"
        self.llm = get_llm(temperature=0.3)

        self.state: dict[str, Any] = {
            "facility_checked": None,
            "specialist_checked": None,
            "availability_data": {},
            "coordination_complete": False,
        }

    def run(
        self,
        facility: dict,
        specialist: Optional[dict] = None,
        urgency_level: str = "low",
        preferred_date: Optional[str] = None,
        chief_complaint: str = "",
    ) -> dict[str, Any]:
        """
        Coordinate appointment for patient.

        Args:
            facility: Target facility dict from discovery agent
            specialist: Optional specific specialist dict
            urgency_level: Assessed urgency level
            preferred_date: Patient's preferred appointment date
            chief_complaint: Category of complaint (for context)

        Returns:
            dict with availability_info, booking_guidance, preparation_checklist
        """
        import time
        start_time = time.time()

        facility_id = facility.get("id", "")
        specialist_id = specialist.get("id") if specialist else None

        # ── Tool Call: Check appointment availability ────────────────────
        availability = check_appointment_availability(
            facility_id=facility_id,
            specialist_id=specialist_id,
            preferred_date=preferred_date,
        )
        self.state["availability_data"] = availability
        self.state["facility_checked"] = facility.get("name")
        if specialist:
            self.state["specialist_checked"] = specialist.get("name")

        # ── Build LLM prompt ─────────────────────────────────────────────
        avail_text = self._format_availability(availability, facility, specialist)

        prompt = f"""Patient needs appointment coordination:

HEALTHCARE NEED: {chief_complaint}
URGENCY LEVEL: {urgency_level.upper()}
PREFERRED DATE: {preferred_date or 'As soon as possible'}

FACILITY DETAILS:
- Name: {facility.get('name', 'N/A')}
- Phone: {facility.get('phone', 'N/A')}
- Type: {facility.get('type', 'N/A')}
- Government: {'Yes' if facility.get('is_government') else 'No'}
- 24×7: {'Yes' if facility.get('is_24x7') else 'No'}
- Emergency: {'Yes' if facility.get('has_emergency') else 'No'}

{avail_text}

Please provide:
1. Specific booking instructions (how to call, what to say)
2. Pre-appointment checklist (documents + preparation)
3. What to expect on arrival
4. OPD queue management tips
5. Telemedicine alternative (if applicable)
6. Emergency bypass instructions (if urgency is high/emergency)"""

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ]

        try:
            response = self.llm.invoke(messages)
            guidance_text = response.content if hasattr(response, "content") else str(response)
        except Exception as e:
            app_logger.error(f"LLM error in AppointmentCoordinationAgent: {e}")
            guidance_text = self._fallback_guidance(facility, urgency_level)

        self.state["coordination_complete"] = True

        # ── Audit logging ────────────────────────────────────────────────
        duration_ms = (time.time() - start_time) * 1000
        audit_logger.log(
            session_id=self.session_id,
            action_type="agent_call",
            agent_name=self.agent_name,
            action=f"appointment_coordination → {facility.get('name')}",
            outcome="success",
            metadata={
                "facility": facility.get("name"),
                "specialist": specialist.get("name") if specialist else None,
                "urgency": urgency_level,
                "availability_success": availability.get("success", False),
            },
            duration_ms=duration_ms,
        )

        return {
            "agent": self.agent_name,
            "booking_guidance": guidance_text,
            "availability_info": availability,
            "facility_name": facility.get("name"),
            "facility_phone": facility.get("phone"),
            "specialist_name": specialist.get("name") if specialist else None,
            "is_walk_in": availability.get("is_walk_in_available", False),
            "avg_wait_minutes": availability.get("avg_wait_time_minutes", 30),
            "coordination_complete": True,
            "note": "Please call the facility to confirm appointment before visiting.",
        }

    def _format_availability(self, avail: dict, facility: dict, specialist: Optional[dict]) -> str:
        """Format availability data for LLM context."""
        lines = ["AVAILABILITY DATA:"]
        if avail.get("success"):
            lines.append(f"- Walk-in available: {'Yes' if avail.get('is_walk_in_available') else 'No'}")
            lines.append(f"- Average wait time: {avail.get('avg_wait_time_minutes', 30)} minutes")
            if specialist:
                lines.append(f"- Specialist: {avail.get('specialist_name', 'N/A')} ({avail.get('specialty', 'N/A')})")
                lines.append(f"- Available days: {avail.get('available_days', [])}")
                lines.append(f"- Time slots: {avail.get('available_slots', [])}")
                lines.append(f"- Consultation fee: ₹{avail.get('consultation_fee', 0)}")
                lines.append(f"- Telemedicine: {'Yes' if avail.get('telemedicine_available') else 'No'}")
        else:
            lines.append("- Live availability data not available. Call facility directly.")
        return "\n".join(lines)

    def _fallback_guidance(self, facility: dict, urgency: str) -> str:
        """Fallback if LLM fails."""
        name = facility.get("name", "the facility")
        phone = facility.get("phone", "104")
        if urgency == "emergency":
            return f"🚨 EMERGENCY: Call 108 NOW! If stable, go directly to {name}. Phone: {phone}"
        return (
            f"**To book appointment at {name}:**\n"
            f"1. Call {phone}\n"
            f"2. Mention your healthcare need and request an OPD appointment\n"
            f"3. Carry: Aadhaar card, Health card, Previous records\n"
            f"4. Arrive 30 minutes before your appointment time\n\n"
            f"For help: Call National Health Helpline 104 (free, 24×7)"
        )

    def get_state(self) -> dict[str, Any]:
        return self.state.copy()
