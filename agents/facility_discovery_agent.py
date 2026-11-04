"""
Agent 2: Healthcare Facility Discovery Agent
============================================
Purpose: Searches and ranks healthcare facilities based on patient location,
         healthcare need, facility type, government vs private preference,
         accessibility, availability, and accreditation.

Responsibilities:
  - Execute facility searches using healthcare_tools
  - Compare and rank facilities by multiple criteria
  - Filter for government/free facilities for low-income patients
  - Find specialists linked to discovered facilities
  - Provide structured facility comparison with explainability factors
  - Maintain search history in session state
"""

from typing import Any, Optional
from langchain_core.messages import SystemMessage, HumanMessage

from agents.llm_factory import get_llm
from tools.healthcare_tools import (
    search_healthcare_facilities,
    find_specialists,
    check_appointment_availability,
)
from utils.logger import app_logger, audit_logger


SYSTEM_PROMPT = """You are a Healthcare Facility Discovery Specialist for rural India.

Your role is to help patients find the most suitable healthcare facility based on their specific needs.

WHEN PRESENTING FACILITIES:
1. Always lead with the most accessible government facility (free/subsidized care)
2. Mention distance, wait times, and available services clearly
3. Highlight if the facility has emergency services or ICU
4. Note if telemedicine is available (reduces travel for follow-ups)
5. Always provide the facility phone number

COMPARISON CRITERIA (explain these):
- Distance/accessibility from patient location
- Type of care needed vs. facility capability
- Government vs. private (cost considerations)
- Availability and wait times
- Accreditation (NABH/NABL certification)
- Available departments and specialists

IMPORTANT:
- Do NOT recommend specific doctors by name from memory — only use the data provided
- Always note that "availability is subject to change, please call before visiting"
- If no specialist is available locally, mention telemedicine or referral to district hospital
- Highlight government schemes: Ayushman Bharat, PMJAY, State health schemes

Format your response as a clear, easy-to-read comparison with numbered options.
"""


class FacilityDiscoveryAgent:
    """
    Agent 2: Healthcare Facility Discovery Agent

    State maintained:
        - discovered_facilities (list of facility dicts)
        - discovered_specialists (list)
        - last_search_criteria
        - search_count
    """

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.agent_name = "FacilityDiscoveryAgent"
        self.llm = get_llm(temperature=0.2)

        self.state: dict[str, Any] = {
            "discovered_facilities": [],
            "discovered_specialists": [],
            "last_search_criteria": {},
            "search_count": 0,
            "top_recommendation_id": None,
        }

    def run(
        self,
        district: str,
        state_name: str,
        departments: list[str],
        urgency_level: str = "low",
        facility_type: Optional[str] = None,
        government_only: bool = False,
        find_specialists_flag: bool = True,
    ) -> dict[str, Any]:
        """
        Discover and rank healthcare facilities for a patient.

        Args:
            district: Patient's district
            state_name: Patient's state
            departments: Required departments from assessment agent
            urgency_level: low | medium | high | emergency
            facility_type: Specific facility type filter
            government_only: Show only government facilities
            find_specialists_flag: Also search for relevant specialists

        Returns:
            dict with facilities, specialists, comparison_text, top_recommendation
        """
        import time
        start_time = time.time()
        self.state["search_count"] += 1

        # ── Tool Call 1: Search Facilities ───────────────────────────────
        requires_emergency = urgency_level in ["high", "emergency"]
        requires_24x7 = urgency_level == "emergency"

        primary_department = departments[0] if departments else None

        facility_results = search_healthcare_facilities(
            district=district,
            state=state_name,
            facility_type=facility_type,
            department=primary_department,
            requires_emergency=requires_emergency,
            requires_24x7=requires_24x7,
            government_only=government_only,
            max_results=8,
        )

        self.state["discovered_facilities"] = facility_results.get("facilities", [])
        self.state["last_search_criteria"] = facility_results.get("search_criteria", {})

        # ── Tool Call 2: Find Specialists ────────────────────────────────
        specialist_results = {"specialists": []}
        if find_specialists_flag and departments:
            specialist_results = find_specialists(
                specialty=primary_department or "General Medicine",
                district=district,
                state=state_name,
                telemedicine_only=False,
                max_results=5,
            )
            self.state["discovered_specialists"] = specialist_results.get("specialists", [])

        # ── Determine top recommendation ─────────────────────────────────
        top_facility = None
        if self.state["discovered_facilities"]:
            # Score = rating * 0.4 + (1/distance) * 0.3 + government_bonus * 0.2 + emergency * 0.1
            for f in self.state["discovered_facilities"]:
                dist = f.get("distance_km") or 50
                score = (
                    (f.get("rating") or 0) * 0.4
                    + (1 / max(dist, 0.1)) * 0.3 * 10
                    + (0.2 if f.get("is_government") else 0)
                    + (0.1 if f.get("has_emergency") and requires_emergency else 0)
                )
                f["_score"] = round(score, 3)

            sorted_facilities = sorted(
                self.state["discovered_facilities"],
                key=lambda x: x.get("_score", 0),
                reverse=True,
            )
            top_facility = sorted_facilities[0] if sorted_facilities else None
            if top_facility:
                self.state["top_recommendation_id"] = top_facility.get("id")

        # ── Build LLM prompt with tool results ───────────────────────────
        facilities_text = self._format_facilities_for_prompt(self.state["discovered_facilities"])
        specialists_text = self._format_specialists_for_prompt(self.state["discovered_specialists"])

        prompt = f"""Patient Location: {district}, {state_name}
Urgency Level: {urgency_level.upper()}
Healthcare Need / Departments: {', '.join(departments)}

DISCOVERED FACILITIES (from database search):
{facilities_text}

DISCOVERED SPECIALISTS:
{specialists_text}

TOP SCORED FACILITY: {top_facility.get('name', 'N/A') if top_facility else 'None found'}

Please provide a helpful, clear summary comparing these healthcare options for the patient.
Explain WHY the top facility is recommended (decision factors).
Include phone numbers and any relevant government scheme information.
If no facilities are found in the district, suggest nearby district hospitals or referral options."""

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ]

        try:
            response = self.llm.invoke(messages)
            comparison_text = response.content if hasattr(response, "content") else str(response)
        except Exception as e:
            app_logger.error(f"LLM error in FacilityDiscoveryAgent: {e}")
            comparison_text = self._fallback_summary(self.state["discovered_facilities"], top_facility)

        # ── Audit logging ────────────────────────────────────────────────
        duration_ms = (time.time() - start_time) * 1000
        audit_logger.log(
            session_id=self.session_id,
            action_type="agent_call",
            agent_name=self.agent_name,
            action=f"facility_discovery (district={district}, dept={primary_department})",
            outcome="success" if self.state["discovered_facilities"] else "no_results",
            metadata={
                "facilities_found": len(self.state["discovered_facilities"]),
                "specialists_found": len(self.state["discovered_specialists"]),
                "top_facility": top_facility.get("name") if top_facility else None,
            },
            duration_ms=duration_ms,
        )

        return {
            "agent": self.agent_name,
            "comparison_text": comparison_text,
            "facilities": self.state["discovered_facilities"],
            "specialists": self.state["discovered_specialists"],
            "top_recommendation": top_facility,
            "top_recommendation_id": self.state["top_recommendation_id"],
            "total_facilities_found": len(self.state["discovered_facilities"]),
            "total_specialists_found": len(self.state["discovered_specialists"]),
            "decision_factors": self._get_decision_factors(top_facility),
            "search_criteria": self.state["last_search_criteria"],
        }

    def _format_facilities_for_prompt(self, facilities: list) -> str:
        """Format facility list for LLM context."""
        if not facilities:
            return "No facilities found in database for this location."
        lines = []
        for i, f in enumerate(facilities[:5], 1):
            lines.append(
                f"{i}. {f.get('name')} ({f.get('type')}) | "
                f"{'Government' if f.get('is_government') else 'Private'} | "
                f"Dist: {f.get('distance_km', 'N/A')} km | "
                f"Phone: {f.get('phone', 'N/A')} | "
                f"Emergency: {'Yes' if f.get('has_emergency') else 'No'} | "
                f"Beds: {f.get('available_beds', 'N/A')} | "
                f"Rating: {f.get('rating', 'N/A')} | "
                f"Score: {f.get('_score', 'N/A')}"
            )
        return "\n".join(lines)

    def _format_specialists_for_prompt(self, specialists: list) -> str:
        """Format specialist list for LLM context."""
        if not specialists:
            return "No specialists found in database for this location."
        lines = []
        for i, s in enumerate(specialists[:3], 1):
            lines.append(
                f"{i}. Dr. {s.get('name')} ({s.get('specialty')}) | "
                f"Facility: {s.get('facility_name', 'N/A')} | "
                f"Days: {s.get('available_days', [])} | "
                f"Fee: ₹{s.get('consultation_fee', 0)} | "
                f"Telemedicine: {'Yes' if s.get('telemedicine_available') else 'No'}"
            )
        return "\n".join(lines)

    def _fallback_summary(self, facilities: list, top: Optional[dict]) -> str:
        """Fallback text if LLM is unavailable."""
        if not facilities:
            return "No healthcare facilities found for this location. Please contact health helpline 104."
        top_name = top.get("name", "N/A") if top else facilities[0].get("name", "N/A")
        top_phone = top.get("phone", "N/A") if top else facilities[0].get("phone", "N/A")
        return (
            f"Based on your location, the recommended facility is **{top_name}**.\n"
            f"Phone: {top_phone}\n\n"
            f"Total {len(facilities)} facilities found. "
            "Please call the facility before visiting to confirm availability."
        )

    def _get_decision_factors(self, top_facility: Optional[dict]) -> list[str]:
        """Generate explainability factors for top recommendation."""
        if not top_facility:
            return ["No facilities found in the database for this location."]
        factors = []
        if top_facility.get("is_government"):
            factors.append("Government facility — free/subsidized services available")
        if top_facility.get("rating"):
            factors.append(f"High patient rating: {top_facility['rating']}/5")
        if top_facility.get("distance_km"):
            factors.append(f"Proximity: {top_facility['distance_km']} km from your area")
        if top_facility.get("has_emergency"):
            factors.append("24-hour emergency services available")
        if top_facility.get("accreditation"):
            factors.append(f"{top_facility['accreditation']} accredited facility")
        if top_facility.get("available_beds"):
            factors.append(f"{top_facility['available_beds']} beds currently available")
        return factors or ["Best match based on location and service availability"]

    def get_state(self) -> dict[str, Any]:
        return self.state.copy()
