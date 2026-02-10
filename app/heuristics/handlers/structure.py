import re
from typing import Dict, List, Tuple


from .base import BaseHandler
from app.models import IR
from app.models_v2 import IRv2, ConstraintV2


class StructureHandler(BaseHandler):
    """
    Deterministic structure engine that formats raw prompts into DeepSpec standard.
    Also acts as a heuristic handler to inject strict output format constraints.
    """

    def handle(self, ir_v2: IRv2, ir_v1: IR) -> None:
        """
        Detect output format keywords and inject strict constraints.
        """
        text = ir_v2.tasks[0] if ir_v2.tasks else ""
        # Also check original text if available
        if ir_v2.metadata and "original_text" in ir_v2.metadata:
            text = ir_v2.metadata["original_text"]

        lower_text = text.lower()

        # Keywords to detect
        formats = {
            "json": "JSON",
            "csv": "CSV",
            "xml": "XML",
            "markdown table": "Markdown table",
            "list": "List",
        }

        detected = []
        for key, label in formats.items():
            if key in lower_text:
                detected.append(label)

        # If multiple detected, pick the first one (simple heuristic)
        # or maybe we want to enforce all? Let's just pick the first specific one found.
        # Priority: JSON > XML > CSV > Table > List

        target_format = None
        if "json" in lower_text:
            target_format = "JSON"
        elif "xml" in lower_text:
            target_format = "XML"
        elif "csv" in lower_text:
            target_format = "CSV"
        elif "markdown table" in lower_text:
            target_format = "Markdown table"
        elif "list" in lower_text:
            target_format = "List"

        if target_format:
            constraint_text = f"Output strict {target_format}. Do not output conversational text."
            ir_v2.constraints.append(
                ConstraintV2(
                    id=f"structure_strict_{target_format.lower().replace(' ', '_')}",
                    text=constraint_text,
                    origin="structure_handler",
                    priority=85,
                    rationale=f"User requested {target_format} format.",
                )
            )

    def process(self, text: str) -> str:
        """
        Main entry point to structure the text.
        """
        # 1. Clean and Normalize
        text = text.strip()

        # 2. Extract Variables
        text, variables = self._inject_variables(text)

        # 3. Segment Sections
        sections = self._segment_sections(text)

        # 4. Detect Output Format
        output_format_block = self._detect_output_format(text)

        # 5. Assemble DeepSpec
        return self._format_deepspec(sections, variables, output_format_block)

    def _inject_variables(self, text: str) -> Tuple[str, List[str]]:
        """
        Identify capitalized placeholders (e.g., USER_NAME) and convert to {{variable}}.
        Returns modified text and list of found variables.
        """
        variables = set()

        # Pattern: All caps words, length > 2, possibly with underscores, not starting with numbers
        # Excluding common keywords like JSON, XML, CSV, HTTP, API
        ignored = {"JSON", "XML", "CSV", "HTTP", "HTTPS", "API", "URL", "ID", "HTML", "CSS", "SQL"}

        def replace_var(match):
            word = match.group(0)
            if word in ignored:
                return word
            variables.add(word)
            return f"{{{{{word}}}}}"

        # Look for standalone uppercase words, avoiding ones inside existing brackets
        pattern = r"\b[A-Z][A-Z0-9_]{2,}\b"

        # Simple approach: Identify potential vars first
        matches = re.findall(pattern, text)
        for m in matches:
            if m not in ignored:
                variables.add(m)
                # Naive replacement - careful not to replace inside {{...}} if already there
                # But for this task, we assume raw text input.
                # To be detailed: we should only replace if not already surrounded.
                # Regex lookbehind/ahead for {{ is tricky in one pass.

        # Let's do a uniform replacement for identified variables
        for var in variables:
            # Replace 'VAR' but not '{{VAR}}'
            # Regex: (citation needed) - simple replace for now is safer for raw input
            text = re.sub(rf"(?<!{{{{)\b{var}\b(?!}}}})", f"{{{{{var}}}}}", text)

        return text, sorted(list(variables))

    def _segment_sections(self, text: str) -> Dict[str, str]:
        """
        Heuristic segmentation into Role, Context, Task, Constraints.
        """
        sections = {"Role": "", "Context": "", "Task": "", "Constraints": ""}

        # Split by sentence boundaries (rough heuristic: period followed by space or newline)
        # We replace newlines with a special marker or just treat them as separators
        # Let's split by regex that handles newlines OR sentence endings
        # Normalize newlines and split by sentence
        clean_text = text.replace("\r\n", "\n").replace("\n", " ")
        # Insert break markers
        marked = re.sub(r"([.!?])\s+", r"\1|||", clean_text)
        parts = marked.split("|||")

        current_bucket = "Task"  # Default bucket

        for part in parts:
            part = part.strip()
            if not part:
                continue

            lower_part = part.lower()

            # Heuristics to switch buckets
            # We prioritize explicit headers first
            if any(
                x in lower_part for x in ["context:", "background:", "situation:", "context is"]
            ):
                current_bucket = "Context"
            elif any(
                x in lower_part
                for x in [
                    "task:",
                    "goal:",
                    "objective:",
                    "do this:",
                    "please",
                    "write a",
                    "create a",
                    "your task",
                    "task is",
                ]
            ):
                current_bucket = "Task"
            elif any(
                x in lower_part
                for x in ["constraint", "avoid", "do not", "limit:", "rule", "don't"]
            ):
                current_bucket = "Constraints"
            # Specific role markers check - do this LAST or restrict it
            elif any(x in lower_part for x in ["act as", "your role", "role:"]):
                current_bucket = "Role"
            elif "you are" in lower_part:
                # Only switch to Role if we aren't already in Context/Task strings that might contain "you are"
                # For now, let's treat "you are" as Role only if it's at the start or explicit
                if current_bucket not in ("Context", "Task"):
                    current_bucket = "Role"
            elif any(
                x in lower_part
                for x in ["constraint", "avoid", "do not", "limit:", "rule", "don't"]
            ):
                current_bucket = "Constraints"

            # append to bucket
            sections[current_bucket] += part + "\n"

        return {k: v.strip() for k, v in sections.items()}

    def _detect_output_format(self, text: str) -> str:
        """
        Detects requested format and returns XML schema block.
        """
        lower_text = text.lower()

        if "json" in lower_text:
            return """<output_format>
  <style>JSON</style>
  <schema>
    {
      "key": "value"
    }
  </schema>
</output_format>"""

        if "xml" in lower_text:
            return """<output_format>
  <style>XML</style>
  <schema>
    <root>
      <element>value</element>
    </root>
  </schema>
</output_format>"""

        if "csv" in lower_text:
            return """<output_format>
  <style>CSV</style>
  <schema>
    col1,col2,col3
    val1,val2,val3
  </schema>
</output_format>"""

        return ""

    def infer_schema(self, text: str) -> str:
        """
        Infer a JSON Schema from natural language instructions.
        Examples:
        - "Extract name, email, and age" -> {"type": "object", "properties": {"name": {"type": "string"}, ...}}
        - "Fields: title, body, tags (array)" -> ...
        """
        text_lower = text.lower()

        # 1. Detect Intent
        # We look for the keyword, then capture everything until a sentence end or double newline
        intent_pattern = (
            r"\b(extract|fields|columns|properties|keys|capture)\b[:\s]+(.*?)(?:$|[.!?\n])"
        )
        match = re.search(intent_pattern, text_lower, re.DOTALL)

        if not match:
            return ""

        field_string = match.group(2)

        # 2. Split and Clean Fields
        # Split by comma or 'and'
        raw_fields = re.split(r"[,;]|\band\b", field_string)
        properties = {}

        stopwords = ["from", "in", "of", "for", "the", "with", "where"]

        for field in raw_fields:
            field = field.strip()
            if not field:
                continue

            # Truncate at stopwords from the END (e.g., "age from user")
            # We split by space, if we find a stopword, we take everything before it
            words = field.split()
            clean_words = []
            for w in words:
                if w in stopwords:
                    break
                clean_words.append(w)

            if not clean_words:
                continue

            # Reassemble
            base_name = " ".join(clean_words)

            # Remove type hints in parens: "age (int)" -> "age"
            clean_name = re.sub(r"\s*\(.*?\)", "", base_name).strip()
            # Convert to snake_case only if it has spaces
            clean_name = clean_name.replace(" ", "_")

            # Sanity check: Field names shouldn't be massive sentences
            if len(clean_name) > 30 or " " in clean_name:
                continue

            # Type inference (check original field text for hints like "(array)")
            prop_type = self._map_type(field)

            properties[clean_name] = {"type": prop_type}
            if prop_type == "array":
                properties[clean_name]["items"] = {"type": "string"}

        if not properties:
            return ""

        schema = {"type": "object", "properties": properties, "required": list(properties.keys())}

        import json

        return json.dumps(schema, indent=2)

    def _map_type(self, field_name: str) -> str:
        """Heuristic type mapping based on field name."""
        s = field_name.lower()
        if any(
            x in s for x in ["age", "count", "number", "quantity", "year", "limit", "id", "score"]
        ):
            return "integer"
        if any(x in s for x in ["is_", "has_", "active", "enabled", "check", "flag"]):
            return "boolean"
        if any(x in s for x in ["list", "array", "tags", "categories", "items", "friends"]):
            return "array"
        if any(x in s for x in ["email", "date", "time", "url", "link", "phone"]):
            return "string"
        return "string"

    def _format_deepspec(
        self, sections: Dict[str, str], variables: List[str], output_xml: str
    ) -> str:
        """
        Assembles the final markdown.
        """
        out = []

        # Variables header
        if variables:
            out.append("### Variables")
            for var in variables:
                out.append(f"- {var}")
            out.append("")

        # Standard Sections
        # We enforce order: Role -> Context -> Task -> Constraints

        if sections["Role"]:
            out.append("### Role")
            out.append(sections["Role"])
            out.append("")

        if sections["Context"]:
            out.append("### Context")
            out.append(sections["Context"])
            out.append("")

        if sections["Task"]:
            out.append("### Task")
            out.append(sections["Task"])
            out.append("")

        if sections["Constraints"]:
            out.append("### Constraints")
            out.append(sections["Constraints"])
            out.append("")

        # Output Format
        if output_xml:
            out.append(output_xml)

        return "\n".join(out).strip()
