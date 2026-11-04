"""
Agent 4: Healthcare Knowledge RAG Agent
=========================================
Purpose: Answers general healthcare knowledge questions using RAG over
         indexed healthcare guidelines, WHO documents, government health
         schemes, and local facility knowledge bases.

Responsibilities:
  - Answer patient questions about healthcare services, conditions, and processes
  - Retrieve relevant information from indexed documents
  - Explain government health schemes eligibility
  - Provide general health education (NOT diagnosis)
  - Cite sources for every answer (explainability)
  - Flag low-confidence answers with appropriate warnings
"""

from typing import Any, Optional
from langchain_core.messages import SystemMessage, HumanMessage

from agents.llm_factory import get_llm
from rag.retriever import rag_pipeline
from utils.logger import app_logger, audit_logger


SYSTEM_PROMPT = """You are a Healthcare Knowledge Assistant with access to verified healthcare documents.

Your role is to answer general healthcare questions using information from:
- WHO and Ministry of Health & Family Welfare (MoHFW) guidelines
- Government health scheme information (Ayushman Bharat, PMJAY, NHM)
- Healthcare facility information
- Emergency response protocols
- General health education materials

CRITICAL RULES:
1. ONLY use information from the retrieved context provided to you
2. Do NOT make up medical facts — if you don't have the information, say so clearly
3. NEVER provide specific diagnoses, treatment plans, or drug prescriptions
4. ALWAYS cite your source at the end: "Source: [document name]"
5. For low-confidence answers (context < 0.5 relevance), add: "⚠️ Low confidence — please consult a healthcare professional"
6. Focus on:
   - What services are available
   - How to access government health schemes
   - General prevention and health education
   - What to expect at different types of healthcare facilities
   - How to prepare for a medical visit

If the retrieved context does not contain relevant information for the query,
say: "I don't have specific information on this in my knowledge base. 
I recommend calling the National Health Helpline: 104 for guidance."
"""


class RAGKnowledgeAgent:
    """
    Agent 4: Healthcare Knowledge RAG Agent

    Collections searched:
        - healthcare_guidelines (primary)
        - government_schemes
        - emergency_protocols

    State maintained:
        - queries_answered
        - sources_cited
        - low_confidence_count
    """

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.agent_name = "RAGKnowledgeAgent"
        self.llm = get_llm(temperature=0.1)  # Very low temp for factual answers

        self.state: dict[str, Any] = {
            "queries_answered": 0,
            "sources_cited": [],
            "low_confidence_count": 0,
        }

    def run(
        self,
        query: str,
        collection_hint: Optional[str] = None,
        max_results: int = 5,
    ) -> dict[str, Any]:
        """
        Answer a healthcare knowledge query using RAG.

        Args:
            query: Patient's knowledge question
            collection_hint: Preferred collection to search first
            max_results: Number of RAG results to retrieve

        Returns:
            dict with answer_text, sources, confidence_level, retrieved_chunks
        """
        import time
        start_time = time.time()
        self.state["queries_answered"] += 1

        # ── Step 1: Determine best collection to search ─────────────────
        collections_to_try = self._determine_collections(query, collection_hint)

        # ── Step 2: RAG Retrieval ────────────────────────────────────────
        all_results = []
        best_context = ""

        for collection in collections_to_try:
            rag_result = rag_pipeline.query(
                query_text=query,
                collection_name=collection,
                top_k=max_results,
                session_id=self.session_id,
            )
            if rag_result.get("success") and rag_result.get("results"):
                all_results.extend(rag_result["results"])
                if not best_context:
                    best_context = rag_result.get("context", "")

        # Sort by relevance
        all_results.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
        top_results = all_results[:max_results]

        # ── Step 3: Assess retrieval quality ────────────────────────────
        avg_relevance = (
            sum(r.get("relevance_score", 0) for r in top_results) / len(top_results)
            if top_results else 0
        )
        confidence_level = (
            "high" if avg_relevance > 0.75
            else "medium" if avg_relevance > 0.50
            else "low"
        )

        if confidence_level == "low":
            self.state["low_confidence_count"] += 1

        # ── Step 4: Build LLM prompt with RAG context ───────────────────
        if best_context:
            context_section = f"""
RETRIEVED KNOWLEDGE (from healthcare guidelines):
{best_context}

Average Relevance Score: {avg_relevance:.2f}
"""
        else:
            context_section = "NO RELEVANT DOCUMENTS FOUND IN KNOWLEDGE BASE."

        prompt = f"""Patient Question: {query}

{context_section}

Confidence Level based on retrieved context: {confidence_level.upper()}

Please answer the question using ONLY the retrieved context above.
End your answer with: "Source: [document names from context]"
If confidence is low, add a warning to consult a healthcare professional."""

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ]

        try:
            response = self.llm.invoke(messages)
            answer_text = response.content if hasattr(response, "content") else str(response)
        except Exception as e:
            app_logger.error(f"LLM error in RAGKnowledgeAgent: {e}")
            answer_text = (
                "I'm unable to retrieve information at this time. "
                "For healthcare guidance, please call:\n"
                "- National Health Helpline: 104 (free, 24×7)\n"
                "- ASHA/ANM in your village for local guidance"
            )

        # ── Extract sources ──────────────────────────────────────────────
        sources = list({r.get("source", "Unknown") for r in top_results})
        self.state["sources_cited"].extend(sources)

        # ── Audit logging ────────────────────────────────────────────────
        duration_ms = (time.time() - start_time) * 1000
        audit_logger.log(
            session_id=self.session_id,
            action_type="rag_query",
            agent_name=self.agent_name,
            action=f"knowledge_query: {query[:80]}",
            outcome="success" if top_results else "no_results",
            metadata={
                "collections_searched": collections_to_try,
                "results_found": len(top_results),
                "avg_relevance": round(avg_relevance, 3),
                "confidence": confidence_level,
                "sources": sources,
            },
            duration_ms=duration_ms,
        )

        return {
            "agent": self.agent_name,
            "query": query,
            "answer_text": answer_text,
            "confidence_level": confidence_level,
            "avg_relevance_score": round(avg_relevance, 3),
            "sources": sources,
            "retrieved_chunks": top_results,
            "collections_searched": collections_to_try,
            "rag_available": len(top_results) > 0,
            "disclaimer": (
                "This information is for educational and navigation purposes only. "
                "Always consult a qualified healthcare professional for medical advice."
            ),
        }

    def _determine_collections(self, query: str, hint: Optional[str]) -> list[str]:
        """Select most relevant collections for a query."""
        query_lower = query.lower()

        if hint and hint in rag_pipeline.COLLECTIONS:
            return [hint] + [c for c in rag_pipeline.COLLECTIONS if c != hint]

        if any(w in query_lower for w in ["emergency", "ambulance", "first aid", "critical"]):
            return ["emergency_protocols", "healthcare_guidelines"]
        if any(w in query_lower for w in ["scheme", "ayushman", "pmjay", "free", "government", "nhm"]):
            return ["government_schemes", "healthcare_guidelines"]
        if any(w in query_lower for w in ["hospital", "facility", "clinic", "doctor", "department"]):
            return ["facility_knowledge", "healthcare_guidelines"]

        return ["healthcare_guidelines", "government_schemes"]

    def get_state(self) -> dict[str, Any]:
        return self.state.copy()
