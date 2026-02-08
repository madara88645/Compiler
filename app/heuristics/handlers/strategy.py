"""
Strategy Handler: Advanced Prompting Pattern Injection

Injects sophisticated prompting strategies based on task analysis:
- Chain-of-Thought (CoT) for complex tasks
- Few-Shot suggestions for classification/transformation
- Persona deepening for role-based prompts
"""
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class StrategyResult:
    """Result of strategy injection."""

    system_prompt_additions: List[str]
    constraint_additions: List[str]
    few_shot_suggestion: Optional[str]
    persona_traits: List[str]
    strategy_notes: List[str]


class StrategyHandler:
    """
    Injects advanced prompting patterns based on prompt characteristics.

    Strategies:
    1. CoT: Force step-by-step for high-complexity tasks
    2. Few-Shot: Suggest examples for classification/transformation
    3. Persona: Deepen role definitions with psychological traits
    """

    # Persona trait mapping
    PERSONA_TRAITS: Dict[str, List[str]] = {
        "teacher": [
            "Patient and encouraging",
            "Uses the Socratic method - ask guiding questions",
            "Breaks down complex topics into digestible chunks",
            "Celebrates small wins and progress",
        ],
        "auditor": [
            "Skeptical and detail-oriented",
            "Questions assumptions rigorously",
            "Follows strict verification procedures",
            "Documents findings meticulously",
        ],
        "coach": [
            "Motivational and supportive",
            "Focuses on actionable improvement",
            "Provides constructive feedback",
            "Sets clear milestones",
        ],
        "analyst": [
            "Data-driven and objective",
            "Identifies patterns and trends",
            "Quantifies findings when possible",
            "Separates facts from opinions",
        ],
        "mentor": [
            "Shares experience and wisdom",
            "Provides context from real-world scenarios",
            "Encourages independent thinking",
            "Offers long-term perspective",
        ],
        "expert": [
            "Deep domain knowledge",
            "Cites authoritative sources",
            "Acknowledges edge cases and limitations",
            "Uses precise technical terminology",
        ],
    }

    # Keywords indicating classification tasks
    CLASSIFICATION_KEYWORDS = [
        "classify",
        "categorize",
        "label",
        "sort",
        "identify",
        "detect",
        "recognize",
        "tag",
        "group",
        "cluster",
        "determine type",
        "which type",
    ]

    # Keywords indicating transformation tasks
    TRANSFORMATION_KEYWORDS = [
        "convert",
        "transform",
        "translate",
        "rewrite",
        "rephrase",
        "format",
        "restructure",
        "summarize",
        "expand",
        "simplify",
    ]

    def process(
        self,
        prompt_text: str,
        complexity_score: float = 0.0,
        task_type: Optional[str] = None,
        persona: Optional[str] = None,
        output_format: Optional[str] = None,
    ) -> StrategyResult:
        """
        Analyze the prompt and inject appropriate strategies.

        Args:
            prompt_text: The raw prompt text
            complexity_score: 0-100 score (from existing heuristics)
            task_type: Optional explicit task type (classification, transformation, etc.)
            persona: Optional persona identifier (teacher, auditor, etc.)
            output_format: Optional output format (JSON, XML, CSV)

        Returns:
            StrategyResult with additions and suggestions
        """
        system_additions = []
        constraint_additions = []
        strategy_notes = []
        few_shot = None
        traits = []

        # 1. Complexity-Based CoT
        cot_result = self._inject_cot(complexity_score, prompt_text)
        if cot_result:
            system_additions.append(cot_result)
            strategy_notes.append(f"CoT injected (complexity: {complexity_score:.0f})")

        # 2. Few-Shot Generator
        detected_task = task_type or self._detect_task_type(prompt_text)
        if detected_task in ("classification", "transformation"):
            few_shot = self._generate_few_shot_suggestion(detected_task, output_format)
            strategy_notes.append(f"Few-shot suggested for {detected_task}")

        # 3. Persona Deepener
        detected_persona = persona or self._detect_persona(prompt_text)
        if detected_persona:
            traits = self._get_persona_traits(detected_persona)
            if traits:
                persona_block = self._format_persona_block(detected_persona, traits)
                system_additions.append(persona_block)
                strategy_notes.append(f"Persona deepened: {detected_persona}")

        return StrategyResult(
            system_prompt_additions=system_additions,
            constraint_additions=constraint_additions,
            few_shot_suggestion=few_shot,
            persona_traits=traits,
            strategy_notes=strategy_notes,
        )

    # --------------------------------------------------------------------------
    # CHAIN-OF-THOUGHT INJECTION
    # --------------------------------------------------------------------------

    def _inject_cot(self, complexity: float, text: str) -> Optional[str]:
        """
        Inject CoT instruction if complexity warrants it.

        Threshold: complexity > 70
        """
        if complexity <= 70:
            return None

        # Check if CoT is already present
        cot_indicators = [
            "step by step",
            "chain of thought",
            "think through",
            "reasoning",
            "break down",
            "walk through",
        ]
        text_lower = text.lower()
        if any(indicator in text_lower for indicator in cot_indicators):
            return None  # Already has CoT

        # Select appropriate CoT style based on complexity level
        if complexity > 90:
            return (
                "## Thinking Process\n"
                "Before responding, you MUST:\n"
                "1. Identify the core problem\n"
                "2. List all relevant constraints\n"
                "3. Consider edge cases\n"
                "4. Outline your approach step by step\n"
                "5. Validate your reasoning before finalizing\n"
            )
        else:  # 70 < complexity <= 90
            return (
                "## Approach\n"
                "Think through this step by step. "
                "Break down the problem and address each component systematically.\n"
            )

    # --------------------------------------------------------------------------
    # FEW-SHOT GENERATOR
    # --------------------------------------------------------------------------

    def _detect_task_type(self, text: str) -> Optional[str]:
        """Heuristically detect if task is classification or transformation."""
        text_lower = text.lower()

        for kw in self.CLASSIFICATION_KEYWORDS:
            if kw in text_lower:
                return "classification"

        for kw in self.TRANSFORMATION_KEYWORDS:
            if kw in text_lower:
                return "transformation"

        return None

    def _generate_few_shot_suggestion(
        self, task_type: str, output_format: Optional[str] = None
    ) -> str:
        """
        Generate a few-shot suggestion block.

        For classification: Input -> Label
        For transformation: Input -> Transformed Output
        """
        format_hint = ""
        if output_format:
            format_lower = output_format.lower()
            if "json" in format_lower:
                format_hint = "Output should be in JSON format."
            elif "xml" in format_lower:
                format_hint = "Output should be in XML format."
            elif "csv" in format_lower:
                format_hint = "Output should be in CSV format."

        if task_type == "classification":
            suggestion = (
                "## Few-Shot Examples\n"
                "Provide 3 examples before processing:\n\n"
                "**Example 1:**\n"
                "- Input: [sample input]\n"
                "- Label: [category A]\n\n"
                "**Example 2:**\n"
                "- Input: [sample input]\n"
                "- Label: [category B]\n\n"
                "**Example 3:**\n"
                "- Input: [sample input]\n"
                "- Label: [category A]\n"
            )
        else:  # transformation
            suggestion = (
                "## Few-Shot Examples\n"
                "Provide 3 examples of the transformation:\n\n"
                "**Example 1:**\n"
                "- Input: [original format]\n"
                "- Output: [transformed format]\n\n"
                "**Example 2:**\n"
                "- Input: [original format]\n"
                "- Output: [transformed format]\n\n"
                "**Example 3:**\n"
                "- Input: [original format]\n"
                "- Output: [transformed format]\n"
            )

        if format_hint:
            suggestion += f"\n{format_hint}\n"

        return suggestion

    # --------------------------------------------------------------------------
    # PERSONA DEEPENER
    # --------------------------------------------------------------------------

    def _detect_persona(self, text: str) -> Optional[str]:
        """Detect persona from text using keyword matching."""
        text_lower = text.lower()

        persona_keywords = {
            "teacher": ["teacher", "tutor", "educator", "instructor", "teach me"],
            "auditor": ["auditor", "reviewer", "checker", "inspector", "audit"],
            "coach": ["coach", "trainer", "guide me", "help me improve"],
            "analyst": ["analyst", "analyze", "data scientist", "researcher"],
            "mentor": ["mentor", "advisor", "counsel", "guide"],
            "expert": ["expert", "specialist", "professional", "authority"],
        }

        for persona, keywords in persona_keywords.items():
            for kw in keywords:
                if kw in text_lower:
                    return persona

        return None

    def _get_persona_traits(self, persona: str) -> List[str]:
        """Get psychological traits for a persona."""
        return self.PERSONA_TRAITS.get(persona.lower(), [])

    def _format_persona_block(self, persona: str, traits: List[str]) -> str:
        """Format persona traits as a system prompt block."""
        traits_formatted = "\n".join(f"- {trait}" for trait in traits)
        return (
            f"## Persona: {persona.title()}\n"
            f"Embody these characteristics:\n"
            f"{traits_formatted}\n"
        )

    # --------------------------------------------------------------------------
    # UTILITY: APPLY STRATEGIES TO PROMPT
    # --------------------------------------------------------------------------

    def apply_to_prompt(self, system_prompt: str, result: StrategyResult) -> str:
        """
        Apply strategy results to an existing system prompt.

        Appends additions in a clean format.
        """
        additions = result.system_prompt_additions[:]

        # Add few-shot suggestion as a comment/section
        if result.few_shot_suggestion:
            additions.append(result.few_shot_suggestion)

        if not additions:
            return system_prompt

        separator = "\n\n---\n\n"
        return system_prompt.strip() + separator + separator.join(additions)
