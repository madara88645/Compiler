import re
from app.heuristics.handlers.base import BaseHandler
from app.models import IR
from app.models_v2 import IRv2


# Fields that should ALWAYS be strings, even if an LLM/structure engine guesses integer
_STRING_FIELDS = [
    "phone",
    "phone_number",
    "zip",
    "zip_code",
    "postal_code",
    "ssn",
    "id_number",
]

# Bolt Optimization: Pre-compile an alternated regex to quickly check if *any* target field exists
_FAST_CHECK_PATTERN = re.compile(r'"(?:' + "|".join(_STRING_FIELDS) + r')"', re.IGNORECASE)

# Bolt Optimization: Pre-compile the substitution regexes at the module level
_FIELD_REGEXES = [
    re.compile(r'("' + field + r'"\s*:\s*\{\s*"type"\s*:\s*")(?:integer|number)(")', re.IGNORECASE)
    for field in _STRING_FIELDS
]


class SchemaSanitizerHandler(BaseHandler):
    """Sanitizes JSON schemas to ensure specific fields (like phone numbers) are strings, not integers."""

    def handle(self, ir_v2: IRv2, ir_v1: IR) -> None:
        for constraint in ir_v2.constraints:
            if "Strictly follow this JSON Schema:" in constraint.text:
                text = constraint.text

                # Bolt Optimization: Fast path check skips expensive regex replacement loop if no keywords match
                if _FAST_CHECK_PATTERN.search(text):
                    # A simple regex to find the property definitions and force type to "string"
                    for pattern in _FIELD_REGEXES:
                        # Look for: "phone_number": { \n "type": "integer"
                        # and replace with "string"
                        text = pattern.sub(r"\g<1>string\g<2>", text)

                    constraint.text = text
