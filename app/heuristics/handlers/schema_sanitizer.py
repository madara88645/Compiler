import re
from app.heuristics.handlers.base import BaseHandler
from app.models import IR
from app.models_v2 import IRv2


class SchemaSanitizerHandler(BaseHandler):
    """Sanitizes JSON schemas to ensure specific fields (like phone numbers) are strings, not integers."""

    def handle(self, ir_v2: IRv2, ir_v1: IR) -> None:
        # Fields that should ALWAYS be strings, even if an LLM/structure engine guesses integer
        string_fields = [
            "phone",
            "phone_number",
            "zip",
            "zip_code",
            "postal_code",
            "ssn",
            "id_number",
        ]

        for constraint in ir_v2.constraints:
            if "Strictly follow this JSON Schema:" in constraint.text:
                text = constraint.text

                # A simple regex to find the property definitions and force type to "string"
                for field in string_fields:
                    # Look for: "phone_number": { \n "type": "integer"
                    # and replace with "string"
                    pattern = r'("' + field + r'"\s*:\s*\{\s*"type"\s*:\s*")(?:integer|number)(")'
                    text = re.sub(pattern, r"\g<1>string\g<2>", text, flags=re.IGNORECASE)

                constraint.text = text
