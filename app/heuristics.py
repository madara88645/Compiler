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
