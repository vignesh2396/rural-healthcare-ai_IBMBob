"""
Logging & Audit Trail Utilities
=================================
Purpose: Structured logging with audit trail for all agent actions and user interactions.
         Supports HIPAA-compatible audit logging with PII masking.
Dependencies: Python standard library (logging, json), settings
"""

import logging
import logging.handlers
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from config.settings import settings

# ─── Create log directory ───────────────────────────────────────────────────
os.makedirs(settings.LOGS_DIR, exist_ok=True)


class PIIMaskingFilter(logging.Filter):
    """
    Logging filter that masks PII (phone numbers, Aadhaar-like IDs, emails)
    before writing to log files.
    """
    PII_PATTERNS = [
        (re.compile(r'\b\d{12}\b'), '****-****-****'),          # Aadhaar
        (re.compile(r'\b\d{10}\b'), '**********'),              # Phone
        (re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'), '***@***.***'),  # Email
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            for pattern, replacement in self.PII_PATTERNS:
                record.msg = pattern.sub(replacement, record.msg)
        return True


class JSONFormatter(logging.Formatter):
    """Formats log records as structured JSON for log aggregation tools."""

    def format(self, record: logging.LogRecord) -> str:
        record.message = record.getMessage()
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.message,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "extra"):
            log_entry.update(record.extra)
        return json.dumps(log_entry, ensure_ascii=False)


def setup_logger(name: str) -> logging.Logger:
    """
    Creates and configures a logger with:
    - Console handler (human-readable)
    - Rotating file handler (JSON structured)
    - PII masking filter
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # already configured

    logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
    pii_filter = PIIMaskingFilter()

    # ── Console handler ──
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))
    console_handler.addFilter(pii_filter)

    # ── File handler (rotating, 10MB, 5 backups) ──
    log_file = settings.LOGS_DIR / "app.log"
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(JSONFormatter())
    file_handler.addFilter(pii_filter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    return logger


class AuditLogger:
    """
    HIPAA-compatible audit trail logger.
    Records every agent action, tool call, and user interaction with:
    - Session ID, timestamp, action type, agent name, outcome
    """

    def __init__(self):
        self._logger = logging.getLogger("audit")
        self._logger.setLevel(logging.INFO)
        audit_file = settings.LOGS_DIR / "audit.log"
        handler = logging.handlers.RotatingFileHandler(
            audit_file, maxBytes=50 * 1024 * 1024, backupCount=10, encoding="utf-8"
        )
        handler.setFormatter(JSONFormatter())
        handler.addFilter(PIIMaskingFilter())
        if not self._logger.handlers:
            self._logger.addHandler(handler)

    def log(
        self,
        session_id: str,
        action_type: str,        # agent_call | tool_call | rag_query | escalation | user_input
        agent_name: str,
        action: str,
        outcome: str,            # success | failure | escalated | human_review
        metadata: Optional[dict] = None,
        duration_ms: Optional[float] = None,
    ) -> None:
        """Write a single audit entry."""
        entry = {
            "audit_id": str(uuid.uuid4()),
            "session_id": session_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action_type": action_type,
            "agent_name": agent_name,
            "action": action,
            "outcome": outcome,
            "duration_ms": duration_ms,
            "metadata": metadata or {},
        }
        self._logger.info(json.dumps(entry, ensure_ascii=False))


# ─── Global singletons ───────────────────────────────────────────────────────
app_logger = setup_logger("healthcare_ai")
audit_logger = AuditLogger()
