"""
Supervisor Agent — Multi-Agent Orchestrator
============================================
Purpose: Central orchestrator that routes patient requests to appropriate
         specialized agents, maintains session state, ensures workflow
         completion, and coordinates agent handoffs.

Architecture:
    User → Supervisor → Assessment Agent
                      → Facility Discovery Agent
                      → RAG Knowledge Agent
                      → Referral Planning Agent
                      → Appointment Coordination Agent
                      → Emergency Escalation Agent (bypass on emergency)

Human-in-the-Loop:
    - Emergency situations: Always route to Emergency Agent + flag for human review
    - High urgency: Confirm with patient before generating referral
    - Low confidence RAG results: Flag for additional verification
    - Unknown/ambiguous situations: Ask for clarification before proceeding

State maintained across the full session:
    - patient_location (district, state)
    - chief_complaint
    - urgency_level
    - discovered_facilities
    - referral_generated
    - appointment_coordinated
    - knowledge_queries_answered
    - session_complete
"""

import uuid
import time
from typing import Any, Optional
from datetime import datetime, timezone

from agents.assessment_agent import PatientAssessmentAgent
from agents.facility_discovery_agent import FacilityDiscoveryAgent
from agents.referral_agent import ReferralPlanningAgent
from agents.rag_knowledge_agent import RAGKnowledgeAgent
from agents.appointment_agent import AppointmentCoordinationAgent
from agents.emergency_agent import EmergencyEscalationAgent
from utils.database import PatientSession, SessionLocal, init_db
from utils.logger import app_logger, audit_logger
from config.settings import settings


class SupervisorAgent:
    """
    Central orchestrator for the Rural Healthcare AI Navigation System.

    Implements a stateful multi-agent workflow with:
    - Sequential agent activation based on conversation stage
    - Emergency bypass (immediately routes to escalation agent)
    - Memory persistence across conversation turns
    - Explainability at every decision point
    - Human-in-the-loop triggers for high-risk decisions
    """

    # Conversation stages
    STAGE_GREETING = "greeting"
    STAGE_ASSESSMENT = "assessment"
    STAGE_DISCOVERY = "discovery"
    STAGE_KNOWLEDGE = "knowledge"
    STAGE_REFERRAL = "referral"
    STAGE_APPOINTMENT = "appointment"
    STAGE_EMERGENCY = "emergency"
    STAGE_COMPLETE = "complete"

    def __init__(self):
        init_db()
        self.session_id = str(uuid.uuid4())
        self.session_token = uuid.uuid4().hex
        self.stage = self.STAGE_GREETING
        self.turn_count = 0

        # Initialize all agents
        self.assessment_agent = PatientAssessmentAgent(self.session_id)
        self.discovery_agent = FacilityDiscoveryAgent(self.session_id)
        self.referral_agent = ReferralPlanningAgent(self.session_id)
        self.rag_agent = RAGKnowledgeAgent(self.session_id)
        self.appointment_agent = AppointmentCoordinationAgent(self.session_id)
        self.emergency_agent = EmergencyEscalationAgent(self.session_id)

        # Session-level state
        self.state: dict[str, Any] = {
            "session_id": self.session_id,
            "district": None,
            "state_name": None,
            "chief_complaint": None,
            "urgency_level": "low",
            "recommended_departments": [],
            "top_facility": None,
            "top_specialist": None,
            "referral_generated": False,
            "referral_id": None,
            "appointment_coordinated": False,
            "emergency_triggered": False,
            "human_review_required": False,
            "knowledge_queries": [],
            "workflow_steps_completed": [],
            "government_only_preference": False,
            "conversation_history": [],  # list of (role, text) tuples
        }

        # Persist session to DB
        self._create_db_session()

        app_logger.info(f"SupervisorAgent initialized | Session: {self.session_id}")

    def _create_db_session(self) -> None:
        """Create session record in database."""
        db = SessionLocal()
        try:
            session = PatientSession(
                id=self.session_id,
                session_token=self.session_token,
                navigation_status="active",
            )
            db.add(session)
            db.commit()
        except Exception as e:
            db.rollback()
            app_logger.error(f"DB session creation failed: {e}")
        finally:
            db.close()

    def _update_db_session(self) -> None:
        """Update session record with current state."""
        db = SessionLocal()
        try:
            session = db.query(PatientSession).filter_by(id=self.session_id).first()
            if session:
                session.district = self.state.get("district")
                session.state = self.state.get("state_name")
                session.chief_complaint_category = self.state.get("chief_complaint")
                session.urgency_level = self.state.get("urgency_level")
                session.referral_generated = self.state.get("referral_generated", False)
                session.escalated_to_emergency = self.state.get("emergency_triggered", False)
                session.human_review_requested = self.state.get("human_review_required", False)
                if self.stage == self.STAGE_COMPLETE:
                    session.navigation_status = "completed"
                db.commit()
        except Exception as e:
            db.rollback()
            app_logger.error(f"DB session update failed: {e}")
        finally:
            db.close()

    def process_message(self, user_message: str) -> dict[str, Any]:
        """
        Main entry point — process a user message and route to appropriate agent(s).

        Args:
            user_message: Raw user input from chat interface

        Returns:
            dict with:
                response_text: Primary response for display
                agent_invoked: Which agent handled it
                stage: Current workflow stage
                state: Current session state snapshot
                decision_factors: Explainability list
                tool_results: Raw tool output (for transparency panel)
                emergency: bool flag
                human_review_required: bool flag
        """
        start_time = time.time()
        self.turn_count += 1

        # Save to conversation history
        self.state["conversation_history"].append(("user", user_message))

        app_logger.info(
            f"Supervisor | Turn: {self.turn_count} | Stage: {self.stage} | "
            f"Session: {self.session_id[:8]}..."
        )

        # ── STEP 1: Check for emergency keywords FIRST (bypass) ─────────
        from tools.healthcare_tools import assess_urgency
        quick_urgency = assess_urgency(user_message)
        if quick_urgency.get("urgency_level") == "emergency":
            return self._handle_emergency(user_message, quick_urgency)

        # ── STEP 2: Route based on stage ─────────────────────────────────
        result = None

        # Detect facility-search intent regardless of current stage so the
        # Knowledge stage doesn't trap facility-navigation requests.
        _facility_keywords = [
            "hospital", "clinic", "health centre", "health center", "phc", "chc",
            "find", "locate", "near", "nearby", "government", "district", "govt",
            "doctor", "specialist", "facility", "facilities", "where", "search",
        ]
        _msg_lower = user_message.lower()
        _is_facility_request = any(kw in _msg_lower for kw in _facility_keywords)

        if self.stage in [self.STAGE_GREETING, self.STAGE_ASSESSMENT]:
            result = self._run_assessment(user_message)

        elif self.stage == self.STAGE_KNOWLEDGE:
            if _is_facility_request:
                # User switched from knowledge mode to facility search — re-route
                self.stage = self.STAGE_ASSESSMENT
                result = self._run_assessment(user_message)
            else:
                # Patient asked a knowledge question — use RAG agent
                result = self._run_knowledge_query(user_message)

        elif self.stage == self.STAGE_DISCOVERY:
            result = self._run_discovery()

        elif self.stage == self.STAGE_REFERRAL:
            result = self._run_referral()

        elif self.stage == self.STAGE_APPOINTMENT:
            result = self._run_appointment()

        elif self.stage == self.STAGE_COMPLETE:
            result = self._handle_post_completion(user_message)

        else:
            result = self._run_assessment(user_message)

        # ── STEP 3: Stage progression logic ─────────────────────────────
        self._advance_stage(result)

        # ── STEP 4: Save to conversation history ─────────────────────────
        response_text = (
            result.get("response_text")
            or result.get("comparison_text")
            or result.get("navigation_plan")
            or result.get("answer_text")
            or result.get("emergency_response")
            or "Processing your request — please try again."
        )
        self.state["conversation_history"].append(("assistant", response_text))

        # ── STEP 5: Update DB ─────────────────────────────────────────────
        self._update_db_session()

        # ── Audit ────────────────────────────────────────────────────────
        duration_ms = (time.time() - start_time) * 1000
        audit_logger.log(
            session_id=self.session_id,
            action_type="agent_call",
            agent_name="SupervisorAgent",
            action=f"route_message (turn={self.turn_count}, stage={self.stage})",
            outcome="success",
            metadata={
                "stage": self.stage,
                "urgency": self.state.get("urgency_level"),
                "district": self.state.get("district"),
                "turn": self.turn_count,
            },
            duration_ms=duration_ms,
        )

        return {
            **result,
            "response_text": response_text,
            "stage": self.stage,
            "session_id": self.session_id,
            "turn_count": self.turn_count,
            "session_state": self._get_public_state(),
            "workflow_steps_completed": self.state["workflow_steps_completed"],
        }

    def _run_assessment(self, user_message: str) -> dict[str, Any]:
        """Run Assessment Agent and update session state."""
        self.stage = self.STAGE_ASSESSMENT
        result = self.assessment_agent.run(user_message)

        # Propagate state upward
        assessment_state = self.assessment_agent.get_state()
        if assessment_state.get("district"):
            self.state["district"] = assessment_state["district"]
        if assessment_state.get("state"):
            self.state["state_name"] = assessment_state["state"]
        if assessment_state.get("chief_complaint"):
            self.state["chief_complaint"] = assessment_state["chief_complaint"]
        if assessment_state.get("urgency_level"):
            self.state["urgency_level"] = assessment_state["urgency_level"]
        if assessment_state.get("recommended_departments"):
            self.state["recommended_departments"] = assessment_state["recommended_departments"]

        if "assessment" not in self.state["workflow_steps_completed"]:
            self.state["workflow_steps_completed"].append("assessment")

        # Check if assessment is complete — if so, determine next stage
        if assessment_state.get("assessment_complete") or result.get("needs_escalation"):
            if result.get("needs_escalation"):
                self.stage = self.STAGE_EMERGENCY
            else:
                self.stage = self.STAGE_DISCOVERY

        return result

    def _run_discovery(self) -> dict[str, Any]:
        """Run Facility Discovery Agent."""
        district = self.state.get("district") or "Unknown"
        state_name = self.state.get("state_name") or "Unknown"
        departments = self.state.get("recommended_departments") or ["General Medicine"]
        urgency = self.state.get("urgency_level", "low")

        result = self.discovery_agent.run(
            district=district,
            state_name=state_name,
            departments=departments,
            urgency_level=urgency,
            government_only=self.state.get("government_only_preference", False),
            find_specialists_flag=True,
        )

        # Store top recommendation
        if result.get("top_recommendation"):
            self.state["top_facility"] = result["top_recommendation"]
        if result.get("specialists"):
            self.state["top_specialist"] = result["specialists"][0] if result["specialists"] else None

        if "discovery" not in self.state["workflow_steps_completed"]:
            self.state["workflow_steps_completed"].append("discovery")

        self.stage = self.STAGE_REFERRAL

        return {
            **result,
            "response_text": result.get("comparison_text", "Searching for healthcare facilities..."),
        }

    def _run_referral(self) -> dict[str, Any]:
        """Run Referral Planning Agent."""
        district = self.state.get("district") or "Your location"
        state_name = self.state.get("state_name") or "Your state"
        top_facility = self.state.get("top_facility") or {}
        departments = self.state.get("recommended_departments") or ["General Medicine"]
        urgency = self.state.get("urgency_level", "low")
        complaint = self.state.get("chief_complaint") or "general healthcare"

        result = self.referral_agent.run(
            patient_context=f"Location: {district}, {state_name}. Need: {complaint}",
            district=district,
            state_name=state_name,
            target_facility=top_facility,
            target_department=departments[0] if departments else "General Medicine",
            urgency_level=urgency,
            chief_complaint=complaint,
            step_number=len(self.state["workflow_steps_completed"]) + 1,
        )

        self.state["referral_generated"] = True
        self.state["referral_id"] = result.get("referral_id")

        if "referral" not in self.state["workflow_steps_completed"]:
            self.state["workflow_steps_completed"].append("referral")

        self.stage = self.STAGE_APPOINTMENT

        return {
            **result,
            "response_text": result.get("navigation_plan", "Generating your navigation plan..."),
        }

    def _run_appointment(self) -> dict[str, Any]:
        """Run Appointment Coordination Agent."""
        top_facility = self.state.get("top_facility") or {}
        specialist = self.state.get("top_specialist")
        urgency = self.state.get("urgency_level", "low")
        complaint = self.state.get("chief_complaint") or "healthcare consultation"

        result = self.appointment_agent.run(
            facility=top_facility,
            specialist=specialist,
            urgency_level=urgency,
            chief_complaint=complaint,
        )

        self.state["appointment_coordinated"] = True

        if "appointment" not in self.state["workflow_steps_completed"]:
            self.state["workflow_steps_completed"].append("appointment")

        self.stage = self.STAGE_COMPLETE

        return {
            **result,
            "response_text": result.get("booking_guidance", "Coordination complete."),
        }

    def _run_knowledge_query(self, query: str) -> dict[str, Any]:
        """Run RAG Knowledge Agent for general healthcare questions."""
        result = self.rag_agent.run(query=query)
        self.state["knowledge_queries"].append(query)

        if "knowledge" not in self.state["workflow_steps_completed"]:
            self.state["workflow_steps_completed"].append("knowledge")

        return {
            **result,
            "response_text": result.get("answer_text", "Searching knowledge base..."),
        }

    def _handle_emergency(
        self,
        user_message: str,
        urgency_result: dict,
    ) -> dict[str, Any]:
        """Emergency bypass — immediately routes to emergency escalation."""
        self.stage = self.STAGE_EMERGENCY
        self.state["emergency_triggered"] = True
        self.state["human_review_required"] = True
        self.state["urgency_level"] = "emergency"

        # Try to get nearest emergency facility if we have location
        nearest_facility = None
        if self.state.get("district"):
            from tools.healthcare_tools import search_healthcare_facilities
            fac_result = search_healthcare_facilities(
                district=self.state["district"],
                state=self.state.get("state_name", ""),
                requires_emergency=True,
                requires_24x7=True,
                max_results=1,
            )
            if fac_result.get("facilities"):
                nearest_facility = fac_result["facilities"][0]

        result = self.emergency_agent.run(
            situation_description=f"Patient reported: {user_message[:200]}",
            district=self.state.get("district") or "Unknown",
            state_name=self.state.get("state_name") or "Unknown",
            matched_emergency_keywords=urgency_result.get("matched_emergency_keywords", []),
            nearest_emergency_facility=nearest_facility,
        )

        if "emergency_escalation" not in self.state["workflow_steps_completed"]:
            self.state["workflow_steps_completed"].append("emergency_escalation")

        self._update_db_session()

        return {
            **result,
            "response_text": result.get("emergency_response", ""),
            "emergency": True,
            "human_review_required": True,
        }

    def _handle_post_completion(self, user_message: str) -> dict[str, Any]:
        """Handle messages after workflow completion — knowledge queries or re-navigation."""
        msg_lower = user_message.lower()

        # Detect knowledge queries
        if any(w in msg_lower for w in ["what is", "how to", "explain", "tell me about", "scheme", "government"]):
            return self._run_knowledge_query(user_message)

        # Detect new complaint — restart assessment
        if any(w in msg_lower for w in ["new", "another", "different", "also have", "and also"]):
            self.stage = self.STAGE_ASSESSMENT
            return self._run_assessment(user_message)

        # General follow-up response
        return {
            "agent": "SupervisorAgent",
            "response_text": (
                "Your navigation session is complete! 🎉\n\n"
                f"**Summary:**\n"
                f"- Referral ID: {self.state.get('referral_id', 'N/A')}\n"
                f"- Recommended Facility: {self.state.get('top_facility', {}).get('name', 'N/A')}\n"
                f"- Urgency: {self.state.get('urgency_level', 'N/A').upper()}\n\n"
                "If you have another healthcare question, feel free to ask!\n"
                "For help: National Health Helpline **104** (free, 24×7)"
            ),
            "stage": self.STAGE_COMPLETE,
            "session_state": self._get_public_state(),
        }

    def _advance_stage(self, result: dict) -> None:
        """Advance conversation stage based on result signals."""
        # Emergency always takes priority
        if result.get("emergency") or result.get("emergency_triggered"):
            self.stage = self.STAGE_EMERGENCY
            return
        # If discovery completed → move to referral
        if self.stage == self.STAGE_DISCOVERY and result.get("top_recommendation"):
            self.stage = self.STAGE_REFERRAL
        # If referral completed → move to appointment
        if self.stage == self.STAGE_REFERRAL and result.get("referral_id"):
            self.stage = self.STAGE_APPOINTMENT

    def handle_user_location_update(self, district: str, state_name: str) -> None:
        """Called when user updates location via sidebar widgets."""
        self.state["district"] = district
        self.state["state_name"] = state_name
        self.assessment_agent.update_location(district, state_name)
        app_logger.info(f"Location updated: {district}, {state_name}")

    def set_government_only(self, value: bool) -> None:
        """Called when user selects government-only preference."""
        self.state["government_only_preference"] = value

    def trigger_knowledge_mode(self) -> None:
        """Switch to knowledge query mode."""
        self.stage = self.STAGE_KNOWLEDGE

    def get_workflow_summary(self) -> dict[str, Any]:
        """Return a summary of the workflow for display in the UI."""
        return {
            "session_id": self.session_id[:8] + "...",
            "stage": self.stage,
            "turn_count": self.turn_count,
            "location_confirmed": bool(self.state.get("district")),
            "assessment_complete": "assessment" in self.state["workflow_steps_completed"],
            "facilities_found": len(self.discovery_agent.state.get("discovered_facilities", [])),
            "referral_generated": self.state.get("referral_generated", False),
            "referral_id": self.state.get("referral_id"),
            "appointment_coordinated": self.state.get("appointment_coordinated", False),
            "emergency_triggered": self.state.get("emergency_triggered", False),
            "human_review_required": self.state.get("human_review_required", False),
            "workflow_steps": self.state["workflow_steps_completed"],
            "urgency_level": self.state.get("urgency_level", "low"),
        }

    def _get_public_state(self) -> dict[str, Any]:
        """Return safe public state (no PII)."""
        return {
            "district": self.state.get("district"),
            "state_name": self.state.get("state_name"),
            "urgency_level": self.state.get("urgency_level"),
            "recommended_departments": self.state.get("recommended_departments"),
            "referral_id": self.state.get("referral_id"),
            "emergency_triggered": self.state.get("emergency_triggered"),
            "workflow_steps_completed": self.state.get("workflow_steps_completed"),
        }
