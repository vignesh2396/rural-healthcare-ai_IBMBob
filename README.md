# 🏥 Rural Healthcare AI Navigation System

<div align="center">

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![LangChain](https://img.shields.io/badge/LangChain-1.x-1C3C3C?logo=chainlink&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.66-FF4B4B?logo=streamlit&logoColor=white)
![Google Gemini](https://img.shields.io/badge/Gemini-2.0%20Flash-4285F4?logo=google&logoColor=white)
![Tests](https://img.shields.io/badge/Tests-23%2F23%20Passing-2ECC71?logo=pytest&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-blue)
![IBM SkillsBuild](https://img.shields.io/badge/IBM%20SkillsBuild-Agentic%20AI%20Capstone-054ADA?logo=ibm&logoColor=white)

**An Agentic AI-Powered Patient Navigation & Referral Coordination System for Rural India**

[🚀 Quick Start](#-quick-start) · [🤖 Architecture](#-ai-agent-architecture) · [🧪 Testing](#-testing) · [📊 Impact](#-expected-impact) · [🔮 Roadmap](#-future-roadmap)

</div>

> ⚠️ **Medical Disclaimer**: This system is a **navigation support tool only**. It does **NOT** provide medical diagnoses, prescribe medications, or replace qualified healthcare professionals. For emergencies, call **108** immediately.

---

## 📋 Table of Contents

1. [Project Overview](#-project-overview)
2. [Problem Statement](#-problem-statement)
3. [Target Users](#-target-users)
4. [AI Agent Architecture](#-ai-agent-architecture)
5. [Technology Stack](#-technology-stack)
6. [Quick Start](#-quick-start)
7. [Installation](#-installation)
8. [Configuration](#️-configuration)
9. [Running the Application](#-running-the-application)
10. [Testing](#-testing)
11. [Project Structure](#-project-structure)
12. [Responsible AI](#️-responsible-ai)
13. [Expected Impact](#-expected-impact)
14. [Future Roadmap](#-future-roadmap)
15. [Emergency Contacts](#-emergency-contacts)

---

## 🎯 Project Overview

The **Rural Healthcare AI Navigation System** is a production-ready **Agentic AI prototype** that helps patients in rural and semi-urban regions of India navigate healthcare services. It identifies appropriate facilities, compares care options, coordinates referrals, and guides patients through the healthcare journey — all without attempting to diagnose conditions or replace medical professionals.

| Property | Value |
|----------|-------|
| **Domain** | Healthcare / Digital Health |
| **Category** | Patient Navigation & Referral Coordination |
| **Framework** | LangChain Multi-Agent Architecture |
| **UI** | Streamlit |
| **LLM** | Google Gemini 2.0 Flash (+ OpenAI / Groq fallback) |
| **Test Coverage** | 23/23 unit tests passing |
| **Built for** | IBM SkillsBuild Agentic AI Capstone Program 2026 |

---

## 🌾 Problem Statement

Patients in rural areas of India face:

| Challenge | Detail |
|-----------|--------|
| **Distance** | Average 4–8 km to nearest PHC; 30+ km to district hospitals |
| **Awareness Gap** | Lack of knowledge about available services and government schemes (PMJAY, eSanjeevani) |
| **Fragmented Referrals** | Poor coordination between PHC → CHC → District Hospital |
| **Tertiary Overcrowding** | Patients traveling to city hospitals for conditions treatable locally |
| **Language Barriers** | Healthcare information not available in local languages |

**This system addresses all five challenges through AI-guided navigation.**

---

## 👥 Target Users

| User | Description |
|------|-------------|
| 👨‍🌾 **Rural Patient** | Primary user seeking healthcare navigation |
| 👩‍⚕️ **ASHA/ANM Worker** | Community health worker helping patients |
| 🏥 **Healthcare Administrator** | Monitors referral patterns |
| 📊 **District Health Officer** | Analyzes healthcare access gaps |

---

## 🤖 AI Agent Architecture

```
Patient Query
     │
     ▼
┌─────────────────────────────┐
│      Supervisor Agent       │  ← Orchestrates all agents, maintains state
│   (Router + State Manager)  │
└──────────────┬──────────────┘
               │
    ┌──────────┴───────────────────────────────┐
    │                                          │
    ▼                                          ▼
┌───────────────┐                    ┌──────────────────┐
│  Assessment   │                    │    Emergency     │  ← BYPASS (immediate)
│    Agent      │                    │  Escalation      │  ← Temp: 0.0
│  (Temp: 0.1)  │                    │    Agent         │  ← Hardcoded fallback
└──────┬────────┘                    └──────────────────┘
       │
       ▼
┌──────────────────┐
│    Facility      │  ← Tool: search_healthcare_facilities()
│  Discovery Agent │  ← Tool: find_specialists()
└──────┬───────────┘  ← Haversine distance ranking
       │
       ▼
┌──────────────────┐    ┌──────────────────────┐
│    Referral      │    │   RAG Knowledge      │  ← TF-IDF in-memory
│  Planning Agent  │    │      Agent           │  ← 4 collections
└──────┬───────────┘    └──────────────────────┘  ← Top-K = 5
       │
       ▼
┌──────────────────────────┐
│  Appointment Coordination │  ← Tool: check_appointment_availability()
│         Agent             │  ← Guidance only (no actual booking)
└──────────────────────────┘
```

### Agent Responsibilities

| Agent | Temperature | Responsibilities | Tools |
|-------|------------|-----------------|-------|
| **Supervisor Agent** | — | Orchestrates workflow, routes messages, session state | All agents |
| **Assessment Agent** | 0.1 | Collects location, assesses urgency, maps departments | `assess_urgency()`, `map_symptoms_to_departments()` |
| **Facility Discovery Agent** | 0.2 | Searches & ranks facilities by distance + type | `search_healthcare_facilities()`, `find_specialists()` |
| **Referral Planning Agent** | 0.2 | Creates REF-XXXXXXXX referral with step-by-step plan | `generate_referral_summary()`, `log_navigation_step()` |
| **RAG Knowledge Agent** | 0.2 | Answers knowledge queries with source citations | TF-IDF retriever, ChromaDB-ready |
| **Appointment Coordination Agent** | 0.2 | Guides appointment booking process | `check_appointment_availability()` |
| **Emergency Escalation Agent** | 0.0 | **BYPASSES** normal workflow on emergency keywords | Hardcoded + LLM fallback |

### Emergency Bypass (Critical Safety Feature)

When any of these keywords are detected, the system **bypasses all normal workflow stages** and immediately activates the Emergency Escalation Agent — before any LLM call:

```
chest pain · not breathing · unconscious · stroke · arm weakness · 
severe bleeding · suicide · ending my life · self harm · labor pain · eclampsia
```

The Emergency Agent:
- Always starts with `🚨 CALL 108 IMMEDIATELY`
- Has a **hardcoded fallback response** that works even if the LLM API is down
- Sets `human_review_required = True` in session state
- Writes a `action_type=escalation` entry to the audit log

---

## 🛠️ Technology Stack

| Category | Technology | Version |
|----------|-----------|---------|
| **LLM (Primary)** | Google Gemini 2.0 Flash | `langchain-google-genai>=1.0.0` |
| **LLM (Fallback 1)** | OpenAI GPT-4o-mini | `langchain-openai>=0.1.0` |
| **LLM (Fallback 2)** | Groq qwen3.8-27b | `langchain-groq>=0.1.0` |
| **AI Framework** | LangChain | `>=1.0.0` |
| **RAG** | TF-IDF in-memory (ChromaDB swap-in ready) | `scikit-learn` |
| **Vector Search** | Cosine similarity + keyword overlap fallback | — |
| **Database** | SQLite + SQLAlchemy ORM | `>=2.0.0` |
| **Interface** | Streamlit | `>=1.32.0` |
| **Logging** | Python logging (structured JSON) + Audit trail | — |
| **Testing** | pytest | `9.2.0` |
| **Video Generation** | MoviePy + Pillow | `1.0.3` / `>=13.0` |
| **Configuration** | python-dotenv | `>=1.0.0` |

---

## 🚀 Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/vignesh2396/rural-healthcare-ai_IBMBob.git
cd rural-healthcare-ai_IBMBob

# 2. Create and activate virtual environment
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up your API key
cp .env.example .env
# Edit .env and add: GOOGLE_API_KEY=your_key_here

# 5. Run the app
streamlit run app.py
```

The app opens at **http://localhost:8501** 🎉

Get a **free** Google Gemini API key at: https://ai.google.dev

---

## 📦 Installation

### Prerequisites

- Python **3.10** or higher
- `pip` package manager
- One of: Google Gemini API key (free) · OpenAI API key · Groq API key

### Step-by-Step

```bash
# Clone
git clone https://github.com/vignesh2396/rural-healthcare-ai_IBMBob.git
cd rural-healthcare-ai_IBMBob

# Virtual environment (recommended)
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux

# Install all dependencies
pip install -r requirements.txt

# Verify installation
python -c "import streamlit, langchain, langchain_google_genai; print('✅ All core packages installed')"
```

### Docker (Alternative)

```bash
docker-compose up --build
# App available at http://localhost:8501
```

---

## ⚙️ Configuration

### Step 1 — Copy environment template

```bash
cp .env.example .env
```

### Step 2 — Add your API key to `.env`

```env
# ── LLM Configuration ─────────────────────────────────────
# Get free key at https://ai.google.dev
GOOGLE_API_KEY=your_actual_google_api_key_here

LLM_PROVIDER=google
LLM_MODEL=gemini-2.0-flash-exp
LLM_TEMPERATURE=0.2
LLM_MAX_TOKENS=4096

# ── Optional fallbacks ─────────────────────────────────────
# OPENAI_API_KEY=sk-...
# GROQ_API_KEY=gsk_...

# ── Application ────────────────────────────────────────────
APP_ENV=development
DEBUG=true
```

### Free API Key Options

| Provider | Free Tier | Sign Up URL |
|----------|-----------|-------------|
| 🥇 Google Gemini | ✅ Generous free tier | https://ai.google.dev |
| 🥈 Groq | ✅ Rate-limited free | https://console.groq.com |
| 🥉 OpenAI | Trial credits | https://platform.openai.com |

---

## 🏃 Running the Application

```bash
streamlit run app.py
```

Opens at: **http://localhost:8501**

### Quick Test Inputs

**1. Standard Navigation:**
```
I am from Nashik, Maharashtra. I have chest discomfort for 2 days.
I need to see a cardiologist at a government hospital.
```

**2. Pregnancy Care:**
```
I am 7 months pregnant in Nashik. I need a gynecologist.
I cannot travel far. Is telemedicine available?
```

**3. Knowledge Query:**
```
What is the Ayushman Bharat scheme? How much coverage? Who is eligible?
```

**4. Emergency Test** ⚠️ *(triggers emergency mode)*:
```
My father has chest pain, left arm pain, and is sweating a lot.
```

**5. Mental Health:**
```
I am feeling very depressed. I need help. iCall number please.
```

---

## 🧪 Testing

### Run All Unit Tests

```bash
pytest tests/test_unit.py -v
```

**Result: 23/23 tests passing in 1.39 s**

```
tests/test_unit.py::TestUrgencyAssessment::test_emergency_chest_pain        PASSED
tests/test_unit.py::TestUrgencyAssessment::test_emergency_stroke_keywords   PASSED
tests/test_unit.py::TestUrgencyAssessment::test_medium_urgency_fever        PASSED
tests/test_unit.py::TestUrgencyAssessment::test_low_urgency_routine         PASSED
tests/test_unit.py::TestUrgencyAssessment::test_emergency_keywords_returned PASSED
tests/test_unit.py::TestUrgencyAssessment::test_disclaimer_always_present   PASSED
tests/test_unit.py::TestUrgencyAssessment::test_mental_health_crisis        PASSED
tests/test_unit.py::TestDepartmentMapping::test_cardiac_mapping             PASSED
tests/test_unit.py::TestDepartmentMapping::test_orthopedic_mapping          PASSED
tests/test_unit.py::TestDepartmentMapping::test_gynecology_mapping          PASSED
tests/test_unit.py::TestDepartmentMapping::test_pediatric_mapping           PASSED
tests/test_unit.py::TestDepartmentMapping::test_unknown_symptoms_fallback   PASSED
tests/test_unit.py::TestDepartmentMapping::test_result_has_disclaimer       PASSED
tests/test_unit.py::TestReferralGeneration::test_referral_id_format         PASSED
tests/test_unit.py::TestReferralGeneration::test_referral_contains_...      PASSED
tests/test_unit.py::TestHaversineDistance::test_same_location_zero_distance PASSED
tests/test_unit.py::TestHaversineDistance::test_known_distance_mumbai_pune  PASSED
tests/test_unit.py::TestDatabaseInitialization::test_db_tables_created      PASSED
tests/test_unit.py::TestDatabaseInitialization::test_session_creation...    PASSED
tests/test_unit.py::TestSettingsValidation::test_settings_load              PASSED
tests/test_unit.py::TestSettingsValidation::test_settings_validate_returns  PASSED
tests/test_unit.py::TestEmergencyBypass::test_emergency_keywords_trigger    PASSED
tests/test_unit.py::TestEmergencyBypass::test_mental_health_fallback        PASSED

======================= 23 passed in 1.39s =======================
```

### Run Specific Test Categories

```bash
pytest tests/ -k "urgency"      # Urgency detection tests
pytest tests/ -k "department"   # Department mapping tests
pytest tests/ -k "emergency"    # Emergency bypass tests
pytest tests/ -k "facility"     # Facility search tests
```

### Scenario Test Cases

See [`tests/test_cases.md`](tests/test_cases.md) for 10 detailed manual test scenarios including:

| ID | Scenario | Priority |
|----|----------|----------|
| TC-01 | Standard patient navigation (Nashik, cardiac) | High |
| TC-02 | Telemedicine preference (pregnant, remote) | High |
| TC-03 | Missing location information | Medium |
| TC-04 | Gibberish / invalid input | Medium |
| TC-05 | **Cardiac emergency detection** | 🔴 Critical |
| TC-06 | **Mental health crisis** | 🔴 Critical |
| TC-07 | Government scheme knowledge query | High |
| TC-08 | RAG no-result handling | Medium |
| TC-09 | Tool failure resilience | Medium |
| TC-10 | Low confidence — remote specialist | Medium |

---

## 📁 Project Structure

```
rural-healthcare-ai_IBMBob/
│
├── app.py                              # Main Streamlit application (entry point)
├── requirements.txt                    # Python dependencies (pinned versions)
├── .env.example                        # Environment variable template
├── .gitignore                          # Git ignore patterns
├── Dockerfile                          # Docker container definition
├── docker-compose.yml                  # Docker Compose setup
├── generate_video.py                   # Slideshow video generator (moviepy)
│
├── agents/                             # AI Agent modules
│   ├── __init__.py
│   ├── supervisor_agent.py             # Orchestrator (central router + state)
│   ├── assessment_agent.py             # Agent 1: Patient assessment (Temp 0.1)
│   ├── facility_discovery_agent.py     # Agent 2: Facility search & ranking
│   ├── referral_agent.py               # Agent 3: Referral planning (REF-XXXXXXXX)
│   ├── rag_knowledge_agent.py          # Agent 4: RAG knowledge retrieval
│   ├── appointment_agent.py            # Agent 5: Appointment coordination
│   ├── emergency_agent.py              # Agent 6: Emergency escalation (Temp 0.0)
│   └── llm_factory.py                  # Provider-agnostic LLM initialization
│
├── tools/                              # Custom LangChain-compatible tools
│   ├── __init__.py
│   └── healthcare_tools.py             # 5 tools: urgency, dept, facilities, referral, appt
│
├── rag/                                # RAG pipeline
│   ├── __init__.py
│   ├── retriever.py                    # TF-IDF in-memory RAG pipeline
│   └── documents/                      # Knowledge base documents
│       ├── healthcare_guidelines.txt
│       └── emergency_protocols.txt
│
├── utils/                              # Utility modules
│   ├── __init__.py
│   ├── database.py                     # SQLAlchemy models + init
│   └── logger.py                       # Structured logging + audit trail
│
├── config/                             # Configuration
│   ├── __init__.py
│   └── settings.py                     # Environment-based settings (12 parameters)
│
├── tests/                              # Test suite
│   ├── test_unit.py                    # 23 pytest unit tests (100% passing)
│   └── test_cases.md                   # 10 manual scenario test cases
│
├── data/                               # Data directory
│   └── healthcare.db                   # SQLite database (auto-created on first run)
│
├── logs/                               # Log files (auto-created)
│   ├── app.log                         # Application log
│   └── audit.log                       # Audit trail (all agent actions)
│
├── docs/                               # Documentation
├── assets/                             # Architecture diagrams, screenshots
├── .streamlit/
│   └── config.toml                     # Streamlit theme configuration
│
├── Rural_Healthcare_AI_Presentation.pptx  # 16-slide project presentation
└── Rural_Healthcare_AI_Slideshow.mp4      # 1.6-min project video (720p)
```

---

## 🛡️ Responsible AI

This system implements the following responsible AI principles aligned with IBM AI Ethics guidelines:

| Principle | Implementation |
|-----------|---------------|
| 🚫 **No Diagnosis** | Agents explicitly refuse to diagnose or prescribe |
| 👥 **Human-in-the-Loop** | Emergencies flagged `human_review_required=True` |
| 🔍 **Transparency** | Every recommendation includes `decision_factors[]` |
| 🔒 **Privacy** | Minimal PII collection; PII masked in all logs |
| ⚡ **Emergency First** | Emergency bypass fires **before** any LLM call |
| 📋 **Audit Trail** | All agent actions logged: `session_id`, `action_type`, `outcome`, `duration_ms` |
| 💬 **Disclaimers** | Medical disclaimer shown on **every** interaction |
| 🎯 **Explainability** | Sources cited, confidence levels disclosed in RAG responses |

---

## 📊 Expected Impact

| Metric | Target |
|--------|--------|
| Reduction in unnecessary tertiary visits | **25–40%** |
| Time to identify appropriate facility | **< 3 minutes** |
| Government scheme awareness improvement | **60%+** of users |
| Emergency response guidance time | **< 30 seconds** |
| Patient navigation completion rate | **> 80%** |

---

## 🔮 Future Roadmap

- [ ] 🌐 Regional language support (Hindi, Marathi, Tamil, Telugu)
- [ ] 📡 Real-time bed availability via NHM APIs
- [ ] 💳 ABHA (Ayushman Bharat Health Account) integration
- [ ] 📱 SMS/WhatsApp referral delivery
- [ ] 👩‍⚕️ ASHA worker mobile app (offline-capable)
- [ ] 📞 eSanjeevani real telemedicine platform integration
- [ ] 🔇 Offline mode for poor connectivity areas
- [ ] 🎙️ Voice interface for zero-literacy users

---

## ⚠️ Known Limitations

1. **Navigation only** — does NOT diagnose conditions or prescribe treatments
2. **Facility data** — sample data for demo; production needs real facility database
3. **RAG quality** — depends on completeness of indexed knowledge documents
4. **Real-time data** — appointment slots and bed availability are not live
5. **Language** — currently English-focused; regional language support is roadmap item
6. **Telemedicine** — guidance only; no actual platform integration
7. **Emergency detection** — keyword-based, not clinical-grade NLU

---

## 📞 Emergency Contacts

> These numbers are always displayed in the app, regardless of system state.

| Service | Number |
|---------|--------|
| 🚑 Ambulance | **108 / 102** |
| ⚕️ Health Helpline | **104** |
| 🆘 Mental Health (iCall) | **9152987821** |
| 🧠 KIRAN Helpline | **1800-599-0019** |
| 🚔 Police | **100** |
| 🔥 Fire | **101** |

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit changes: `git commit -m 'feat: add your feature'`
4. Push to branch: `git push origin feature/your-feature`
5. Open a Pull Request

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">

**Built as part of IBM SkillsBuild Agentic AI Capstone Program 2026**

*Domain: Healthcare / Digital Health · Framework: LangChain · LLM: Google Gemini 2.0 Flash*

⚠️ *Always seek qualified medical care. This AI system cannot replace a doctor.*

</div>
