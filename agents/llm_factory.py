"""
LLM Factory — Provider-Agnostic Language Model Initialization
==============================================================
Purpose: Returns appropriate LangChain-compatible LLM based on configured provider.
         Supports Google Gemini (preferred), OpenAI, and Groq as fallback.
Dependencies: langchain, google-generativeai, openai, groq
"""

from typing import Any
from config.settings import settings
from utils.logger import app_logger


def get_llm(temperature: float = None, max_tokens: int = None) -> Any:
    """
    Factory function returning the configured LLM instance.
    Priority: Google Gemini → OpenAI → Groq → raises ValueError

    Args:
        temperature: Override default temperature
        max_tokens: Override default max_tokens

    Returns:
        LangChain-compatible LLM instance

    Raises:
        ValueError: If no valid API key is configured
    """
    temp = temperature if temperature is not None else settings.LLM_TEMPERATURE
    tokens = max_tokens if max_tokens is not None else settings.LLM_MAX_TOKENS

    # ── Google Gemini (preferred) ──────────────────────────────────────────
    if settings.LLM_PROVIDER == "google" and settings.GOOGLE_API_KEY and settings.GOOGLE_API_KEY.startswith("AIza"):
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            llm = ChatGoogleGenerativeAI(
                model=settings.LLM_MODEL,
                google_api_key=settings.GOOGLE_API_KEY,
                temperature=temp,
                max_output_tokens=tokens,
                convert_system_message_to_human=True,
            )
            app_logger.info(f"LLM: Google Gemini [{settings.LLM_MODEL}]")
            return llm
        except ImportError:
            app_logger.warning("langchain_google_genai not installed. Trying OpenAI.")
        except Exception as e:
            app_logger.warning(f"Gemini init failed: {e}. Trying fallback.")

    # ── OpenAI ────────────────────────────────────────────────────────────
    if settings.OPENAI_API_KEY:
        try:
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(
                model="gpt-4o-mini",
                openai_api_key=settings.OPENAI_API_KEY,
                temperature=temp,
                max_tokens=tokens,
            )
            app_logger.info("LLM: OpenAI GPT-4o-mini")
            return llm
        except ImportError:
            app_logger.warning("langchain_openai not installed. Trying Groq.")

    # ── Groq (free-tier fallback) ──────────────────────────────────────────
    if settings.GROQ_API_KEY:
        try:
            from langchain_groq import ChatGroq
            llm = ChatGroq(
                model_name=settings.GROQ_MODEL,
                groq_api_key=settings.GROQ_API_KEY,
                temperature=temp,
                max_tokens=tokens,
            )
            app_logger.info(f"LLM: Groq [{settings.GROQ_MODEL}]")
            return llm
        except ImportError:
            app_logger.warning("langchain_groq not installed.")

    raise ValueError(
        "No LLM API key configured. Set GOOGLE_API_KEY, OPENAI_API_KEY, or GROQ_API_KEY in your .env file."
    )
