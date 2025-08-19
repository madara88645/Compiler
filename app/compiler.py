from __future__ import annotations
import re
from typing import List
from .models import IR, DEFAULT_ROLE_TR, DEFAULT_ROLE_EN
import json, hashlib, time
from .heuristics import (
    detect_language, detect_domain, detect_recency, extract_format,
    detect_length_hint, extract_style_tone, detect_conflicts, extract_inputs,
    detect_teaching_intent, detect_summary, extract_comparison_items, extract_variant_count, pick_persona,
    detect_risk_flags, extract_entities, estimate_complexity, detect_ambiguous_terms, generate_clarify_questions,
    detect_code_request
)

GENERIC_GOAL = {
    'tr': 'İsteği yerine getir ve faydalı, doğru bir cevap üret.',
    'en': 'Satisfy the request and produce a helpful, correct answer.'
}
GENERIC_TASK = {
    'tr': 'İsteği analiz et ve yanıtla.',
    'en': 'Analyze the request and respond.'
}
RECENCY_CONSTRAINT_TR = 'Güncel bilgi gerektirir; cevap üretmeden önce web araştırması yap.'
RECENCY_CONSTRAINT_EN = 'Requires up-to-date info; perform web research before answering.'


def split_sentences(text: str) -> List[str]:
    parts = re.split(r'[\n;.]+', text)
    return [p.strip() for p in parts if p.strip()]


from typing import Tuple

def extract_goals_tasks(text: str, lang: str) -> Tuple[List[str], List[str]]:
    sentences = split_sentences(text)
    goals: List[str] = []
    tasks: List[str] = []
    for s in sentences:
        if len(s.split()) < 2:
            continue
        if len(goals) < 3:
            goals.append(s)
        if len(tasks) < 5:
            tasks.append(s)
    if not goals:
        goals = [GENERIC_GOAL[lang]]
    if not tasks:
        tasks = [GENERIC_TASK[lang]]
    return goals, tasks


def build_steps(tasks: List[str]) -> List[str]:
    steps: List[str] = []
    for t in tasks:
        if len(steps) >= 8:
            break
        # Simple transformation
        steps.append(f"Review: {t[:80]}")
    return steps


HEURISTIC_VERSION = "2025.08.19-1"

def _canonical_constraints(items: list[str]) -> list[str]:
    seen = set()
    out: list[str] = []
    for c in items:
        key = c.strip().lower()
        if not key:
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(c.strip())
    return out

def _compute_signature(ir: IR) -> str:
    # Deterministic short hash of IR core fields (exclude metadata.ir_signature itself)
    core = ir.dict()
    md = core.get('metadata', {}).copy()
    md.pop('ir_signature', None)
    core['metadata'] = md
    blob = json.dumps(core, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode('utf-8')).hexdigest()[:12]

def compile_text(text: str) -> IR:
    lang = detect_language(text)
    domain, evidence = detect_domain(text)
    output_format = extract_format(text)
    length_hint = detect_length_hint(text)
    style, tone = extract_style_tone(text)
    inputs = extract_inputs(text, lang)
    # If user explicitly hinted a format, prefer it over general detection
    if inputs.get('format'):
        output_format = inputs['format']
    goals, tasks = extract_goals_tasks(text, lang)
    steps = build_steps(tasks)
    constraints: List[str] = []
    if length_hint == 'short':
        constraints.append('Keep it concise')
    elif length_hint == 'long':
        constraints.append('Provide comprehensive detail')

    # Banned placeholder (empty unless found later)
    banned: List[str] = []

    tools: List[str] = []
    if detect_recency(text):
        tools.append('web')
        constraints.append(RECENCY_CONSTRAINT_TR if lang=='tr' else RECENCY_CONSTRAINT_EN)

    # General task enhancements (stored in metadata to avoid schema changes)
    is_summary, summary_count = detect_summary(text)
    comparison_items = extract_comparison_items(text)
    variant_count = extract_variant_count(text)
    risk_flags = detect_risk_flags(text)
    entities = extract_entities(text)
    complexity = estimate_complexity(text)
    ambiguous = detect_ambiguous_terms(text)
    clarify_qs = generate_clarify_questions(ambiguous)
    code_req = detect_code_request(text)
    if is_summary:
        constraints.append('Provide a concise summary')
        if summary_count:
            constraints.append(f'Max {summary_count} bullet points')
        output_format = output_format or 'markdown'
    if comparison_items and len(comparison_items) >= 2:
        constraints.append('Present a structured comparison')
        if output_format == 'markdown':
            output_format = 'table'
    if variant_count > 1:
        constraints.append(f'Generate {variant_count} distinct variants')
    if risk_flags:
        if lang == 'tr':
            constraints.append('Riskli alan: profesyonel tavsiye yerine genel bilgi ver (finans/tıp/hukuk)')
        else:
            constraints.append('Risk domain detected: provide general information, not professional advice')
    if code_req:
        if lang == 'tr':
            constraints.append('Kod örneklerinde kısa yorum satırları ekle')
        else:
            constraints.append('Include brief inline comments in code examples')
    if ambiguous:
        if lang == 'tr':
            constraints.append('Belirsiz terimleri netleştir: ' + ", ".join(sorted(ambiguous)))
        else:
            constraints.append('Clarify ambiguous terms: ' + ", ".join(sorted(ambiguous)))

    # Include original text in conflict detection so opposing adjectives inside prompt are caught.
    conflicts = detect_conflicts(constraints + [text])

    # Persona selection (base)
    persona, persona_info = pick_persona(text)
    role = DEFAULT_ROLE_TR if lang=='tr' else DEFAULT_ROLE_EN

    ir = IR(
        language=lang,
        persona=persona,
        role=role,
        domain=domain,
        goals=goals,
        tasks=tasks,
    inputs=inputs,
        constraints=constraints,
        style=style,
        tone=tone,
        output_format=output_format,
        length_hint=length_hint,
        steps=steps,
        examples=[],
        banned=banned,
        tools=tools,
        metadata={
            'conflicts': conflicts,
            'detected_domain_evidence': evidence,
            'notes': [],
            'summary': str(is_summary).lower(),
            'summary_limit': summary_count if summary_count else None,
            'comparison_items': comparison_items,
            'variant_count': variant_count,
            'original_text': text,
            'persona_evidence': persona_info,
            'risk_flags': risk_flags,
            'entities': entities,
            'complexity': complexity,
            'ambiguous_terms': ambiguous,
            'clarify_questions': clarify_qs,
            'code_request': code_req,
            'heuristic_version': HEURISTIC_VERSION
        }
    )
    # Teaching intent enrichment
    if detect_teaching_intent(text):
        persona = 'teacher'
        ir.persona = persona
        # Language-specific teaching persona
        if lang == 'tr':
            ir.role = "bilgili ve öğretici bir profesör uzman"
        else:
            ir.role = "a knowledgeable and instructive professor expert"
        lvl = (inputs.get('level') or '').lower()
        dur = inputs.get('duration')  # e.g., 10m, 1h
        if lang == 'tr':
            ir.constraints.append("Aşamalı, kavramdan örneğe doğru öğretici anlatım kullan")
            ir.constraints.append("Öğrenme konularında analoji kullan")
            ir.constraints.append("İlgili güvenilir kaynak önerileri ekle")
            if lvl == 'beginner':
                ir.constraints.append("Sıfırdan başlayanlar için basit dil kullan")
            elif lvl == 'intermediate':
                ir.constraints.append("Orta seviye için yeterli ayrıntı ekle")
            elif lvl == 'advanced':
                ir.constraints.append("İleri seviye için derin teknik içerik ekle")
            if dur:
                ir.constraints.append(f"Süre hedefi: {dur} içinde bitecek kapsam")
            ir.style.append("structured")
            ir.tone.append("friendly")
            base_steps = [
                "Temel kavramları sade dille tanıt",
                "Örneklerle göster",
                "Kısa bir egzersiz öner",
                "Özetle ve kaynakları listele"
            ]
            if lvl == 'advanced':
                base_steps.insert(2, "Kısa bir derinlemesine bölüm ekle")
            ir.steps = base_steps
            # Mini quiz template in examples
            ir.examples = ir.examples or [
                "Örn: Giriş -> Örnek -> Alıştırma -> Özet",
                "Mini Quiz: 3 soru (1 kolay, 1 orta, 1 zor) ve kısa cevap anahtarı"
            ]
        else:
            ir.constraints.append("Use a progressive, pedagogical flow from concepts to examples")
            ir.constraints.append("Use analogies to make concepts clearer")
            ir.constraints.append("Include relevant reputable source recommendations")
            if lvl == 'beginner':
                ir.constraints.append("Use simple language for beginners")
            elif lvl == 'intermediate':
                ir.constraints.append("Provide sufficient detail for intermediate level")
            elif lvl == 'advanced':
                ir.constraints.append("Include deep technical content for advanced learners")
            if dur:
                ir.constraints.append(f"Time-bound: target completion within {dur}")
            ir.style.append("structured")
            ir.tone.append("friendly")
            base_steps = [
                "Introduce core concepts simply",
                "Demonstrate with examples",
                "Propose a short exercise",
                "Summarize and list resources"
            ]
            if lvl == 'advanced':
                base_steps.insert(2, "Add a brief deep-dive section")
            ir.steps = base_steps
            ir.examples = ir.examples or [
                "Ex: Intro -> Example -> Exercise -> Summary",
                "Mini Quiz: 3 questions (easy, medium, hard) with short answer key"
            ]
    # Final constraint normalization
    ir.constraints = _canonical_constraints(ir.constraints)
    # Attach signature
    ir.metadata['ir_signature'] = _compute_signature(ir)
    return ir

def generate_trace(ir: IR) -> list[str]:
    """Produce a human-readable trace of heuristic triggers for debugging.

    Only uses existing IR + metadata (no recomputation) so it's deterministic.
    """
    md = ir.metadata or {}
    lines: list[str] = []
    def add(k: str, v):
        lines.append(f"{k}={v}")
    add("heuristic_version", md.get('heuristic_version'))
    add("language", ir.language)
    add("persona", ir.persona)
    # Domain evidence
    ev = md.get('detected_domain_evidence') or []
    add("domain", f"{ir.domain} ({len(ev)} evid)" if ev else ir.domain)
    if ev:
        lines.append("domain_evidence:" + ",".join(ev[:8]))
    add("summary", md.get('summary'))
    limit = md.get('summary_limit')
    if limit:
        add("summary_limit", limit)
    comp_items = md.get('comparison_items') or []
    if comp_items:
        add("comparison_items", len(comp_items))
    add("variant_count", md.get('variant_count'))
    if ir.tools:
        add("tools", ",".join(ir.tools))
    risk = md.get('risk_flags') or []
    if risk:
        add("risk_flags", ",".join(risk))
    amb = md.get('ambiguous_terms') or []
    if amb:
        add("ambiguous_terms", ",".join(sorted(amb)))
    clar = md.get('clarify_questions') or []
    if clar:
        add("clarify_q_count", len(clar))
    if md.get('code_request'):
        add("code_request", True)
    ents = md.get('entities') or []
    if ents:
        add("entities", ",".join(ents[:6]))
    add("complexity", md.get('complexity'))
    # Persona scores
    pe = md.get('persona_evidence', {})
    scores = pe.get('scores') or {}
    if scores:
        score_line = ",".join(f"{k}:{v}" for k,v in sorted(scores.items()))
        add("persona_scores", score_line)
    add("ir_signature", md.get('ir_signature'))
    return lines


def optimize_ir(ir: IR) -> IR:
    # Placeholder for future optimization passes: could merge similar tasks, etc.
    return ir
