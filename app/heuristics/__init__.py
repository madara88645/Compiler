from __future__ import annotations
import json
import os
import re
from typing import Any, Dict, List, Tuple


try:
    import yaml  # type: ignore
except Exception:  # optional dependency
    yaml = None  # type: ignore

RECENCY_KEYWORDS = [
    # English temporal recency markers
    r"today",
    r"recent",
    r"latest",
    r"breaking",
    r"current",
    r"this week",
    r"this month",
    r"2025",
    # Turkish temporal markers (kept for TR input support)
    r"bugün",
    r"şu an",
    r"güncel",
    r"son gelişmeler",
    r"şimdi",
]

DOMAIN_PATTERNS: Dict[str, List[str]] = {
    "ai/nlp": [r"nlp", r"language model", r"prompt", r"embedding", r"transformer", r"tokenization"],
    "ai/ml": [
        r"machine learning",
        r"deep learning",
        r"neural",
        r"model eğit",
        r"yapay zeka",
        r"regression",
        r"classification",
    ],
    "finance": [
        r"borsa",
        r"hisse",
        r"stock",
        r"finans",
        r"döviz",
        r"usd",
        r"eur",
        r"investment",
        r"portfolio",
        r"hedging",
    ],
    "physics": [r"quantum", r"fizik", r"relativity", r"kuantum", r"particle"],
    "software": [
        r"api",
        r"microservice",
        r"docker",
        r"kubernetes",
        r"python",
        r"javascript",
        r"refactor",
        r"microservices",
    ],
    "cloud": [r"aws", r"azure", r"gcp", r"cloudformation", r"terraform", r"serverless"],
    # Newer domains for coverage
    "data-eng": [
        r"airflow",
        r"dbt",
        r"data pipeline",
        r"etl",
        r"elt",
        r"spark",
        r"kafka",
        r"warehouse",
    ],
    "mlops": [
        r"mlops",
        r"model registry",
        r"feature store",
        r"deployment",
        r"inference",
        r"monitoring",
    ],
    "security": [
        r"oauth",
        r"jwt",
        r"encryption",
        r"xss",
        r"csrf",
        r"sast",
        r"dast",
        r"pentest",
        r"owasp",
    ],
    "compliance": [r"gdpr", r"hipaa", r"soc 2", r"iso 27001", r"pci-dss", r"compliance"],
}

STYLE_KEYWORDS = ["structured", "academic", "resmi", "concise", "öz"]
TONE_KEYWORDS = ["friendly", "samimi", "formal", "objective", "tarafsız"]
FORMAT_KEYWORDS = {
    "json": [r"json"],
    "yaml": [r"yaml"],
    "markdown": [r"markdown", r"md"],
    "table": [r"table", r"tablo", r"csv"],
}
LENGTH_KEYWORDS = {
    "short": [r"short", r"kısa", r"brief"],
    "long": [r"long", r"detaylı", r"uzun", r"comprehensive"],
}

CONFLICT_RULES = [
    (
        re.compile(r"very short|kısa"),
        re.compile(r"high detail|detaylı|comprehensive"),
        "length_vs_detail",
    ),
]

TEACHING_KEYWORDS = [
    r"teach",
    r"explain",
    r"learn me",
    r"tutorial",
    r"guide",
    r"öğret",
    r"anlat",
    r"ders",
    r"öğrenmek istiyorum",
]

# Bolt Optimization: Pre-compile regexes for fast evaluation


# Persona keyword groups (simple scoring)
PERSONA_KEYWORDS = {
    "teacher": [
        r"teach",
        r"öğret",
        r"ders",
        r"explain",
        r"tutorial",
        r"öğretici",
        r"workshop",
        r"lesson",
    ],
    "researcher": [
        r"research",
        r"araştır",
        r"analyze",
        r"analysis",
        r"paper",
        r"literature",
        r"survey",
        r"systematic review",
    ],
    "coach": [
        r"coach",
        r"koç",
        r"motivate",
        r"motivation",
        r"rehberlik",
        r"encourage",
        r"accountability",
    ],
    "mentor": [r"mentor", r"mentorluk", r"career", r"kariyer", r"advice", r"guidance", r"growth"],
    # New: developer/coding assistant persona
    "developer": [
        r"pair program",
        r"pair-program",
        r"code with me",
        r"walk me through code",
        r"tdd",
        r"test driven",
        r"debug",
        r"refactor",
        r"implement",
        r"function",
        r"class",
        r"script",
        r"module",
        r"api",
        r"python",
        r"javascript",
        r"typescript",
        r"java",
        r"c#",
        r"go",
        r"rust",
        r"deno",
        r"node",
        r"kod",
        r"örnek kod",
        r"birlikte kodla",
        r"hata ayıkla",
        r"yeniden düzenle",
    ],
}

# Bolt Optimization: Pre-compile regexes for developer persona

# Bolt Optimization: Pre-compile regexes for all personas
_COMPILED_PERSONA_KEYWORDS = {k: [re.compile(p) for p in v] for k, v in PERSONA_KEYWORDS.items()}


def pick_persona(text: str) -> tuple[str, dict]:
    lower = text.lower()
    scores = {k: 0 for k in PERSONA_KEYWORDS}
    evidence: dict[str, list[str]] = {k: [] for k in PERSONA_KEYWORDS}

    for persona, compiled_pats in _COMPILED_PERSONA_KEYWORDS.items():
        if persona not in scores:
            scores[persona] = 0
            evidence[persona] = []
        for r in compiled_pats:
            if r.search(lower):
                scores[persona] += 1
                evidence[persona].append(r.pattern)
    # choose highest score, tie -> deterministic alphabetical order of persona key
    ranked = sorted(scores.items(), key=lambda x: (-x[1], x[0]))
    if ranked and ranked[0][1] > 0:
        chosen = ranked[0][0]
    else:
        chosen = "assistant"
    return chosen, {"scores": scores, "evidence": evidence, "chosen": chosen}


# --- New general-purpose heuristics ---
SUMMARY_KEYWORDS = [
    r"özetle",
    r"kısaca",
    r"tl;dr",
    r"summarize",
    r"summary",
    r"brief",
    r"short version",
    r"abstract",
    r"condense",
    r"outline",
]
COMPARISON_KEYWORDS = [r"karşılaştır", r"vs", r"hangisi", r"compare", r"versus", r"farkları"]
VARIANT_KEYWORDS = [
    r"alternatif",
    r"alternatifler",
    r"alternatives",
    r"variants",
    r"seçenek",
    r"options",
    r"choices",
]

CREATIVE_INTENT_KEYWORDS = [
    "creative",
    "story",
    "poem",
    "headline",
    "tagline",
    "launch post",
    "copywriting",
    "fiction",
    "narrative",
    "brainstorm names",
]

EXPLANATION_INTENT_KEYWORDS = [
    "explain",
    "walk me through",
    "how does",
    "how do",
    "clarify",
    "break down",
    "help me understand",
]

PROPOSAL_INTENT_KEYWORDS = [
    "proposal",
    "propose",
    "pitch",
    "recommend a strategy",
    "suggest a strategy",
]

REVIEW_INTENT_KEYWORDS = [
    "review",
    "critique",
    "audit",
    "evaluate",
    "assess",
    "check my",
]

PREPARATION_INTENT_KEYWORDS = [
    "prepare me",
    "prep me",
    "interview prep",
    "study plan",
    "practice questions",
    "mock interview",
]

TROUBLESHOOTING_INTENT_KEYWORDS = [
    "troubleshoot",
    "troubleshooting",
    "diagnose",
    "debug this",
    "fix this error",
    "why is this failing",
    "why my",
    "traceback",
    "stack trace",
]


def detect_summary(text: str) -> tuple[bool, int | None]:
    lower = text.lower()
    has_summary = False
    for k in SUMMARY_KEYWORDS:
        if k in lower:
            has_summary = True
            break
    if has_summary:
        # Try to find a number of bullets requested (e.g. "5 madde", "5 bullets")
        m = _BULLET_RE.search(lower)
        if m:
            try:
                n = int(m.group(1))
                return True, n
            except ValueError:
                pass
        return True, None
    return False, None


def extract_comparison_items(text: str) -> list[str]:
    lower = text.lower()
    items: list[str] = []
    # common pattern: "x vs y" or "x vs y vs z"
    if " vs " in lower:
        raw = [p.strip() for p in lower.split(" vs ") if p.strip()]
        items = raw
    # Turkish pattern: "x ile y karşılaştır" or "x ve y karşılaştır"
    has_comparison = False
    if not items:
        for k in COMPARISON_KEYWORDS:
            if k in lower:
                has_comparison = True
                break
    if has_comparison:
        marker_index = min(
            (
                pos
                for pos in (
                    lower.find(" compare"),
                    lower.find(" karşılaştır"),
                )
                if pos != -1
            ),
            default=-1,
        )
        if marker_index != -1:
            segment = " ".join(lower[:marker_index].split())
            normalized = (
                segment.replace(",", ";").replace("/", ";").replace("&", ";").replace("|", ";")
            )
            padded = f" {normalized} "
            padded = padded.replace(" ile ", ";").replace(" ve ", ";")
            cand = [p.strip() for p in padded.split(";") if p.strip()]
            if len(cand) >= 2:
                items = cand
    # de-dup & shorten
    cleaned: list[str] = []
    seen = set()
    for it in items:
        it2 = it[:40].strip()
        if not it2:
            continue
        if it2 in seen:
            continue
        seen.add(it2)
        cleaned.append(it2)
    return cleaned


def extract_variant_count(text: str) -> int:
    lower = text.lower()
    has_variant = False
    for k in VARIANT_KEYWORDS:
        if k in lower:
            has_variant = True
            break

    # Bolt Optimization: Replace any() generator expression with fast-path loop to avoid overhead
    if has_variant:
        m = _VARIANT_RE.search(lower)
        if m:
            try:
                v = int(m.group(1))
                return max(2, min(v, 10))
            except ValueError:
                return 3
        # default if keyword present but no number
        return 3
    return 1


def _contains_any_keyword(text: str, keywords: list[str]) -> bool:
    lower = text.lower()
    for keyword in keywords:
        if keyword in lower:
            return True
    return False


def detect_creative_intent(text: str) -> bool:
    return _contains_any_keyword(text, CREATIVE_INTENT_KEYWORDS)


def detect_explanation_intent(text: str) -> bool:
    return _contains_any_keyword(text, EXPLANATION_INTENT_KEYWORDS)


def detect_proposal_intent(text: str) -> bool:
    return _contains_any_keyword(text, PROPOSAL_INTENT_KEYWORDS)


def detect_review_intent(text: str) -> bool:
    return _contains_any_keyword(text, REVIEW_INTENT_KEYWORDS)


def detect_preparation_intent(text: str) -> bool:
    return _contains_any_keyword(text, PREPARATION_INTENT_KEYWORDS)


def detect_troubleshooting_intent(text: str) -> bool:
    return detect_live_debug(text) or _contains_any_keyword(text, TROUBLESHOOTING_INTENT_KEYWORDS)


# --- Extended heuristics (IR & heuristics expansion) ---

RISK_KEYWORDS = {
    "financial": [
        r"yatırım",
        r"hisse",
        r"borsa",
        r"stock",
        r"invest",
        r"trading",
        r"kripto",
        r"crypto",
        r"portfolio",
        r"derivative",
        r"option pricing",
    ],
    "health": [
        r"diyet",
        r"sağlık",
        r"hastalık",
        r"disease",
        r"treatment",
        r"therapy",
        r"nutrition",
        r"medical",
        r"diagnosis",
        r"supplement",
        r"medicine",
        r"drug",
        r"pill",
        r"pain",
        r"headache",
        r"symptom",
        r"doctor",
        r"physician",
        # Added missing TR keywords
        r"ağrı",
        r"semptom",
        r"ilaç",
        r"doktor",
        r"hastane",
        r"tedavi",
        r"karnım",
        r"midem",
        r"başım",
    ],
    "legal": [
        r"sözleşme",
        r"contract",
        r"legal",
        r"hukuk",
        r"sue",
        r"dava",
        r"regulation",
        r"compliance",
        r"policy",
        r"regulatory",
        r"lawsuit",
        r"lawyer",
        r"attorney",
        r"court",
        r"litigation",
    ],
    "security": [
        r"security",
        r"güvenlik",
        r"pentest",
        r"owasp",
        r"rce",
        r"xss",
        r"csrf",
        r"sql injection",
        r"injection attack",
        r"exclude",
        r"bypass",
        r"hack",
        r"exploit",
    ],
    "privacy": [
        r"privacy",
        r"gdpr",
        r"ccpa",
        r"data protection",
        r"consent",
        r"personal data",
        r"kişisel veri",
        r"gizlilik",
        r"aydınlatma metni",
        r"kvkk",
    ],
    "infrastructure": [
        r"deploy",
        r"production",
        r"server",
        r"database migration",
        r"rollback",
        r"downtime",
        r"kubernetes",
        r"terraform",
        r"docker",
        r"ci/cd",
        r"pipeline",
        r"sunucu",
        r"yayınlama",
    ],
}

AMBIGUOUS_TERMS = {
    "optimize": {
        "question": "Which metric or aspect should be optimized? (performance, cost, memory?)",
        "category": "performance",
    },
    "improve": {
        "question": "What specific improvement dimension matters (speed, accuracy, UX?)",
        "category": "quality",
    },
    "better": {
        "question": "Better in what sense (quality, efficiency, reliability?)",
        "category": "quality",
    },
    "efficient": {
        "question": "Which resource should be minimized (time, memory, cost?)",
        "category": "performance",
    },
    "scalable": {"question": "Target scale or concurrency level?", "category": "scalability"},
    "fast": {"question": "What response time / throughput target?", "category": "performance"},
    "robust": {
        "question": "Robust against which failures or edge cases?",
        "category": "reliability",
    },
    "secure": {
        "question": "What threat model or security properties (confidentiality, integrity, availability?)",
        "category": "security",
    },
    "resilient": {
        "question": "Resilient against which failure modes (network partition, instance crash, data loss?)",
        "category": "reliability",
    },
    "scalable architecture": {
        "question": "Target scale, throughput or users? Horizontal/vertical scaling?",
        "category": "scalability",
    },
    "optimize costs": {
        "question": "Which cost component (compute, storage, egress, API)?",
        "category": "cost",
    },
}

CODE_REQUEST_KEYWORDS = [
    r"code",
    r"function",
    r"snippet",
    r"implement",
    r"class",
    r"python",
    r"örnek kod",
    r"kod",
    r"script",
    r"algorithm",
]


def detect_coding_context(text: str) -> bool:
    """Broader coding trigger: either explicit code request or developer persona cues."""
    lower = text.lower()
    if detect_code_request(text):
        return True
    for p in PERSONA_KEYWORDS["developer"]:
        if p in lower:
            return True
    return False


# Live debug detection (English + Turkish cues)
LIVE_DEBUG_KEYWORDS = [
    r"live debug",
    r"help me debug",
    r"debug this",
    r"why is this failing",
    r"fix this error",
    r"traceback",
    r"stack trace",
    r"exception",
    r"reproduce",
    r"reproduction steps",
    r"minimal repro",
    r"mre",
    r"logs?",
    r"error log",
    r"canlı debug",
    r"canli debug",
    r"canlı hata ayıklama",
    r"hata ayıkla",
    r"hata ayıklama",
    r"yığın izi",
    r"istisna",
]

_JOINED_LIVE_DEBUG = re.compile("|".join(LIVE_DEBUG_KEYWORDS))


def detect_live_debug(text: str) -> bool:
    lower = text.lower()
    return bool(_JOINED_LIVE_DEBUG.search(lower))


# --- Privacy / PII detection (lightweight heuristic, no external deps) ---
PII_PATTERNS = {
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    # Simplistic international phone (avoids matching short numbers); requires 7+ digits overall
    "phone": re.compile(r"(?:(?:\+|00)?\d{1,3}[ \-]?)?(?:\d{3}[ \-]?){2,3}\d{2,4}"),
    # Credit card (13-16 digits with optional spaces/hyphens) – basic filter, later Luhn could be added
    "credit_card": re.compile(r"\b(?:\d[ -]?){13,16}\b"),
    # Turkish IBAN (TR + 24 digits) simplified
    "iban": re.compile(r"\bTR\d{24}\b", re.IGNORECASE),
    # US Social Security Number (XXX-XX-XXXX)
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    # Passport number (1-2 letters + 6-9 digits, covers US/UK/TR/EU)
    "passport": re.compile(r"\b[A-Z]{1,2}\d{6,9}\b"),
    # Turkish TC Kimlik No (11 digits, starts with non-zero)
    "tc_kimlik": re.compile(r"\b[1-9]\d{10}\b"),
}


_PII_CONTEXT_FALSE_POSITIVE_HINTS = (
    "example",
    "sample",
    "dummy",
    "placeholder",
    "format",
    "mask",
    "regex",
    "test data",
    "fake",
)


def _is_tc_kimlik_valid(value: str) -> bool:
    """Validate Turkish TC Kimlik number checksum to reduce false positives."""
    if not re.fullmatch(r"[1-9]\d{10}", value):
        return False
    digits = [int(ch) for ch in value]
    odd_sum = sum(digits[0:9:2])
    even_sum = sum(digits[1:8:2])
    check_10 = ((odd_sum * 7) - even_sum) % 10
    check_11 = sum(digits[:10]) % 10
    return digits[9] == check_10 and digits[10] == check_11


def _has_fp_hint_around_match(text: str, start: int, end: int, window: int = 24) -> bool:
    lo = max(0, start - window)
    hi = min(len(text), end + window)
    ctx = text[lo:hi].lower()
    return any(hint in ctx for hint in _PII_CONTEXT_FALSE_POSITIVE_HINTS)


def detect_pii(text: str) -> list[str]:
    flags: list[str] = []
    # To reduce false positives for credit cards: ensure at least 13 digits contiguous when stripped
    for kind, pat in PII_PATTERNS.items():
        for m in pat.finditer(text):
            val = m.group(0)
            if kind == "credit_card":
                # Bolt Optimization: map() is ~3x faster than generator sum for counting characters
                digits_count = sum(map(str.isdigit, val))
                if digits_count < 13:
                    continue
            if kind == "phone":
                # Bolt Optimization: map() is ~3x faster than generator sum for counting characters
                digits_count = sum(map(str.isdigit, val))
                if digits_count < 7:
                    continue
            if kind in {"ssn", "passport"} and _has_fp_hint_around_match(text, m.start(), m.end()):
                continue
            if kind == "tc_kimlik" and not _is_tc_kimlik_valid(val):
                continue
            if kind not in flags:
                flags.append(kind)
            # Do not collect more than 5 kinds to keep metadata small
            if len(flags) >= 5:
                break
        if len(flags) >= 5:
            break
    return flags


def detect_risk_flags(text: str) -> list[str]:
    lower = text.lower()
    flags: list[str] = []
    for cat, pats in RISK_KEYWORDS.items():
        for p in pats:
            if p in lower:
                flags.append(cat)
                break
    return flags


def extract_entities(text: str) -> list[str]:
    # Simple heuristic: capitalized tokens & tech patterns
    entities: list[str] = []
    # Capture tokens like GPT-4, ISO 27001, Kubernetes
    pattern = re.compile(r"\b([A-Z][a-zA-Z0-9_-]{2,}|[A-Z]{2,}\d{0,4}|GPT-\d|ISO\s?\d{3,5})\b")
    for m in pattern.finditer(text):
        val = m.group(1)
        if val and val not in entities and len(entities) < 30:
            entities.append(val)
    return entities


_COMPLEXITY_WORD_RE = re.compile(r"[a-zA-ZğüşöçıİĞÜŞÖÇ0-9\u0307]+")


def estimate_complexity(text: str) -> str:
    # Bolt Optimization: compute lower once and use it instead of redundant calls
    # and lower() generators.
    lower = text.lower()
    length = len(text.split())
    # Keep uppercase letters in regex pattern so it accurately matches tokens
    # that contain combining character variants when lowered (e.g. \u0307)
    # Bolt Optimization: Pre-compiled regex for .findall() is faster than re.findall
    unique = len(set(_COMPLEXITY_WORD_RE.findall(lower)))
    score = 0
    if length > 40:
        score += 1
    if unique > 30:
        score += 1
    if " vs " in lower or "compare" in lower or "karşılaştır" in lower:
        score += 1
    if "teach" in lower or "öğret" in lower or "explain" in lower:
        score += 1
    return "high" if score >= 3 else "medium" if score == 2 else "low"


def detect_ambiguous_terms(text: str) -> list[str]:
    lower = text.lower()
    return [t for t in AMBIGUOUS_TERMS if t in lower]


def generate_clarify_questions(terms: list[str]) -> list[str]:
    # Backward compatible simple list (used by existing tests)
    out: list[str] = []
    for t in terms:
        info = AMBIGUOUS_TERMS.get(t)
        if not info:
            continue
        q = info["question"]
        if q not in out:
            out.append(q)
        if len(out) >= 5:
            break
    return out


def generate_clarify_questions_struct(terms: list[str]) -> list[dict[str, Any]]:
    struct: list[dict[str, Any]] = []
    for t in terms:
        info = AMBIGUOUS_TERMS.get(t)
        if not info:
            continue
        struct.append(
            {"term": t, "category": info.get("category"), "question": info.get("question")}
        )
        if len(struct) >= 5:
            break
    return struct


# --- Temporal & Quantity Extraction ---
YEAR_PATTERN = re.compile(r"\b(19\d{2}|20\d{2})\b")
QUARTER_PATTERN = re.compile(r"\bq([1-4])\s*(20\d{2})\b", re.IGNORECASE)
MONTHS = [
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
    # Turkish month names
    "ocak",
    "şubat",
    "subat",
    "mart",
    "nisan",
    "mayıs",
    "mayis",
    "haziran",
    "temmuz",
    "ağustos",
    "agustos",
    "eylül",
    "eylul",
    "ekim",
    "kasım",
    "kasim",
    "aralık",
    "aralik",
]
REL_TEMPORAL = [
    "today",
    "yesterday",
    "tomorrow",
    "this week",
    "next week",
    "this month",
    "next month",
    "this year",
    "recent",
]


def extract_temporal_flags(text: str) -> list[str]:
    lower = text.lower()
    flags: list[str] = []
    for m in YEAR_PATTERN.findall(text):
        if m not in flags:
            flags.append(m)
    for qm in QUARTER_PATTERN.findall(text):
        qflag = f"Q{qm[0]} {qm[1]}"
        if qflag not in flags:
            flags.append(qflag)
    for m in MONTHS:
        if m in lower and m not in flags:
            flags.append(m)
    for token in REL_TEMPORAL:
        if token in lower and token not in flags:
            flags.append(token)
    return flags[:20]


QUANTITY_PATTERN = re.compile(
    r"\b(\d+(?:\.\d+)?)\s*(ms|s|sec|seconds|m|min|minutes|h|hours|d|day|days|w|week|weeks|%|percent|users?|reqs?|requests?|kb|mb|gb|tb)\b",
    re.IGNORECASE,
)


def extract_quantities(text: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for m in QUANTITY_PATTERN.finditer(text):
        val, unit = m.groups()
        unit_norm = unit.lower()
        out.append({"value": val, "unit": unit_norm})
        if len(out) >= 30:
            break
    # Range pattern like 1500-3000 ms
    range_pat = re.compile(
        r"\b(\d{2,})-(\d{2,})\s*(ms|s|m|h|users|requests|reqs|mb|gb|tb|%)?\b", re.IGNORECASE
    )
    for m in range_pat.finditer(text):
        v1, v2, unit = m.groups()
        out.append({"value": f"{v1}-{v2}", "unit": (unit or "").lower()})
        if len(out) >= 40:
            break
    return out


# --- Config Externalization ---
CONFIG_PATH = os.environ.get("PROMPTC_CONFIG", "config/patterns.yml")


def _apply_external_config(data: dict[str, Any]):
    global DOMAIN_PATTERNS, AMBIGUOUS_TERMS, RISK_KEYWORDS
    if "domain_patterns" in data and isinstance(data["domain_patterns"], dict):
        DOMAIN_PATTERNS = {
            k: list(v) for k, v in data["domain_patterns"].items() if isinstance(v, (list, tuple))
        }
    if "ambiguous_terms" in data and isinstance(data["ambiguous_terms"], dict):
        # expected format: term: {question:..., category:...}
        AMBIGUOUS_TERMS = data["ambiguous_terms"]  # type: ignore
    if "risk_keywords" in data and isinstance(data["risk_keywords"], dict):
        RISK_KEYWORDS = data["risk_keywords"]  # type: ignore


def load_external_config(path: str = CONFIG_PATH) -> bool:
    if not os.path.exists(path):
        return False
    try:
        if yaml:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        else:
            # Very naive fallback: expect JSON if yaml not available
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        if isinstance(data, dict):
            _apply_external_config(data)
            return True
    except Exception:
        return False
    return False


def reload_patterns():
    load_external_config()


# Initial load attempt (non-fatal)
load_external_config()


def detect_code_request(text: str) -> bool:
    lower = text.lower()
    for p in CODE_REQUEST_KEYWORDS:
        if p in lower:
            return True
    return False


# Bolt Optimization: Pre-compile regexes for fast evaluation
_TR_LANG_RE = re.compile(r"\bve\b|\bile\b|\bkimdir\b")
_ES_LANG_RE = re.compile(r"\b(enséñame|por favor|hola|qué|análisis|rápido)\b")

_BULLET_RE = re.compile(r"(\d{1,2})\s*(madde|bullet|bullets|özet|point|points)")
_VARIANT_RE = re.compile(r"(\d{1,2})\s*(alternatif|seçenek|variant|variants|options)")
_SEVER_RE = re.compile(r"\b([\wçğıöşü]+)\s+sever\b")
_LEVEL_BEGINNER_RE = re.compile(r"\b(beginner|entry|intro|novice)\b|\b(başlangıç|giriş|temel)\b")
_LEVEL_INTERMEDIATE_RE = re.compile(r"\b(intermediate|mid)\b|\b(orta seviye|orta)\b")
_LEVEL_ADVANCED_RE = re.compile(r"\b(advanced|expert)\b|\b(ileri|uzman)\b")
_HALF_HOUR_RE = re.compile(r"\bhalf\s+(an\s+)?hour\b")

# Bolt Optimization: Pre-compile regex patterns for extract_inputs
_SPORTS_PATTERNS = [
    (s, re.compile(rf"\b{s}\b"))
    for s in ["futbol", "football", "soccer", "basketbol", "basketball", "tenis", "tennis"]
]

_DUR_PATTERNS = [
    # Turkish with locative suffix
    (re.compile(r"(\d{1,3})\s*(dk|dakika)(?:da|de|ta|te)?\b"), "m"),
    (re.compile(r"(\d{1,2})\s*(saat)(?:te|ta|de|da)?\b"), "h"),
    # English
    (re.compile(r"(\d{1,3})\s*(min|minute|minutes|mins|m)\b"), "m"),
    (re.compile(r"(\d{1,2})\s*(hour|hours|h)\b"), "h"),
    (re.compile(r"in\s*(\d{1,3})\s*(minutes|minute|mins)\b"), "m"),
]


def detect_language(text: str) -> str:
    # Simple heuristic: presence of Turkish or Spanish indicators, else default English
    lower = text.lower()
    tr_chars = "çğıöşü"

    has_tr = False
    for c in tr_chars:
        if c in lower:
            has_tr = True
            break
    if has_tr or _TR_LANG_RE.search(lower):
        return "tr"

    # Spanish accents / inverted punctuation / common words
    has_es = False
    for ch in ("ñ", "á", "é", "í", "ó", "ú", "ü", "¿", "¡"):
        if ch in text:
            has_es = True
            break
    if has_es or _ES_LANG_RE.search(lower):
        return "es"

    return "en"


def detect_domain(text: str) -> Tuple[str, List[str]]:
    lower = text.lower()
    evidence: List[str] = []
    for domain, pats in DOMAIN_PATTERNS.items():
        for p in pats:
            if p in lower:
                evidence.append(f"{domain}:{p}")
    if not evidence:
        return "general", []
    # Choose the domain with most evidence counts
    counts: Dict[str, int] = {}
    for ev in evidence:
        d = ev.split(":", 1)[0]
        counts[d] = counts.get(d, 0) + 1
    domain = sorted(counts.items(), key=lambda x: (-x[1], x[0]))[0][0]
    return domain, evidence


def detect_domain_candidates(evidence: List[str], top_k: int = 3) -> List[str]:
    """Return ordered list of plausible domain candidates from evidence.

    Keeps deterministic ordering: primary domain first then others by count then name.
    """
    if not evidence:
        return []
    counts: Dict[str, int] = {}
    for ev in evidence:
        d = ev.split(":", 1)[0]
        counts[d] = counts.get(d, 0) + 1
    ranked = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
    return [d for d, _ in ranked[:top_k]]


def detect_recency(text: str) -> bool:
    lower = text.lower()
    for p in RECENCY_KEYWORDS:
        if p in lower:
            return True
    return False


def extract_format(text: str) -> str:
    lower = text.lower()
    for fmt, pats in FORMAT_KEYWORDS.items():
        for p in pats:
            if p in lower:
                return fmt
    return "markdown"


def detect_length_hint(text: str) -> str:
    lower = text.lower()
    for hint, pats in LENGTH_KEYWORDS.items():
        for p in pats:
            if p in lower:
                if hint == "short":
                    return "short"
                if hint == "long":
                    return "long"
    return "medium"


def extract_style_tone(text: str) -> Tuple[List[str], List[str]]:
    lower = text.lower()
    style = [w for w in STYLE_KEYWORDS if w in lower]
    tone = [w for w in TONE_KEYWORDS if w in lower]
    return style, tone


def detect_conflicts(constraints: List[str]) -> List[str]:
    conflicts: List[str] = []
    joined = " | ".join(constraints).lower()
    for a, b, code in CONFLICT_RULES:
        if a.search(joined) and b.search(joined):
            conflicts.append(code)
    return conflicts


def detect_teaching_intent(text: str) -> bool:
    lower = text.lower()
    for p in TEACHING_KEYWORDS:
        if p in lower:
            return True
    return False


def _normalize_currency(val: str) -> str:
    s = val.replace(" ", "")
    s = s.replace(",", ".")
    return s


_MONEY_TOKEN_RE = re.compile(
    r"^(?P<prefix>[$\u20ac\u20ba]?)(?P<value>\d+(?:[.,]\d+)*)(?P<suffix>[$\u20ac\u20ba]?)$"
)
_CURRENCY_WORDS = {"tl", "try", "lira", "usd", "dolar", "eur"}


def _tokenize_money_text(text: str) -> list[str]:
    tokens: list[str] = []
    current: list[str] = []
    for ch in text:
        if ch.isalnum() or ch in ".,$\u20ac\u20ba":
            current.append(ch)
            continue
        if current:
            tokens.append("".join(current))
            current = []
        if ch in "-\u2013":
            tokens.append("-")
    if current:
        tokens.append("".join(current))
    return tokens


def _match_money_token(token: str) -> re.Match[str] | None:
    stripped = token.rstrip(".,")
    if not stripped:
        return None
    return _MONEY_TOKEN_RE.match(stripped)


def _extract_money_candidate(text: str, require_currency: bool) -> str | None:
    tokens = _tokenize_money_text(text)
    for index, token in enumerate(tokens):
        match = _match_money_token(token)
        if not match:
            continue

        unit = match.group("prefix") or match.group("suffix") or ""
        value = _normalize_currency(match.group("value"))
        cursor = index + 1

        if cursor < len(tokens) and tokens[cursor] in _CURRENCY_WORDS:
            unit = unit or tokens[cursor]
            cursor += 1

        ranged_value = value
        if cursor + 1 < len(tokens) and tokens[cursor] == "-":
            next_match = _match_money_token(tokens[cursor + 1])
            if next_match:
                ranged_value = f"{value}-{_normalize_currency(next_match.group('value'))}"
                unit = unit or next_match.group("prefix") or next_match.group("suffix") or ""
                cursor += 2
                if cursor < len(tokens) and tokens[cursor] in _CURRENCY_WORDS:
                    unit = unit or tokens[cursor]

        if require_currency and not unit:
            continue

        return f"{ranged_value} {unit}".strip()

    return None


def extract_inputs(text: str, lang: str) -> Dict[str, str]:
    lower = text.lower()
    inputs: Dict[str, str] = {}

    # Interest extraction (Turkish + English simple patterns)
    # ex: "futbol sever" -> interest=futbol
    m = _SEVER_RE.search(lower)
    if m:
        inputs["interest"] = m.group(1)
    else:
        # common sports keywords
        # Bolt Optimization: Explict loop replaces dynamic regex compilation
        for s, pattern in _SPORTS_PATTERNS:
            if pattern.search(lower):
                inputs.setdefault("interest", s)
                break

    # Budget extraction (after duration to avoid capturing "10 dakikada" as money)
    budget_keywords = ["bütçe", "budget", "en fazla", "üst limit", "max", "limit", "under", "below"]
    has_budget_kw = False
    for k in budget_keywords:
        if k in lower:
            has_budget_kw = True
            break
    if has_budget_kw:
        keyword_positions = [lower.find(keyword) for keyword in budget_keywords if keyword in lower]
        budget_search_text = lower[min(keyword_positions) :] if keyword_positions else lower
        budget_value = _extract_money_candidate(budget_search_text, require_currency=False)
        if budget_value:
            inputs["budget"] = budget_value
    else:
        budget_hint = _extract_money_candidate(lower, require_currency=True)
        if budget_hint:
            inputs["budget_hint"] = budget_hint

    # Format hint: only set if explicitly present in text
    for fmt, pats in FORMAT_KEYWORDS.items():
        for p in pats:
            if p in lower:
                inputs["format"] = fmt
                break
        if "format" in inputs:
            break

    # Level extraction (beginner/intermediate/advanced)
    if _LEVEL_BEGINNER_RE.search(lower):
        inputs["level"] = "beginner"
    elif _LEVEL_INTERMEDIATE_RE.search(lower):
        inputs["level"] = "intermediate"
    elif _LEVEL_ADVANCED_RE.search(lower):
        inputs["level"] = "advanced"

    # Duration extraction (minutes/hours)
    # Examples: "10 dakikada", "15 dk", "30 dakika", "1 saat", "in 10 minutes", "30 mins", "30m"
    # Verbal half-hour forms (Turkish & English)
    if "yarım saat" in lower or _HALF_HOUR_RE.search(lower):
        inputs["duration"] = "30m"
    else:
        # Bolt Optimization: Used pre-compiled _DUR_PATTERNS
        for dp_compiled, norm in _DUR_PATTERNS:
            md = dp_compiled.search(lower)
            if md:
                num = md.group(1)
                inputs["duration"] = f"{num}{norm}"
                break

    return inputs
