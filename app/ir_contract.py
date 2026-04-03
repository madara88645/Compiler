from __future__ import annotations

IR_LANGUAGES = ["tr", "en", "es"]
IR_PERSONAS = ["assistant", "teacher", "researcher", "coach", "mentor", "developer"]
IR_OUTPUT_FORMATS = ["markdown", "json", "yaml", "table", "text"]
IR_LENGTH_HINTS = ["short", "medium", "long"]

IR_INTENTS = ["teaching", "summary", "compare", "variants", "recency", "risk", "code", "ambiguous"]
IR_STEP_TYPES = ["task", "teach", "research", "compare", "plan"]
IR_CONSTRAINT_PRIORITIES = [10, 20, 30, 40, 50, 60, 65, 70, 75, 80, 90]
IR_RISK_LEVELS = ["low", "medium", "high"]
IR_DATA_SENSITIVITY_LEVELS = ["public", "internal", "confidential", "restricted"]
IR_EXECUTION_MODES = ["advice_only", "human_approval_required", "auto_ok"]
