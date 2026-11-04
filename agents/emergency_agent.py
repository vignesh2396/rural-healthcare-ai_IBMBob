"""
Agent 6: Emergency Escalation Agent
======================================
Purpose: Handles potentially urgent situations that require immediate action
         and human healthcare professional involvement.
         Provides emergency guidance, escalates to human review queue,
         and coordinates with emergency services information.

Responsibilities:
  - Identify emergency situations from urgency assessment
  - Provide clear, calm emergency response guidance
  - Display emergency contact numbers prominently
  - Flag session for human review in the audit system
  - Generate emergency navigation summary
  - NEVER claim to manage emergencies independently — always route to humans
  - Comply with healthcare AI safety guidelines (Section 10 of Capstone Guidelines)

SAFETY GUARANTEE:
  This agent ALWAYS defers to qualified healthcare professionals.
  It NEVER makes final emergency care decisions.
"""

from typing import Any
from langchain_core.messages import SystemMessage, HumanMessage

from agents.llm_factory import get_llm
from utils.logger import app_logger, audit_logger
from config.settings import settings


SYSTEM_PROMPT = f"""You are an Emergency Navigation Assistant for rural healthcare.

⚠️ CRITICAL: You are NOT a medical emergency system. You CANNOT provide emergency medical treatment.
Your ONLY role is to:
1. IMMEDIATELY direct the person to call emergency services
2. Provide clear, calm step-by-step guidance to get emergency help
3. Keep the person calm while they wait for/reach help
4. Provide basic safety guidance (do NOT move someone with possible spinal injury, etc.)

EMERGENCY NUMBERS (INDIA):
- Ambulance: {settings.AMBULANCE_SERVICE}
- Emergency Services: {settings.EMERGENCY_HOTLINE}  
- National Health Helpline: {settings.HEALTH_HELPLINE}
- Police: 100
- Fire: 101
- Women Helpline: 1091

ALWAYS:
- Start EVERY response with: "🚨 CALL {settings.AMBULANCE_SERVICE} (Ambulance) IMMEDIATELY"
- Stay calm and give simple, numbered instructions
- Do NOT panic the patient/caregiver
- Repeat the emergency number at least twice
- If it is a MENTAL HEALTH crisis: mention iCall (9152987821) and Vandrevala (1860-2662-345)

NEVER:
- Claim you can manage the emergency
- Provide drug doses or treatment instructions  
- Replace emergency services or paramedics
- Delay routing to professional help

DISCLAIMER TO ALWAYS INCLUDE:
"⚠️ THIS IS NOT A SUBSTITUTE FOR EMERGENCY MEDICAL SERVICES. 
Call {settings.AMBULANCE_SERVICE} immediately. This AI system cannot manage medical emergencies."
"""


class EmergencyEscalationAgent:
    """
    Agent 6: Emergency Escalation Agent

    Activated when urgency_level == "emergency" OR
    when assessment_agent.needs_escalation == True.

    State maintained:
        - escalation_triggered
        - escalation_timestamp
        - human_review_flagged
        - emergency_type
    """

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.agent_name = "EmergencyEscalationAgent"
        self._llm = None  # Lazy-loaded to allow unit tests without API key

        self.state: dict[str, Any] = {
            "escalation_triggered": False,
            "escalation_timestamp": None,
            "human_review_flagged": False,
            "emergency_type": None,
            "emergency_keywords_found": [],
        }

    def run(
        self,
        situation_description: str,
        district: str,
        state_name: str,
        matched_emergency_keywords: list[str],
        nearest_emergency_facility: dict = None,
    ) -> dict[str, Any]:
        """
        Handle emergency escalation.

        Args:
            situation_description: Summary of the situation (no detailed PII)
            district: Patient's district for localized guidance
            state_name: Patient's state
            matched_emergency_keywords: Keywords that triggered escalation
            nearest_emergency_facility: Nearest facility with emergency services

        Returns:
            dict with emergency_response, emergency_contacts, human_review_triggered,
                  nearest_emergency_facility_info
        """
        import time
        from datetime import datetime, timezone
        start_time = time.time()

        self.state["escalation_triggered"] = True
        self.state["escalation_timestamp"] = datetime.now(timezone.utc).isoformat()
        self.state["emergency_keywords_found"] = matched_emergency_keywords

        # Classify emergency type
        kw_str = " ".join(matched_emergency_keywords).lower()
        if any(w in kw_str for w in ["heart", "chest", "stroke", "breathing"]):
            self.state["emergency_type"] = "cardiac_respiratory"
        elif any(w in kw_str for w in ["bleeding", "trauma", "accident", "fracture"]):
            self.state["emergency_type"] = "trauma"
        elif any(w in kw_str for w in ["pregnancy", "labor", "eclampsia"]):
            self.state["emergency_type"] = "obstetric"
        elif any(w in kw_str for w in ["poison", "snake", "burn"]):
            self.state["emergency_type"] = "toxicology_burns"
        elif any(w in kw_str for w in ["mental", "suicide", "self harm"]):
            self.state["emergency_type"] = "mental_health_crisis"
        else:
            self.state["emergency_type"] = "general_emergency"

        # Nearest emergency facility info
        facility_text = ""
        if nearest_emergency_facility:
            facility_text = (
                f"\nNEAREST EMERGENCY FACILITY:\n"
                f"Name: {nearest_emergency_facility.get('name', 'N/A')}\n"
                f"Phone: {nearest_emergency_facility.get('phone', 'N/A')}\n"
                f"Distance: {nearest_emergency_facility.get('distance_km', 'N/A')} km\n"
                f"Has Ambulance: {'Yes' if nearest_emergency_facility.get('has_ambulance') else 'Check with facility'}\n"
                f"Has ICU: {'Yes' if nearest_emergency_facility.get('has_icu') else 'N/A'}"
            )

        # ── Build LLM prompt ─────────────────────────────────────────────
        prompt = f"""EMERGENCY SITUATION DETECTED

Emergency Type: {self.state['emergency_type'].replace('_', ' ').title()}
Keywords Detected: {matched_emergency_keywords}
Location: {district}, {state_name}
{facility_text}

Situation Summary (anonymized): {situation_description[:200]}

Provide immediate emergency navigation guidance following the system prompt.
Include:
1. IMMEDIATE action (call ambulance NOW)
2. What to do while waiting for help
3. How to get to the nearest emergency facility
4. Mental health crisis resources (if applicable)
5. Repeat emergency numbers at the end"""

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ]

        try:
            if self._llm is None:
                self._llm = get_llm(temperature=0.0)  # Lazy init
            response = self._llm.invoke(messages)
            emergency_response = response.content if hasattr(response, "content") else str(response)
        except Exception as e:
            app_logger.error(f"LLM error in EmergencyEscalationAgent: {e}")
            # Hard-coded fallback — must always work even if LLM fails
            emergency_response = self._hardcoded_emergency_response(
                self.state["emergency_type"],
                nearest_emergency_facility
            )

        # ── Flag for human review ─────────────────────────────────────────
        self.state["human_review_flagged"] = True

        # ── CRITICAL: Audit trail for emergency ──────────────────────────
        duration_ms = (time.time() - start_time) * 1000
        audit_logger.log(
            session_id=self.session_id,
            action_type="escalation",
            agent_name=self.agent_name,
            action=f"EMERGENCY_ESCALATION: {self.state['emergency_type']}",
            outcome="escalated",
            metadata={
                "emergency_type": self.state["emergency_type"],
                "keywords": matched_emergency_keywords,
                "district": district,
                "state": state_name,
                "human_review_required": True,
                "nearest_facility": nearest_emergency_facility.get("name") if nearest_emergency_facility else None,
            },
            duration_ms=duration_ms,
        )

        # Alert log (high-priority)
        app_logger.warning(
            f"EMERGENCY ESCALATION | Session: {self.session_id} | "
            f"Type: {self.state['emergency_type']} | District: {district}"
        )

        return {
            "agent": self.agent_name,
            "emergency_response": emergency_response,
            "emergency_type": self.state["emergency_type"],
            "emergency_triggered": True,
            "human_review_required": True,
            "emergency_contacts": {
                "ambulance": settings.AMBULANCE_SERVICE,
                "emergency": settings.EMERGENCY_HOTLINE,
                "health_helpline": settings.HEALTH_HELPLINE,
                "police": "100",
                "mental_health": "9152987821 (iCall) | 1860-2662-345 (Vandrevala Foundation)",
            },
            "nearest_emergency_facility": nearest_emergency_facility,
            "session_flagged_for_review": True,
            "escalation_timestamp": self.state["escalation_timestamp"],
            "disclaimer": (
                "⚠️ THIS IS NOT A SUBSTITUTE FOR EMERGENCY MEDICAL SERVICES. "
                f"Call {settings.AMBULANCE_SERVICE} immediately. "
                "This AI system CANNOT manage medical emergencies."
            ),
        }

    def _hardcoded_emergency_response(
        self,
        emergency_type: str,
        facility: dict = None
    ) -> str:
        """Hard-coded response — works even when LLM is completely unavailable."""
        facility_info = ""
        if facility:
            facility_info = f"\n\n🏥 Nearest Emergency: {facility.get('name')} | Call: {facility.get('phone', 'N/A')}"

        base = (
            f"🚨 CALL {settings.AMBULANCE_SERVICE} (AMBULANCE) IMMEDIATELY! 🚨\n\n"
            f"Steps while waiting for ambulance:\n"
            f"1. Stay calm and keep the patient still\n"
            f"2. Do not give food, water, or medicines without medical guidance\n"
            f"3. Keep the patient warm and comfortable\n"
            f"4. Stay on the phone with emergency services\n"
            f"5. Send someone to the road to guide the ambulance{facility_info}\n\n"
            f"Emergency: {settings.EMERGENCY_HOTLINE} | Ambulance: {settings.AMBULANCE_SERVICE} | "
            f"Health Helpline: {settings.HEALTH_HELPLINE}\n\n"
            f"⚠️ THIS AI SYSTEM CANNOT MANAGE EMERGENCIES. CALL {settings.AMBULANCE_SERVICE} NOW."
        )

        if emergency_type == "mental_health_crisis":
            return (
                f"🆘 MENTAL HEALTH CRISIS SUPPORT\n\n"
                f"iCall: 9152987821 (Mon-Sat, 8am-10pm)\n"
                f"Vandrevala Foundation: 1860-2662-345 (24×7)\n"
                f"NIMHANS: 080-46110007\n\n"
                f"If there is immediate physical danger: {base}"
            )
        return base

    def get_state(self) -> dict[str, Any]:
        return self.state.copy()
