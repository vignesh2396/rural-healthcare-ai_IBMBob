"""
Agent 1: Patient Requirement Assessment Agent
=============================================
Purpose: The first touchpoint in the patient navigation workflow.
         Gathers patient context (location, symptoms, language preference),
         assesses healthcare needs, and determines urgency level.
         Does NOT diagnose — navigates and triages for facility routing only.

Responsibilities:
  - Collect and validate patient location (state, district)
  - Understand and categorize the chief complaint/healthcare need
  - Assess urgency using the assessment tool
  - Map symptoms to relevant departments
  - Pass structured patient context to supervisor for downstream agents
  - Display appropriate medical disclaimers
"""

from typing import Any, Optional
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from agents.llm_factory import get_llm
from tools.healthcare_tools import assess_urgency, map_symptoms_to_departments
from utils.logger import app_logger, audit_logger


SYSTEM_PROMPT = """You are a compassionate and professional Patient Navigation Assistant for rural healthcare services in India.

Your ONLY purpose is to:
1. Understand the patient's location and healthcare navigation need
2. Help identify what type of healthcare service they are looking for
3. Assess whether the situation requires URGENT attention
4. Route the patient to the correct next step in our navigation system

CRITICAL RULES:
- You MUST NOT diagnose any medical condition
- You MUST NOT recommend specific medicines or treatments
- You MUST NOT replace a qualified healthcare professional
- If there are emergency keywords (chest pain, stroke, difficulty breathing, unconscious, severe bleeding), IMMEDIATELY escalate
- Always display the disclaimer: "This is a navigation support service, not a medical diagnosis system"
- Communicate with empathy and use simple, non-technical language
- Support regional context (you may receive questions about health services in rural/semi-urban areas of India)

INFORMATION TO GATHER:
1. Patient's district and state (location)
2. Chief complaint or healthcare need (in patient's own words)
3. How long they have had this issue (duration)
4. Whether they have visited any facility before
5. Language preference for communication

After gathering this information, provide a structured summary with:
- Location confirmed
- Healthcare need category (not diagnosis)
- Urgency assessment
- Recommended next step (which specialist/facility type to look for)
"""


class PatientAssessmentAgent:
    """
    Agent 1: Patient Requirement Assessment Agent

    State maintained:
        - patient_location (district, state)
        - chief_complaint_text
        - urgency_level
        - recommended_departments
        - conversation_memory (last 10 turns)
    """

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.agent_name = "PatientAssessmentAgent"
        self.llm = get_llm(temperature=0.1)  # Low temp for consistent triage
        self._conversation_history: list = []  # Simple list-based memory (last 10 turns)

        # Mutable state for this session
        self.state: dict[str, Any] = {
            "district": None,
            "state": None,
            "chief_complaint": None,
            "urgency_level": None,
            "urgency_details": None,
            "recommended_departments": [],
            "assessment_complete": False,
            "step_count": 0,
        }

    def run(self, user_message: str) -> dict[str, Any]:
        """
        Process user message and return assessment response.

        Args:
            user_message: Raw patient input text

        Returns:
            dict with response_text, urgency_level, needs_escalation,
                  extracted_location, recommended_departments, tool_results
        """
        import time
        start_time = time.time()
        self.state["step_count"] += 1

        # ── Step 1: Run urgency assessment tool ─────────────────────────
        urgency_result = assess_urgency(
            symptoms_text=user_message,
            additional_context=self.state.get("chief_complaint", "")
        )
        self.state["urgency_level"] = urgency_result.get("urgency_level", "low")
        self.state["urgency_details"] = urgency_result

        # ── Step 2: Map symptoms to departments ─────────────────────────
        dept_result = map_symptoms_to_departments(user_message)
        if dept_result.get("success"):
            self.state["recommended_departments"] = dept_result.get("recommended_departments", [])

        # ── Step 3: Build LLM prompt with tool context ──────────────────
        tool_context = f"""
TOOL ASSESSMENT RESULTS (for your reference, do not repeat verbatim):
- Urgency Level: {urgency_result.get('urgency_level', 'unknown').upper()}
- Emergency Keywords Detected: {urgency_result.get('matched_emergency_keywords', [])}
- Recommended Action: {urgency_result.get('recommended_action', '')}
- Suggested Departments: {dept_result.get('recommended_departments', [])}
- Patient Location (if previously provided): District={self.state.get('district')}, State={self.state.get('state')}

Current conversation step: {self.state['step_count']}

If this is step 1-2, focus on gathering location and understanding the healthcare need.
If urgency is 'emergency', IMMEDIATELY provide emergency contact numbers and advise urgent care.
If you have enough information (location + complaint), provide a structured assessment summary.
"""

        messages = [
            SystemMessage(content=SYSTEM_PROMPT + "\n\n" + tool_context),
        ]

        # Add conversation history (last 10 turns = 20 messages)
        messages.extend(self._conversation_history[-20:])
        messages.append(HumanMessage(content=user_message))

        try:
            response = self.llm.invoke(messages)
            response_text = response.content if hasattr(response, "content") else str(response)
            response_text = response_text or ""  # guard against None content
        except Exception as e:
            app_logger.error(f"LLM error in PatientAssessmentAgent: {e}")
            response_text = (
                "I apologize, I'm having technical difficulties. "
                "If this is a medical emergency, please call 108 (ambulance) immediately. "
                "For health queries, call the National Health Helpline: 104."
            )

        # ── Step 4: Save to conversation history ────────────────────────
        self._conversation_history.append(HumanMessage(content=user_message))
        self._conversation_history.append(AIMessage(content=response_text))

        # ── Step 5: Extract location if mentioned ───────────────────────
        self._extract_location_from_text(user_message)
        if response_text:
            self._extract_location_from_text(response_text)

        # ── Step 6: Check if assessment is complete ──────────────────────
        if self.state["district"] and self.state["chief_complaint"] and self.state["step_count"] >= 2:
            self.state["assessment_complete"] = True

        # ── Audit logging ────────────────────────────────────────────────
        duration_ms = (time.time() - start_time) * 1000
        audit_logger.log(
            session_id=self.session_id,
            action_type="agent_call",
            agent_name=self.agent_name,
            action=f"assess_patient_request (step {self.state['step_count']})",
            outcome="success",
            metadata={
                "urgency_level": self.state["urgency_level"],
                "departments": self.state["recommended_departments"],
                "emergency_matched": bool(urgency_result.get("matched_emergency_keywords")),
            },
            duration_ms=duration_ms,
        )

        return {
            "agent": self.agent_name,
            "response_text": response_text,
            "urgency_level": self.state["urgency_level"],
            "needs_escalation": self.state["urgency_level"] == "emergency",
            "district": self.state.get("district"),
            "state_name": self.state.get("state"),
            "chief_complaint": self.state.get("chief_complaint"),
            "recommended_departments": self.state["recommended_departments"],
            "assessment_complete": self.state["assessment_complete"],
            "emergency_contacts": urgency_result.get("emergency_contacts"),
            "disclaimer": urgency_result.get("disclaimer"),
            "tool_results": {
                "urgency": urgency_result,
                "department_mapping": dept_result,
            }
        }

    def _extract_location_from_text(self, text: str) -> None:
        """Simple keyword extraction for state/district from conversation text."""
        # Common Indian states (abbreviated)
        states = [
            "Maharashtra", "Karnataka", "Tamil Nadu", "Rajasthan", "Uttar Pradesh",
            "Madhya Pradesh", "Gujarat", "Bihar", "West Bengal", "Andhra Pradesh",
            "Telangana", "Kerala", "Odisha", "Punjab", "Haryana", "Jharkhand",
            "Chhattisgarh", "Assam", "Uttarakhand", "Himachal Pradesh",
        ]
        text_lower = text.lower()
        if not self.state.get("state"):
            for s in states:
                if s.lower() in text_lower:
                    self.state["state"] = s
                    break

        # Chief complaint extraction (simplified)
        if not self.state.get("chief_complaint"):
            complaint_keywords = [
                "pain", "fever", "cough", "breathing", "pregnant", "injury",
                "diabetic", "pressure", "blood", "vomiting", "diarrhea", "checkup"
            ]
            found = [kw for kw in complaint_keywords if kw in text_lower]
            if found:
                self.state["chief_complaint"] = ", ".join(found)

    def get_state(self) -> dict[str, Any]:
        """Return current agent state for supervisor routing."""
        return self.state.copy()

    def update_location(self, district: str, state_name: str) -> None:
        """Allow supervisor to inject confirmed location."""
        self.state["district"] = district
        self.state["state"] = state_name
