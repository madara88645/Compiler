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


def pick_persona(text: str) -> tuple[str, dict]:
    lower = text.lower()
    scores = {k: 0 for k in PERSONA_KEYWORDS}
    evidence: dict[str, list[str]] = {k: [] for k in PERSONA_KEYWORDS}
    for persona, pats in PERSONA_KEYWORDS.items():
        for p in pats:
            if re.search(p, lower):
                scores[persona] += 1
                evidence[persona].append(p)
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


def detect_summary(text: str) -> tuple[bool, int | None]:
    lower = text.lower()
    if any(k in lower for k in SUMMARY_KEYWORDS):
        # Try to find a number of bullets requested (e.g. "5 madde", "5 bullets")
        m = re.search(r"(\d{1,2})\s*(madde|bullet|bullets|özet|point|points)", lower)
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
        raw = [p.strip() for p in re.split(r"\bvs\b", lower) if p.strip()]
        items = raw
    # Turkish pattern: "x ile y karşılaştır" or "x ve y karşılaştır"
    if not items and any(k in lower for k in COMPARISON_KEYWORDS):
        m = re.search(r"(.+?)\s+(karşılaştır|compare)", lower)
        if m:
            segment = m.group(1)
            parts = re.split(r"\b(ve|ile|,|/|&|\|)\b", segment)
            cand = [
                p.strip()
                for p in parts
                if p and p.strip() and p not in {"ve", "ile", ",", "/", "&", "|"}
            ]
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
    if any(k in lower for k in VARIANT_KEYWORDS):
        m = re.search(r"(\d{1,2})\s*(alternatif|seçenek|variant|variants|options)", lower)
        if m:
            try:
                v = int(m.group(1))
                return max(2, min(v, 10))
            except ValueError:
                return 3
        # default if keyword present but no number
        return 3
    return 1


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
    dev_pats = PERSONA_KEYWORDS.get("developer", [])
    return any(re.search(p, lower) for p in dev_pats)


# Live debug detection (English + Turkish cues)
LIVE_DEBUG_KEYWORDS = [
    r"live debug",
    r"help me debug",
    r"debug this",
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


def detect_live_debug(text: str) -> bool:
    lower = text.lower()
    return any(re.search(p, lower) for p in LIVE_DEBUG_KEYWORDS)


# --- Privacy / PII detection (lightweight heuristic, no external deps) ---
PII_PATTERNS = {
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    # Simplistic international phone (avoids matching short numbers); requires 7+ digits overall
    "phone": re.compile(r"(?:(?:\+|00)?\d{1,3}[ \-]?)?(?:\d{3}[ \-]?){2,3}\d{2,4}"),
    # Credit card (13-16 digits with optional spaces/hyphens) – basic filter, later Luhn could be added
    "credit_card": re.compile(r"\b(?:\d[ -]?){13,16}\b"),
    # Turkish IBAN (TR + 24 digits) simplified
    "iban": re.compile(r"\bTR\d{24}\b", re.IGNORECASE),
}


def detect_pii(text: str) -> list[str]:
    flags: list[str] = []
    # To reduce false positives for credit cards: ensure at least 13 digits contiguous when stripped
    for kind, pat in PII_PATTERNS.items():
        for m in pat.finditer(text):
            val = m.group(0)
            if kind == "credit_card":
                digits = re.sub(r"[^0-9]", "", val)
                if len(digits) < 13:
                    continue
            if kind == "phone":
                digits = re.sub(r"[^0-9]", "", val)
                if len(digits) < 7:
                    continue
            if kind not in flags:
                flags.append(kind)
            # Do not collect more than 5 kinds to keep metadata small
            if len(flags) >= 5:
                break
    return flags


def detect_risk_flags(text: str) -> list[str]:
    lower = text.lower()
    flags: list[str] = []
    for cat, pats in RISK_KEYWORDS.items():
        if any(re.search(p, lower) for p in pats):
            flags.append(cat)
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


def estimate_complexity(text: str) -> str:
    length = len(text.split())
    unique = len(set(w.lower() for w in re.findall(r"[a-zA-ZğüşöçıİĞÜŞÖÇ0-9]+", text)))
    score = 0
    if length > 40:
        score += 1
    if unique > 30:
        score += 1
    if any(k in text.lower() for k in [" vs ", "compare", "karşılaştır"]):
        score += 1
    if any(k in text.lower() for k in ["teach", "öğret", "explain"]):
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
    return any(re.search(p, lower) for p in CODE_REQUEST_KEYWORDS)


def detect_language(text: str) -> str:
    # Simple heuristic: presence of Turkish or Spanish indicators, else default English
    lower = text.lower()
    tr_chars = "çğıöşü"
    if any(c in lower for c in tr_chars) or re.search(r"\bve\b|\bile\b|\bkimdir\b", lower):
        return "tr"
    # Spanish accents / inverted punctuation / common words
    if any(ch in text for ch in ("ñ", "á", "é", "í", "ó", "ú", "ü", "¿", "¡")) or re.search(
        r"\b(enséñame|por favor|hola|qué|análisis|rápido)\b", lower
    ):
        return "es"
    return "en"


def detect_domain(text: str) -> Tuple[str, List[str]]:
    lower = text.lower()
    evidence: List[str] = []
    for domain, pats in DOMAIN_PATTERNS.items():
        for p in pats:
            if re.search(p, lower):
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
    return any(re.search(p, lower) for p in RECENCY_KEYWORDS)


def extract_format(text: str) -> str:
    lower = text.lower()
    for fmt, pats in FORMAT_KEYWORDS.items():
        for p in pats:
            if re.search(p, lower):
                return fmt
    return "markdown"


def detect_length_hint(text: str) -> str:
    lower = text.lower()
    for hint, pats in LENGTH_KEYWORDS.items():
        for p in pats:
            if re.search(p, lower):
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
    return any(re.search(p, lower) for p in TEACHING_KEYWORDS)


def _normalize_currency(val: str) -> str:
    s = val.replace(" ", "")
    s = s.replace(",", ".")
    return s


def extract_inputs(text: str, lang: str) -> Dict[str, str]:
    lower = text.lower()
    inputs: Dict[str, str] = {}

    # Interest extraction (Turkish + English simple patterns)
    # ex: "futbol sever" -> interest=futbol
    m = re.search(r"\b([\wçğıöşü]+)\s+sever\b", lower)
    if m:
        inputs["interest"] = m.group(1)
    else:
        # common sports keywords
        sports = ["futbol", "football", "soccer", "basketbol", "basketball", "tenis", "tennis"]
        for s in sports:
            if re.search(rf"\b{s}\b", lower):
                inputs.setdefault("interest", s)
                break

    # Budget extraction (after duration to avoid capturing "10 dakikada" as money)
    budget_keywords = ["bütçe", "budget", "en fazla", "üst limit", "max", "limit", "under", "below"]
    money_pattern = re.compile(
        r"(₺|\$|€)?\s*([0-9]{1,3}(?:[.,][0-9]{3})*|[0-9]+)(?:\s*[-–]\s*(₺|\$|€)?\s*([0-9]{1,3}(?:[.,][0-9]{3})*|[0-9]+))?\s*(tl|₺|try|lira|usd|dolar|\$|eur|€)?"
    )
    has_budget_kw = any(k in lower for k in budget_keywords)
    mm = money_pattern.search(lower)
    if has_budget_kw and mm:
        cur1, v1, cur2, v2, cur3 = mm.groups()
        unit = cur3 or cur1 or cur2 or ""
        if v2:
            inputs["budget"] = f"{_normalize_currency(v1)}-{_normalize_currency(v2)} {unit}".strip()
        else:
            inputs["budget"] = f"{_normalize_currency(v1)} {unit}".strip()
    elif not has_budget_kw:
        # Only treat as budget_hint if currency symbol/word present
        if mm:
            cur1, v1, cur2, v2, cur3 = mm.groups()
            unit = cur3 or cur1 or cur2 or ""
            if cur1 or cur2 or cur3:
                if v2:
                    inputs[
                        "budget_hint"
                    ] = f"{_normalize_currency(v1)}-{_normalize_currency(v2)} {unit}".strip()
                else:
                    inputs["budget_hint"] = f"{_normalize_currency(v1)} {unit}".strip()

    # Format hint: only set if explicitly present in text
    for fmt, pats in FORMAT_KEYWORDS.items():
        for p in pats:
            if re.search(p, lower):
                inputs["format"] = fmt
                break
        if "format" in inputs:
            break

    # Level extraction (beginner/intermediate/advanced)
    if re.search(r"\b(beginner|entry|intro|novice)\b|\b(başlangıç|giriş|temel)\b", lower):
        inputs["level"] = "beginner"
    elif re.search(r"\b(intermediate|mid)\b|\b(orta seviye|orta)\b", lower):
        inputs["level"] = "intermediate"
    elif re.search(r"\b(advanced|expert)\b|\b(ileri|uzman)\b", lower):
        inputs["level"] = "advanced"

    # Duration extraction (minutes/hours)
    # Examples: "10 dakikada", "15 dk", "30 dakika", "1 saat", "in 10 minutes", "30 mins", "30m"
    # Verbal half-hour forms (Turkish & English)
    if "yarım saat" in lower or re.search(r"\bhalf\s+(an\s+)?hour\b", lower):
        inputs["duration"] = "30m"
    else:
        dur_patterns = [
            # Turkish with locative suffix
            (r"(\d{1,3})\s*(dk|dakika)(?:da|de|ta|te)?\b", "m"),
            (r"(\d{1,2})\s*(saat)(?:te|ta|de|da)?\b", "h"),
            # English
            (r"(\d{1,3})\s*(min|minute|minutes|mins|m)\b", "m"),
            (r"(\d{1,2})\s*(hour|hours|h)\b", "h"),
            (r"in\s*(\d{1,3})\s*(minutes|minute|mins)\b", "m"),
        ]
        for dp, norm in dur_patterns:
            md = re.search(dp, lower)
            if md:
                num = md.group(1)
                inputs["duration"] = f"{num}{norm}"
                break

    return inputs
