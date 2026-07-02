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
IR_STEP_MODES: Final = ("explore", "decide", "execute", "verify")
IR_SCHEDULING_REASONS: Final = (
    "diagnostic_request",  # explore: problem cue + diagnostic ask/intent
    "convergence_after_exploration",  # decide pseudo-step after an explore step
    "scoped_execution",  # execute backfill once another mode engaged
    "destructive_operation",  # verify via policy_reasons
    "high_risk_change",  # verify via high risk + approval + concrete change
)
IR_CONSTRAINT_PRIORITIES: Final = (10, 20, 30, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100)
IR_RISK_LEVELS: Final = ("low", "medium", "high")
IR_DATA_SENSITIVITY_LEVELS: Final = ("public", "internal", "confidential", "restricted")
IR_EXECUTION_MODES: Final = ("advice_only", "human_approval_required", "auto_ok")
