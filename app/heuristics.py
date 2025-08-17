from __future__ import annotations
import re
from typing import Tuple, List, Dict

RECENCY_KEYWORDS = [
    r"today", r"recent", r"latest", r"breaking", r"current", r"2025",
    r"bugün", r"şu an", r"güncel", r"son gelişmeler", r"şimdi"
]

DOMAIN_PATTERNS: Dict[str, List[str]] = {
    "ai/nlp": [r"nlp", r"language model", r"prompt", r"embedding", r"transformer"],
    "ai/ml": [r"machine learning", r"deep learning", r"neural", r"model eğit", r"yapay zeka"],
    "finance": [r"borsa", r"hisse", r"stock", r"finans", r"döviz", r"usd", r"eur"],
    "physics": [r"quantum", r"fizik", r"relativity", r"kuantum"],
    "software": [r"api", r"microservice", r"docker", r"kubernetes", r"python", r"javascript"],
}

STYLE_KEYWORDS = ["structured", "academic", "resmi", "concise", "öz" ]
TONE_KEYWORDS = ["friendly", "samimi", "formal", "objective", "tarafsız"]
FORMAT_KEYWORDS = {
    "json": [r"json"],
    "yaml": [r"yaml"],
    "markdown": [r"markdown", r"md"],
    "table": [r"table", r"tablo"],
}
LENGTH_KEYWORDS = {
    "short": [r"short", r"kısa", r"brief"],
    "long": [r"long", r"detaylı", r"uzun", r"comprehensive"],
}

CONFLICT_RULES = [
    (re.compile(r"very short|kısa"), re.compile(r"high detail|detaylı|comprehensive"), "length_vs_detail"),
]

TEACHING_KEYWORDS = [
    r"teach", r"explain", r"learn me", r"tutorial", r"guide",
    r"öğret", r"anlat", r"ders", r"öğrenmek istiyorum"
]

# Persona keyword groups (simple scoring)
PERSONA_KEYWORDS = {
    "teacher": [r"teach", r"öğret", r"ders", r"explain", r"tutorial", r"öğretici"],
    "researcher": [r"research", r"araştır", r"analyze", r"analysis", r"paper", r"literature"],
    "coach": [r"coach", r"koç", r"motivate", r"motivation", r"rehberlik"],
    "mentor": [r"mentor", r"mentorluk", r"career", r"kariyer", r"advice", r"guidance"],
}

def pick_persona(text: str) -> tuple[str, dict]:
    lower = text.lower()
    scores = {k:0 for k in PERSONA_KEYWORDS}
    evidence: dict[str,list[str]] = {k:[] for k in PERSONA_KEYWORDS}
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
SUMMARY_KEYWORDS = [r"özetle", r"kısaca", r"tl;dr", r"summarize", r"summary", r"brief", r"short version"]
COMPARISON_KEYWORDS = [r"karşılaştır", r"vs", r"hangisi", r"compare", r"versus", r"farkları"]
VARIANT_KEYWORDS = [r"alternatif", r"alternatifler", r"alternatives", r"variants", r"seçenek", r"options"]

def detect_summary(text: str) -> tuple[bool, int|None]:
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
            cand = [p.strip() for p in parts if p and p.strip() and p not in {"ve","ile",",","/","&","|"}]
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
    'financial': [r"yatırım", r"hisse", r"borsa", r"stock", r"invest", r"trading", r"kripto", r"crypto"],
    'health': [r"diyet", r"sağlık", r"hastalık", r"disease", r"treatment", r"therapy", r"nutrition"],
    'legal': [r"sözleşme", r"contract", r"legal", r"hukuk", r"sue", r"dava", r"regulation"],
}

AMBIGUOUS_TERMS = {
    'optimize': "Which metric or aspect should be optimized? (performance, cost, memory?)",
    'improve': "What specific improvement dimension matters (speed, accuracy, UX?)",
    'better': "Better in what sense (quality, efficiency, reliability?)",
    'efficient': "Which resource should be minimized (time, memory, cost?)",
    'scalable': "Target scale or concurrency level?",
    'fast': "What response time / throughput target?",
    'robust': "Robust against which failures or edge cases?",
}

CODE_REQUEST_KEYWORDS = [r"code", r"function", r"snippet", r"implement", r"class", r"python", r"örnek kod", r"kod"]

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
    if length > 40: score += 1
    if unique > 30: score += 1
    if any(k in text.lower() for k in [" vs ", "compare", "karşılaştır"]): score += 1
    if any(k in text.lower() for k in ["teach", "öğret", "explain"]): score += 1
    return 'high' if score >= 3 else 'medium' if score == 2 else 'low'

def detect_ambiguous_terms(text: str) -> list[str]:
    lower = text.lower()
    found = []
    for term in AMBIGUOUS_TERMS:
        if term in lower:
            found.append(term)
    return found

def generate_clarify_questions(terms: list[str]) -> list[str]:
    qs: list[str] = []
    for t in terms:
        hint = AMBIGUOUS_TERMS.get(t)
        if hint and hint not in qs:
            qs.append(hint)
        if len(qs) >= 5:
            break
    return qs

def detect_code_request(text: str) -> bool:
    lower = text.lower()
    return any(re.search(p, lower) for p in CODE_REQUEST_KEYWORDS)

def detect_language(text: str) -> str:
    # Simple heuristic: presence of Turkish specific chars or common words
    tr_chars = "çğıöşü"
    if any(c in text.lower() for c in tr_chars) or re.search(r"\bve\b|\bile\b|\bkimdir\b", text.lower()):
        return "tr"
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
        d = ev.split(":",1)[0]
        counts[d] = counts.get(d,0)+1
    domain = sorted(counts.items(), key=lambda x: (-x[1], x[0]))[0][0]
    return domain, evidence


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
        sports = ["futbol","football","soccer","basketbol","basketball","tenis","tennis"]
        for s in sports:
            if re.search(rf"\b{s}\b", lower):
                inputs.setdefault("interest", s)
                break

    # Budget extraction (after duration to avoid capturing "10 dakikada" as money)
    budget_keywords = ["bütçe", "budget", "en fazla", "üst limit", "max", "limit", "under", "below"]
    money_pattern = re.compile(r"(₺|\$|€)?\s*([0-9]{1,3}(?:[.,][0-9]{3})*|[0-9]+)(?:\s*[-–]\s*(₺|\$|€)?\s*([0-9]{1,3}(?:[.,][0-9]{3})*|[0-9]+))?\s*(tl|₺|try|lira|usd|dolar|\$|eur|€)?")
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
            if (cur1 or cur2 or cur3):
                if v2:
                    inputs["budget_hint"] = f"{_normalize_currency(v1)}-{_normalize_currency(v2)} {unit}".strip()
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
