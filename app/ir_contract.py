from __future__ import annotations

from typing import Final

IR_LANGUAGES: Final = ("tr", "en", "es")
IR_PERSONAS: Final = (
    "assistant",
    "teacher",
    "researcher",
    "coach",
    "mentor",
    "developer",
    "expert",
)
IR_OUTPUT_FORMATS: Final = ("markdown", "json", "yaml", "table", "text")
IR_LENGTH_HINTS: Final = ("short", "medium", "long")

IR_INTENTS: Final = (
    "teaching",
    "explanation",
    "summary",
    "compare",
    "creative",
    "variants",
    "proposal",
    "review",
    "preparation",
    "troubleshooting",
    "recency",
    "risk",
    "code",
    "debug",
    "ambiguous",
    "capability_mismatch",
    "decompose",
    "summarize",
)
IR_STEP_TYPES: Final = ("task", "teach", "research", "compare", "plan")
IR_CONSTRAINT_PRIORITIES: Final = (10, 20, 30, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100)
IR_RISK_LEVELS: Final = ("low", "medium", "high")
IR_DATA_SENSITIVITY_LEVELS: Final = ("public", "internal", "confidential", "restricted")
IR_EXECUTION_MODES: Final = ("advice_only", "human_approval_required", "auto_ok")
