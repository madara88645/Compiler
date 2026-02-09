"""
Domain Expert Handler - Subject Matter Expertise Engine

Provides domain-specific heuristics and best-practice enforcement:
- Coding: Language detection, error handling, testing, type hints
- Creative Writing: Show-don't-tell, story structure suggestions
- Business: BLUF format, KPI enforcement
"""

from __future__ import annotations
import re
import ast
import textwrap
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from .base import BaseHandler
from app.models import IR
from app.models_v2 import IRv2, ConstraintV2, DiagnosticItem


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================


@dataclass
class DomainSuggestion:
    """A domain-specific suggestion or constraint."""

    text: str
    category: str
    priority: int = 60
    rationale: Optional[str] = None


@dataclass
class DomainAnalysis:
    """Result of domain-specific analysis."""

    detected_domain: str
    sub_domain: Optional[str] = None  # e.g., "python" for coding
    suggestions: List[DomainSuggestion] = field(default_factory=list)
    diagnostics: List[DiagnosticItem] = field(default_factory=list)
    detected_patterns: Dict[str, List[str]] = field(default_factory=dict)


# ==============================================================================
# DOMAIN RULES DICTIONARY
# ==============================================================================

DOMAIN_RULES: Dict[str, Dict] = {
    # -------------------------------------------------------------------------
    # CODING / SOFTWARE ENGINEERING
    # -------------------------------------------------------------------------
    "coding": {
        "keywords": [
            "code",
            "function",
            "class",
            "method",
            "api",
            "endpoint",
            "script",
            "program",
            "algorithm",
            "implement",
            "develop",
            "debug",
            "refactor",
            "optimize",
            "compile",
            "runtime",
            "variable",
            "loop",
            "conditional",
            "exception",
            "error",
            "test",
            "unit test",
            "integration",
            "deploy",
            "git",
        ],
        "languages": {
            "python": {
                "indicators": [
                    "python",
                    "py",
                    "django",
                    "flask",
                    "fastapi",
                    "pandas",
                    "numpy",
                    "pip",
                    "pytest",
                    "def ",
                    "import ",
                ],
                "suggestions": [
                    DomainSuggestion(
                        "Use type hints for function signatures",
                        "best_practice",
                        65,
                        "PEP 484 compliance",
                    ),
                    DomainSuggestion("Follow PEP 8 style guidelines", "style", 50),
                    DomainSuggestion("Use docstrings for documentation", "documentation", 55),
                    DomainSuggestion(
                        "Consider using dataclasses or Pydantic models", "architecture", 45
                    ),
                ],
            },
            "javascript": {
                "indicators": [
                    "javascript",
                    "js",
                    "node",
                    "npm",
                    "react",
                    "vue",
                    "angular",
                    "typescript",
                    "ts",
                    "const ",
                    "let ",
                    "=>",
                ],
                "suggestions": [
                    DomainSuggestion("Use TypeScript for type safety", "best_practice", 60),
                    DomainSuggestion("Follow ESLint rules", "style", 50),
                    DomainSuggestion("Use async/await for asynchronous operations", "pattern", 55),
                    DomainSuggestion("Consider using JSDoc comments", "documentation", 45),
                ],
            },
            "rust": {
                "indicators": [
                    "rust",
                    "cargo",
                    "crate",
                    "fn ",
                    "let mut",
                    "impl ",
                    "trait ",
                    "struct ",
                ],
                "suggestions": [
                    DomainSuggestion(
                        "Handle Result and Option types properly", "error_handling", 70
                    ),
                    DomainSuggestion("Use lifetimes explicitly where needed", "memory_safety", 65),
                    DomainSuggestion("Follow Rust API Guidelines", "style", 50),
                    DomainSuggestion("Consider using clippy for linting", "tooling", 45),
                ],
            },
            "go": {
                "indicators": [
                    "golang",
                    "go ",
                    "go mod",
                    "func ",
                    "package ",
                    "goroutine",
                    "channel",
                ],
                "suggestions": [
                    DomainSuggestion(
                        "Handle errors explicitly (no exceptions)", "error_handling", 70
                    ),
                    DomainSuggestion("Use gofmt for formatting", "style", 50),
                    DomainSuggestion("Follow Go Proverbs", "best_practice", 55),
                ],
            },
        },
        "universal_checks": {
            "error_handling": {
                "missing_patterns": [r"\b(try|catch|except|error|exception|handle)\b"],
                "suggestion": DomainSuggestion(
                    "🛡️ Include comprehensive error handling",
                    "error_handling",
                    75,
                    "Catch and handle potential errors gracefully",
                ),
            },
            "testing": {
                "missing_patterns": [r"\b(test|spec|assert|expect|mock|stub|fixture)\b"],
                "suggestion": DomainSuggestion(
                    "🧪 Include unit tests for the implementation",
                    "testing",
                    70,
                    "Ensure code correctness with automated tests",
                ),
            },
            "documentation": {
                "missing_patterns": [r"\b(document|docstring|comment|readme|jsdoc)\b"],
                "suggestion": DomainSuggestion(
                    "📝 Add documentation for public interfaces",
                    "documentation",
                    55,
                    "Help future developers understand the code",
                ),
            },
            "security": {
                "risk_patterns": [r"\b(password|secret|key|token|credential|auth)\b"],
                "suggestion": DomainSuggestion(
                    "🔐 Review security implications (secrets, auth)",
                    "security",
                    80,
                    "Ensure sensitive data is handled securely",
                ),
            },
        },
    },
    # -------------------------------------------------------------------------
    # CREATIVE WRITING
    # -------------------------------------------------------------------------
    "creative_writing": {
        "keywords": [
            "story",
            "novel",
            "chapter",
            "character",
            "plot",
            "scene",
            "dialogue",
            "narrative",
            "fiction",
            "poem",
            "poetry",
            "screenplay",
            "script",
            "prose",
            "creative",
            "write",
            "protagonist",
            "antagonist",
            "setting",
            "theme",
            "climax",
        ],
        "structures": {
            "heros_journey": {
                "indicators": ["hero", "journey", "adventure", "quest", "transformation", "mentor"],
                "stages": [
                    "ordinary world",
                    "call to adventure",
                    "refusal",
                    "mentor",
                    "threshold",
                    "tests",
                    "approach",
                    "ordeal",
                    "reward",
                    "return",
                ],
            },
            "three_act": {
                "indicators": [
                    "act",
                    "beginning",
                    "middle",
                    "end",
                    "setup",
                    "confrontation",
                    "resolution",
                ],
                "parts": ["setup", "confrontation", "resolution"],
            },
            "save_the_cat": {
                "indicators": ["beat", "save the cat", "opening image", "theme stated", "catalyst"],
            },
        },
        "style_checks": {
            "adverb_overuse": {
                "pattern": r"\b\w+ly\b",
                "threshold": 0.05,  # More than 5% adverbs is suspicious
                "suggestion": DomainSuggestion(
                    "✍️ Show, don't tell: Reduce adverb usage",
                    "style",
                    60,
                    "Replace adverbs with stronger verbs or descriptive scenes",
                ),
            },
            "passive_voice": {
                "pattern": r"\b(was|were|been|being|is|are|am)\s+\w+ed\b",
                "suggestion": DomainSuggestion(
                    "💪 Prefer active voice for stronger prose",
                    "style",
                    55,
                    "Active voice creates more engaging narrative",
                ),
            },
            "filter_words": {
                "words": [
                    "felt",
                    "saw",
                    "heard",
                    "noticed",
                    "realized",
                    "thought",
                    "knew",
                    "seemed",
                ],
                "suggestion": DomainSuggestion(
                    "🎭 Remove filter words for immersive POV",
                    "style",
                    50,
                    "Instead of 'She felt cold', write 'Cold seeped into her bones'",
                ),
            },
        },
        "universal_suggestions": [
            DomainSuggestion("Define clear character motivations", "character", 65),
            DomainSuggestion("Establish the stakes early", "plot", 70),
            DomainSuggestion("Use sensory details for immersion", "description", 55),
            DomainSuggestion("Vary sentence length for rhythm", "style", 45),
        ],
    },
    # -------------------------------------------------------------------------
    # BUSINESS & DATA STRATEGY
    # -------------------------------------------------------------------------
    "business": {
        "keywords": [
            "business",
            "strategy",
            "kpi",
            "metric",
            "roi",
            "revenue",
            "profit",
            "growth",
            "market",
            "customer",
            "stakeholder",
            "executive",
            "presentation",
            "report",
            "analysis",
            "data",
            "budget",
            "forecast",
            "quarterly",
            "annual",
            "dashboard",
            "okr",
            "goal",
            "objective",
            "target",
            "benchmark",
        ],
        "formats": {
            "bluf": {
                "description": "Bottom Line Up Front",
                "suggestion": DomainSuggestion(
                    "📋 Use BLUF format: Lead with the conclusion/recommendation",
                    "format",
                    75,
                    "Executives want the bottom line first, details after",
                ),
            },
            "pyramid": {
                "description": "Pyramid Principle (Minto)",
                "suggestion": DomainSuggestion(
                    "🔺 Structure arguments using the Pyramid Principle",
                    "format",
                    65,
                    "Start with answer, group supporting arguments, order logically",
                ),
            },
        },
        "required_elements": {
            "kpis": {
                "patterns": [r"\b(kpi|metric|measure|indicator|benchmark)\b"],
                "suggestion": DomainSuggestion(
                    "📊 Define specific, measurable KPIs",
                    "metrics",
                    80,
                    "What gets measured gets managed",
                ),
            },
            "timeline": {
                "patterns": [r"\b(deadline|timeline|milestone|quarter|q[1-4]|fy\d{2,4})\b"],
                "suggestion": DomainSuggestion(
                    "📅 Include specific timelines and milestones",
                    "planning",
                    70,
                ),
            },
            "stakeholders": {
                "patterns": [r"\b(stakeholder|owner|responsible|accountable|raci)\b"],
                "suggestion": DomainSuggestion(
                    "👥 Identify stakeholders and ownership",
                    "governance",
                    65,
                ),
            },
            "budget": {
                "patterns": [r"\b(budget|cost|expense|investment|roi|payback)\b"],
                "suggestion": DomainSuggestion(
                    "💰 Include budget/cost considerations",
                    "financial",
                    70,
                ),
            },
        },
        "frameworks": {
            "swot": ["strength", "weakness", "opportunity", "threat", "swot"],
            "porter": ["porter", "five forces", "competitive", "rivalry", "bargaining"],
            "pestle": [
                "pestle",
                "political",
                "economic",
                "social",
                "technological",
                "legal",
                "environmental",
            ],
        },
    },
    # -------------------------------------------------------------------------
    # EDUCATION / TEACHING
    # -------------------------------------------------------------------------
    "education": {
        "keywords": [
            "teach",
            "learn",
            "explain",
            "tutorial",
            "lesson",
            "course",
            "student",
            "beginner",
            "intermediate",
            "advanced",
            "concept",
            "example",
            "exercise",
            "practice",
            "understand",
            "comprehend",
        ],
        "levels": {
            "beginner": {
                "indicators": ["beginner", "basic", "intro", "introduction", "start", "new to"],
                "suggestions": [
                    DomainSuggestion(
                        "Use simple analogies and real-world examples", "pedagogy", 70
                    ),
                    DomainSuggestion("Avoid jargon or define terms when used", "clarity", 75),
                    DomainSuggestion("Include hands-on exercises", "engagement", 65),
                ],
            },
            "intermediate": {
                "indicators": ["intermediate", "some experience", "familiar with"],
                "suggestions": [
                    DomainSuggestion("Build on assumed foundational knowledge", "pedagogy", 60),
                    DomainSuggestion("Include challenging exercises", "engagement", 65),
                ],
            },
            "advanced": {
                "indicators": ["advanced", "expert", "deep dive", "in-depth"],
                "suggestions": [
                    DomainSuggestion("Focus on edge cases and nuances", "depth", 70),
                    DomainSuggestion("Include real-world production scenarios", "practical", 65),
                ],
            },
        },
        "pedagogical_patterns": {
            "feynman": {
                "indicators": ["explain like", "eli5", "simple terms", "child", "5 year old"],
                "suggestion": DomainSuggestion(
                    "🧠 Use Feynman Technique: Explain in simple terms",
                    "pedagogy",
                    70,
                    "If you can't explain it simply, you don't understand it well enough",
                ),
            },
        },
    },
    # -------------------------------------------------------------------------
    # DATA SCIENCE / ANALYTICS
    # -------------------------------------------------------------------------
    "data_science": {
        "keywords": [
            "data",
            "analysis",
            "machine learning",
            "ml",
            "ai",
            "model",
            "dataset",
            "feature",
            "training",
            "prediction",
            "regression",
            "classification",
            "clustering",
            "neural",
            "deep learning",
            "statistics",
            "visualization",
            "pandas",
            "numpy",
            "sklearn",
        ],
        "checks": {
            "data_quality": {
                "patterns": [r"\b(clean|preprocess|missing|null|outlier|validate)\b"],
                "suggestion": DomainSuggestion(
                    "🧹 Address data quality (missing values, outliers)",
                    "data_prep",
                    75,
                ),
            },
            "bias": {
                "patterns": [r"\b(bias|fairness|ethical|balanced|representative)\b"],
                "suggestion": DomainSuggestion(
                    "⚖️ Consider data bias and model fairness",
                    "ethics",
                    70,
                ),
            },
            "evaluation": {
                "patterns": [r"\b(accuracy|precision|recall|f1|auc|rmse|mae|metric)\b"],
                "suggestion": DomainSuggestion(
                    "📏 Define evaluation metrics appropriate for the task",
                    "evaluation",
                    70,
                ),
            },
        },
    },
}


# ==============================================================================
# DOMAIN HANDLER CLASS
# ==============================================================================


class DomainHandler(BaseHandler):
    """
    Domain Expert Handler - Subject Matter Expertise Engine.

    Provides domain-specific heuristics and best-practice enforcement based on
    the detected domain of the prompt.
    """

    def __init__(self):
        """Initialize the domain handler."""
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Pre-compile regex patterns for performance."""
        # Compile keyword patterns for each domain
        self._domain_keywords: Dict[str, re.Pattern] = {}
        for domain, rules in DOMAIN_RULES.items():
            keywords = rules.get("keywords", [])
            if keywords:
                pattern = r"\b(" + "|".join(re.escape(k) for k in keywords) + r")\b"
                self._domain_keywords[domain] = re.compile(pattern, re.IGNORECASE)

    def handle(self, ir_v2: IRv2, ir_v1: IR) -> None:
        """
        Apply domain-specific heuristics to enhance IR.

        This method:
        1. Confirms/refines the detected domain
        2. Applies domain-specific checks
        3. Adds specialized constraints and diagnostics
        """
        original_text = (ir_v1.metadata or {}).get("original_text", "")
        detected_domain = ir_v2.domain.lower() if ir_v2.domain else "general"

        # Perform domain analysis
        analysis = self.analyze_domain(original_text, detected_domain)

        # Add suggestions as constraints
        for suggestion in analysis.suggestions:
            ir_v2.constraints.append(
                ConstraintV2(
                    id=self._hash_id(suggestion.text),
                    text=suggestion.text,
                    origin=f"domain_{analysis.detected_domain}",
                    priority=suggestion.priority,
                    rationale=suggestion.rationale,
                )
            )

        # Add diagnostics
        ir_v2.diagnostics.extend(analysis.diagnostics)

        # Store analysis metadata
        ir_v2.metadata["domain_analysis"] = {
            "detected_domain": analysis.detected_domain,
            "sub_domain": analysis.sub_domain,
            "suggestion_count": len(analysis.suggestions),
            "detected_patterns": analysis.detected_patterns,
        }

    def _hash_id(self, text: str) -> str:
        """Generate a short hash ID."""
        import hashlib

        return hashlib.sha1(text.encode()).hexdigest()[:10]

    def analyze_domain(self, text: str, domain_hint: str = "") -> DomainAnalysis:
        """
        Perform comprehensive domain analysis.

        Args:
            text: The prompt text to analyze.
            domain_hint: Optional domain hint from prior analysis.

        Returns:
            DomainAnalysis with suggestions and diagnostics.
        """
        text_lower = text.lower()

        # Detect or confirm domain
        detected_domain = self._detect_domain(text_lower, domain_hint)

        # Route to domain-specific analyzer
        if detected_domain == "coding":
            return self._analyze_coding(text, text_lower)
        elif detected_domain == "creative_writing":
            return self._analyze_creative_writing(text, text_lower)
        elif detected_domain == "business":
            return self._analyze_business(text, text_lower)
        elif detected_domain == "education":
            return self._analyze_education(text, text_lower)
        elif detected_domain == "data_science":
            return self._analyze_data_science(text, text_lower)
        else:
            return DomainAnalysis(detected_domain=detected_domain)

    def _detect_domain(self, text_lower: str, hint: str) -> str:
        """Detect the primary domain of the text."""
        # Trust the hint if it's valid
        if hint and hint in DOMAIN_RULES:
            return hint

        # Count keyword matches per domain
        scores: Dict[str, int] = {}
        for domain, pattern in self._domain_keywords.items():
            matches = pattern.findall(text_lower)
            scores[domain] = len(matches)

        # Return domain with highest score, or "general" if none
        if scores:
            best = max(scores, key=scores.get)
            if scores[best] > 0:
                return best

        return "general"

    # --------------------------------------------------------------------------
    # CODING DOMAIN
    # --------------------------------------------------------------------------

    def _analyze_coding(self, text: str, text_lower: str) -> DomainAnalysis:
        """Analyze coding/software engineering prompts."""
        analysis = DomainAnalysis(detected_domain="coding")
        rules = DOMAIN_RULES["coding"]

        # Detect programming language
        detected_lang = self._detect_language(text_lower, rules["languages"])
        analysis.sub_domain = detected_lang

        # Add language-specific suggestions
        if detected_lang and detected_lang in rules["languages"]:
            lang_rules = rules["languages"][detected_lang]
            # AST Analysis for Python
            if detected_lang == "python":
                ast_suggestions, ast_diagnostics = self._analyze_python_ast(text)
                analysis.suggestions.extend(ast_suggestions)
                analysis.diagnostics.extend(ast_diagnostics)

            analysis.suggestions.extend(lang_rules.get("suggestions", []))
            analysis.detected_patterns["language"] = [detected_lang]

        # Check universal coding requirements
        for check_name, check_rules in rules["universal_checks"].items():
            missing_patterns = check_rules.get("missing_patterns", [])

            # Check if any pattern matches
            has_mention = False
            for pattern in missing_patterns:
                if re.search(pattern, text_lower):
                    has_mention = True
                    break

            # If not mentioned, suggest it
            if not has_mention:
                analysis.suggestions.append(check_rules["suggestion"])

            # Special case: Security Scanning (Expanded)
            if check_name == "security":
                self._scan_for_secrets(text, analysis)

        # Snippet Injection
        self._inject_snippets(text, analysis)

        return analysis

    def _analyze_python_ast(self, text: str) -> tuple[List[DomainSuggestion], List[DiagnosticItem]]:
        """
        Parse Python code using AST to find structural issues (missing type hints).
        Returns (suggestions, diagnostics).
        """
        suggestions = []
        diagnostics = []

        try:
            # Attempt to parse the prompt as code.
            # Users often paste snippets, so strict parsing might fail if it's natural language mixed with code.
            # We try to extract code blocks first.
            code_blocks = re.findall(r"```python(.*?)```", text, re.DOTALL)
            if not code_blocks:
                # If no markdown blocks, try parsing the whole text if it looks like code
                # (simple heuristic: contains "def " or "import ")
                if "def " in text or "import " in text:
                    code_blocks = [text]

            for code in code_blocks:
                try:
                    # Fix indentation issues
                    code = textwrap.dedent(code)
                    tree = ast.parse(code)

                    # Walker to check function definitions
                    for node in ast.walk(tree):
                        if isinstance(node, ast.FunctionDef):
                            # Check for missing return type hint, skipping __init__
                            if node.name != "__init__" and node.returns is None:
                                diagnostics.append(
                                    DiagnosticItem(
                                        severity="info",
                                        message=f"Function '{node.name}' is missing return type hint",
                                        suggestion=f"Add -> Type to '{node.name}'",
                                        category="type_safety",
                                    )
                                )

                            # Check args
                            for arg in node.args.args:
                                if arg.arg != "self" and arg.annotation is None:
                                    diagnostics.append(
                                        DiagnosticItem(
                                            severity="info",
                                            message=f"Argument '{arg.arg}' in '{node.name}' missing type hint",
                                            suggestion=f"Add type annotation to '{arg.arg}'",
                                            category="type_safety",
                                        )
                                    )

                except SyntaxError:
                    # It's expected that not all prompts are valid compilable code
                    pass

        except Exception:
            pass

        return suggestions, diagnostics

    def _inject_snippets(self, text: str, analysis: DomainAnalysis) -> None:
        """Inject stack-specific boilerplate if requested."""
        text_lower = text.lower()

        if "react" in text_lower and ("component" in text_lower or "code" in text_lower):
            # If standard React is requested
            if "tailwind" in text_lower:
                analysis.suggestions.append(
                    DomainSuggestion(
                        "⚛️ Use Tailwind CSS for styling",
                        "stack_recommendation",
                        70,
                        "Include 'className' props with Tailwind utility classes",
                    )
                )

        # If they mention shadcn/ui (implies React)
        if "shadcn" in text_lower or "ui component" in text_lower:
            analysis.suggestions.append(
                DomainSuggestion(
                    "🧱 Use shadcn/ui pattern (Radix + Tailwind)",
                    "architecture",
                    65,
                    "Import from '@/components/ui/...'",
                )
            )

    def _scan_for_secrets(self, text: str, analysis: DomainAnalysis) -> None:
        """Scan for API keys, tokens, and secrets using regex."""
        # Common secret patterns
        patterns = [
            r"(?i)(api[_-]?key|access[_-]?token|secret[_-]?key)\s*[:=]\s*['\"][a-zA-Z0-9_\-]{20,}['\"]",
            r"sk-[a-zA-Z0-9]{48}",  # OpenAI style
            r"ghp_[a-zA-Z0-9]{36}",  # GitHub Personal Access Token
            r"https://[a-zA-Z0-9]+:[a-zA-Z0-9]+@",  # Basic Auth in URL
        ]

        found = False
        for p in patterns:
            if re.search(p, text):
                found = True
                break

        if found:
            analysis.suggestions.append(
                DomainSuggestion(
                    "🔐 Review security implications (secrets detected)",
                    "security",
                    90,  # High priority
                    "Hardcoded secrets detected. Use environment variables.",
                )
            )
            analysis.diagnostics.append(
                DiagnosticItem(
                    severity="warning",
                    message="Hardcoded secret or API key pattern detected",
                    suggestion="Remove secrets and use environment variables",
                    category="security",
                )
            )

    def _detect_language(self, text_lower: str, language_rules: Dict) -> Optional[str]:
        """Detect the programming language from text."""
        scores: Dict[str, int] = {}

        for lang, rules in language_rules.items():
            indicators = rules.get("indicators", [])
            score = sum(1 for ind in indicators if ind.lower() in text_lower)
            if score > 0:
                scores[lang] = score

        if scores:
            return max(scores, key=scores.get)
        return None

    # --------------------------------------------------------------------------
    # CREATIVE WRITING DOMAIN
    # --------------------------------------------------------------------------

    def _analyze_creative_writing(self, text: str, text_lower: str) -> DomainAnalysis:
        """Analyze creative writing prompts."""
        analysis = DomainAnalysis(detected_domain="creative_writing")
        rules = DOMAIN_RULES["creative_writing"]

        # Check for story structure
        detected_structure = self._detect_story_structure(text_lower, rules["structures"])
        if detected_structure:
            analysis.sub_domain = detected_structure
            analysis.detected_patterns["structure"] = [detected_structure]
        else:
            # Suggest structure if plot elements detected
            if any(word in text_lower for word in ["plot", "story", "chapter", "character"]):
                analysis.suggestions.append(
                    DomainSuggestion(
                        "📖 Consider using Hero's Journey or Three-Act Structure",
                        "structure",
                        60,
                        "Story structures help organize narrative flow",
                    )
                )

        # Style checks
        style_checks = rules["style_checks"]

        # Adverb check
        adverb_check = style_checks["adverb_overuse"]
        adverbs = re.findall(adverb_check["pattern"], text_lower)
        words = text_lower.split()
        if words and len(adverbs) / len(words) > adverb_check["threshold"]:
            analysis.suggestions.append(adverb_check["suggestion"])
            analysis.diagnostics.append(
                DiagnosticItem(
                    severity="info",
                    message=f"High adverb density detected ({len(adverbs)} adverbs)",
                    suggestion="Consider using stronger verbs instead of adverbs",
                    category="style",
                )
            )
            analysis.detected_patterns["adverbs"] = adverbs[:5]  # First 5

        # Filter words check
        filter_check = style_checks["filter_words"]
        found_filters = [w for w in filter_check["words"] if w in text_lower]
        if found_filters:
            analysis.suggestions.append(filter_check["suggestion"])
            analysis.detected_patterns["filter_words"] = found_filters

        # Add universal suggestions
        analysis.suggestions.extend(rules["universal_suggestions"])

        return analysis

    def _detect_story_structure(self, text_lower: str, structures: Dict) -> Optional[str]:
        """Detect if a story structure is being used or requested."""
        for structure_name, rules in structures.items():
            indicators = rules.get("indicators", [])
            if any(ind in text_lower for ind in indicators):
                return structure_name
        return None

    # --------------------------------------------------------------------------
    # BUSINESS DOMAIN
    # --------------------------------------------------------------------------

    def _analyze_business(self, text: str, text_lower: str) -> DomainAnalysis:
        """Analyze business/strategy prompts."""
        analysis = DomainAnalysis(detected_domain="business")
        rules = DOMAIN_RULES["business"]

        # Always suggest BLUF for business content
        analysis.suggestions.append(rules["formats"]["bluf"]["suggestion"])

        # Check for required elements
        for element_name, element_rules in rules["required_elements"].items():
            patterns = element_rules.get("patterns", [])
            has_mention = any(re.search(p, text_lower) for p in patterns)

            if not has_mention:
                analysis.suggestions.append(element_rules["suggestion"])
                analysis.diagnostics.append(
                    DiagnosticItem(
                        severity="info",
                        message=f"Consider adding {element_name.replace('_', ' ')}",
                        suggestion=element_rules["suggestion"].text,
                        category="completeness",
                    )
                )

        # Detect frameworks mentioned
        detected_frameworks = []
        for framework, keywords in rules["frameworks"].items():
            if any(kw in text_lower for kw in keywords):
                detected_frameworks.append(framework)

        if detected_frameworks:
            analysis.detected_patterns["frameworks"] = detected_frameworks

        return analysis

    # --------------------------------------------------------------------------
    # EDUCATION DOMAIN
    # --------------------------------------------------------------------------

    def _analyze_education(self, text: str, text_lower: str) -> DomainAnalysis:
        """Analyze educational/teaching prompts."""
        analysis = DomainAnalysis(detected_domain="education")
        rules = DOMAIN_RULES["education"]

        # Detect skill level
        for level, level_rules in rules["levels"].items():
            indicators = level_rules.get("indicators", [])
            if any(ind in text_lower for ind in indicators):
                analysis.sub_domain = level
                analysis.suggestions.extend(level_rules.get("suggestions", []))
                break

        # Check for Feynman technique
        feynman = rules["pedagogical_patterns"]["feynman"]
        if any(ind in text_lower for ind in feynman["indicators"]):
            analysis.suggestions.append(feynman["suggestion"])
            analysis.detected_patterns["pedagogy"] = ["feynman"]

        return analysis

    # --------------------------------------------------------------------------
    # DATA SCIENCE DOMAIN
    # --------------------------------------------------------------------------

    def _analyze_data_science(self, text: str, text_lower: str) -> DomainAnalysis:
        """Analyze data science/ML prompts."""
        analysis = DomainAnalysis(detected_domain="data_science")
        rules = DOMAIN_RULES["data_science"]

        # Check for required elements
        for check_name, check_rules in rules["checks"].items():
            patterns = check_rules.get("patterns", [])
            has_mention = any(re.search(p, text_lower) for p in patterns)

            if not has_mention:
                analysis.suggestions.append(check_rules["suggestion"])

        return analysis


# ==============================================================================
# CONVENIENCE FUNCTIONS
# ==============================================================================


def analyze_domain(text: str, domain_hint: str = "") -> DomainAnalysis:
    """
    Convenience function to analyze domain-specific aspects of a prompt.

    Args:
        text: The prompt text to analyze.
        domain_hint: Optional domain hint.

    Returns:
        DomainAnalysis with suggestions and diagnostics.
    """
    handler = DomainHandler()
    return handler.analyze_domain(text, domain_hint)
