"""
Configuration Management Module
================================
Purpose: Centralized configuration for the Rural Healthcare AI system.
         Loads environment variables, sets defaults, and validates critical settings.
Dependencies: python-dotenv, pydantic
"""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

_ENV_FILE = Path(__file__).parent.parent / ".env"


class Settings:
    """Application settings loaded from environment variables."""

    def __init__(self):
        # Always re-read the .env file so Streamlit hot-reloads pick up changes
        load_dotenv(_ENV_FILE, override=True)

        # ─── LLM Configuration ───────────────────────────────────────────────────
        self.GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
        self.OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
        self.LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "google")          # google | openai | groq
        self.LLM_MODEL: str = os.getenv("LLM_MODEL", "gemini-2.0-flash-exp")
        self.LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.2"))
        self.LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "4096"))

        # ─── Groq (free-tier fallback) ────────────────────────────────────────────
        self.GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
        self.GROQ_MODEL: str = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")

        # ─── Application ─────────────────────────────────────────────────────────
        self.APP_NAME: str = "Rural Healthcare AI Navigation System"
        self.APP_VERSION: str = "1.0.0"
        self.APP_ENV: str = os.getenv("APP_ENV", "development")              # development | production
        self.DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"
        self.SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-in-production-32chars!")
        self.LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

        # ─── Database ─────────────────────────────────────────────────────────────
        self.DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./data/healthcare.db")
        self.DB_ECHO: bool = os.getenv("DB_ECHO", "false").lower() == "true"

        # ─── RAG / Vector Store ───────────────────────────────────────────────────
        self.CHROMA_PERSIST_DIR: str = os.getenv("CHROMA_PERSIST_DIR", "./rag/chroma_db")
        self.RAG_CHUNK_SIZE: int = int(os.getenv("RAG_CHUNK_SIZE", "500"))
        self.RAG_CHUNK_OVERLAP: int = int(os.getenv("RAG_CHUNK_OVERLAP", "50"))
        self.RAG_TOP_K: int = int(os.getenv("RAG_TOP_K", "5"))
        self.EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "models/embedding-001")

        # ─── Healthcare Facility Data ─────────────────────────────────────────────
        self.FACILITY_DATA_PATH: str = os.getenv("FACILITY_DATA_PATH", "./data/healthcare_facilities.csv")
        self.SPECIALIST_DATA_PATH: str = os.getenv("SPECIALIST_DATA_PATH", "./data/specialists.csv")
        self.DRUG_DATA_PATH: str = os.getenv("DRUG_DATA_PATH", "./data/emergency_contacts.csv")

        # ─── Emergency Configuration ──────────────────────────────────────────────
        self.EMERGENCY_HOTLINE: str = os.getenv("EMERGENCY_HOTLINE", "108")
        self.AMBULANCE_SERVICE: str = os.getenv("AMBULANCE_SERVICE", "102")
        self.HEALTH_HELPLINE: str = os.getenv("HEALTH_HELPLINE", "104")

        # ─── Session & Security ───────────────────────────────────────────────────
        self.SESSION_TIMEOUT_MINUTES: int = int(os.getenv("SESSION_TIMEOUT_MINUTES", "30"))
        self.MAX_CONVERSATION_TURNS: int = int(os.getenv("MAX_CONVERSATION_TURNS", "50"))
        self.RATE_LIMIT_REQUESTS: int = int(os.getenv("RATE_LIMIT_REQUESTS", "60"))

        # ─── Monitoring ───────────────────────────────────────────────────────────
        self.ENABLE_ANALYTICS: bool = os.getenv("ENABLE_ANALYTICS", "true").lower() == "true"
        self.AUDIT_LOG_PATH: str = os.getenv("AUDIT_LOG_PATH", "./logs/audit.log")

        # ─── Paths ────────────────────────────────────────────────────────────────
        self.BASE_DIR: Path = Path(__file__).parent.parent
        self.LOGS_DIR: Path = self.BASE_DIR / "logs"
        self.DATA_DIR: Path = self.BASE_DIR / "data"

    def validate(self) -> list[str]:
        """Validate critical settings. Returns list of warnings."""
        warnings = []
        if not self.GOOGLE_API_KEY and not self.OPENAI_API_KEY and not self.GROQ_API_KEY:
            warnings.append("No LLM API key configured. Set GOOGLE_API_KEY, OPENAI_API_KEY, or GROQ_API_KEY.")
        if self.SECRET_KEY == "change-me-in-production-32chars!" and self.APP_ENV == "production":
            warnings.append("SECRET_KEY must be changed for production deployment.")
        return warnings


# Singleton instance
settings = Settings()
