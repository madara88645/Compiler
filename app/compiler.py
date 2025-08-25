from __future__ import annotations
import re
from typing import List
from .models import IR, DEFAULT_ROLE_TR, DEFAULT_ROLE_EN
from .models_v2 import IRv2, ConstraintV2, StepV2
from app import get_version
import json, hashlib, time
from .heuristics import (
    detect_language, detect_domain, detect_recency, extract_format,
    detect_length_hint, extract_style_tone, detect_conflicts, extract_inputs,
    detect_teaching_intent, detect_summary, extract_comparison_items, extract_variant_count, pick_persona,
    detect_risk_flags, extract_entities, estimate_complexity, detect_ambiguous_terms, generate_clarify_questions,
    detect_code_request, detect_pii, detect_domain_candidates, extract_temporal_flags, extract_quantities,
    generate_clarify_questions_struct
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
        # naive split: each task maybe broken into sub points (not implemented yet)
        steps.append(t)
    return steps

HEURISTIC_VERSION = "2025.08.21-1"
HEURISTIC2_VERSION = "2025.08.23-0"

def _canonical_constraints(items: List[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for c in items:
        c2 = c.strip()
        if not c2:
            continue
        low = c2.lower()
        if low in seen:
            continue
        seen.add(low)
        out.append(c2)
    return out

def _compute_signature(ir: IR) -> str:
    data = json.dumps({
        'goals': ir.goals,
        'tasks': ir.tasks,
        'constraints': ir.constraints,
        'domain': ir.domain,
        'persona': ir.persona,
        'language': ir.language,
        'heur_ver': ir.metadata.get('heuristic_version') if ir.metadata else None
    }, sort_keys=True)
    return hashlib.sha256(data.encode('utf-8')).hexdigest()[:16]

def _mk_id(text: str) -> str:
    return hashlib.sha1(text.strip().lower().encode('utf-8')).hexdigest()[:10]

def compile_text_v2(text: str) -> IRv2:
    # Reuse v1 heuristics to keep behavior; map to richer IRv2 model
    ir1 = compile_text(text)
    intents: list[str] = []
    md = ir1.metadata or {}
    if md.get('summary') == 'true': intents.append('summary')
    if md.get('comparison_items'): intents.append('compare')
    if md.get('variant_count', 1) > 1: intents.append('variants')
    if md.get('risk_flags'): intents.append('risk')
    if md.get('code_request'): intents.append('code')
    if md.get('ambiguous_terms'): intents.append('ambiguous')
    if 'web' in (ir1.tools or []): intents.append('recency')
    if ir1.persona == 'teacher': intents.append('teaching')

    # Prioritize constraints by origin
    origins = md.get('constraint_origins') or {}
    prio_map = {
        'recency': 80,
        'risk_flags': 70,
        'teaching_duration': 65,
        'teaching_level': 60,
        'teaching': 60,
        'comparison': 50,
        'variants': 50,
        'summary': 40,
        'summary_limit': 40,
        'ambiguous_terms': 30,
        'code_request': 30,
    }
    c_v2: list[ConstraintV2] = []
    for c in ir1.constraints:
        origin = origins.get(c, '')
        pr = prio_map.get(origin, 40)
        c_v2.append(ConstraintV2(id=_mk_id(c), text=c, origin=origin or 'unknown', priority=pr))

    # Typed steps: keep as 'task' for now
    steps_v2: list[StepV2] = [StepV2(type='task', text=s) for s in (ir1.steps or [])]

    ir2 = IRv2(
        language=ir1.language,
        persona=ir1.persona, role=ir1.role, domain=ir1.domain,
        intents=intents,
        goals=ir1.goals, tasks=ir1.tasks, inputs=ir1.inputs,
        constraints=c_v2, style=ir1.style, tone=ir1.tone,
        output_format=ir1.output_format, length_hint=ir1.length_hint,
        steps=steps_v2, examples=ir1.examples, banned=ir1.banned, tools=ir1.tools,
        metadata={
            **(ir1.metadata or {}),
            'heuristic2_version': HEURISTIC2_VERSION,
            'ir_version': '2.0',
            'package_version': get_version()
        }
    )
    return ir2

def compile_text(text: str) -> IR:
    lang = detect_language(text)
    domain, evidence = detect_domain(text)
    goals, tasks = extract_goals_tasks(text, lang)
    length_hint = detect_length_hint(text)
    style, tone = extract_style_tone(text)
    output_format = extract_format(text)
    inputs = extract_inputs(text, lang)
    if inputs.get('format'):
        output_format = inputs['format']
    steps = build_steps(tasks)

    constraints: List[str] = []
    constraint_origins: dict[str,str] = {}
    def add_constraint(val: str, origin: str):
        v = val.strip()
        if not v:
            return
        constraints.append(v)
        if v not in constraint_origins:
            constraint_origins[v] = origin

    banned: List[str] = []
    tools: List[str] = []
    if detect_recency(text):
        tools.append('web')
        add_constraint(RECENCY_CONSTRAINT_TR if lang=='tr' else RECENCY_CONSTRAINT_EN, 'recency')

    is_summary, summary_count = detect_summary(text)
    comparison_items = extract_comparison_items(text)
    variant_count = extract_variant_count(text)
    risk_flags = detect_risk_flags(text)
    ambiguous = detect_ambiguous_terms(text)
    clarify_qs = generate_clarify_questions(ambiguous)
    clarify_struct = generate_clarify_questions_struct(ambiguous)
    temporal_flags = extract_temporal_flags(text)
    quantities = extract_quantities(text)
    code_req = detect_code_request(text)
    pii_flags = detect_pii(text)
    entities = extract_entities(text)
    complexity = estimate_complexity(text)

    # Domain candidates & confidence ratio
    domain_candidates = detect_domain_candidates(evidence)
    domain_scores: dict[str,int] = {}
    if evidence:
        for ev in evidence:
            d = ev.split(':',1)[0]
            domain_scores[d] = domain_scores.get(d,0)+1
        primary_evidence = domain_scores.get(domain, 0)
        total_evidence = sum(domain_scores.values())
        domain_confidence = (primary_evidence / total_evidence) if total_evidence else None
    else:
        domain_confidence = None

    # Teaching intent enrichment BEFORE IR instantiation
    persona, persona_info = pick_persona(text)
    role = DEFAULT_ROLE_TR if lang=='tr' else DEFAULT_ROLE_EN
    if detect_teaching_intent(text):
        persona = 'teacher'
        lvl = (inputs.get('level') or '').lower()
        dur = inputs.get('duration')
        if lang == 'tr':
            role = "bilgili ve öğretici bir profesör uzman"
            add_constraint("Aşamalı, kavramdan örneğe doğru öğretici anlatım kullan", 'teaching')
            add_constraint("Öğrenme konularında analoji kullan", 'teaching')
            add_constraint("İlgili güvenilir kaynak önerileri ekle", 'teaching')
            if lvl == 'beginner':
                add_constraint("Sıfırdan başlayanlar için basit dil kullan", 'teaching_level')
            elif lvl == 'intermediate':
                add_constraint("Orta seviye için yeterli ayrıntı ekle", 'teaching_level')
            elif lvl == 'advanced':
                add_constraint("İleri seviye için derin teknik içerik ekle", 'teaching_level')
            if dur:
                add_constraint(f"Süre hedefi: {dur} içinde bitecek kapsam", 'teaching_duration')
        else:
            role = "a knowledgeable and instructive professor expert"
            add_constraint("Use a progressive, pedagogical flow from concepts to examples", 'teaching')
            add_constraint("Use analogies to make concepts clearer", 'teaching')
            add_constraint("Include relevant reputable source recommendations", 'teaching')
            if lvl == 'beginner':
                add_constraint("Use simple language for beginners", 'teaching_level')
            elif lvl == 'intermediate':
                add_constraint("Provide sufficient detail for intermediate level", 'teaching_level')
            elif lvl == 'advanced':
                add_constraint("Include deep technical content for advanced learners", 'teaching_level')
            if dur:
                add_constraint(f"Time-bound: target completion within {dur}", 'teaching_duration')
        if 'structured' not in style:
            style.append('structured')
        if 'friendly' not in tone:
            tone.append('friendly')

    if is_summary:
        add_constraint('Provide a concise summary', 'summary')
        if summary_count:
            add_constraint(f'Max {summary_count} bullet points', 'summary_limit')
        output_format = output_format or 'markdown'
    if comparison_items and len(comparison_items) >= 2:
        add_constraint('Present a structured comparison', 'comparison')
        if output_format == 'markdown':
            output_format = 'table'
    if variant_count > 1:
        add_constraint(f'Generate {variant_count} distinct variants', 'variants')
    if risk_flags:
        if lang == 'tr':
            add_constraint('Riskli alan: profesyonel tavsiye yerine genel bilgi ver (finans/tıp/hukuk)', 'risk_flags')
        else:
            add_constraint('Risk domain detected: provide general information, not professional advice', 'risk_flags')
    if pii_flags:
        if lang == 'tr':
            add_constraint('Kişisel/özel veri içerebilir: Özel bilgileri maskele ve gizliliğe dikkat et', 'pii')
        else:
            add_constraint('Possible personal/sensitive data: anonymize or mask and respect privacy', 'pii')
    if code_req:
        if lang == 'tr':
            add_constraint('Kod örneklerinde kısa yorum satırları ekle', 'code_request')
        else:
            add_constraint('Include brief inline comments in code examples', 'code_request')
    if ambiguous:
        if lang == 'tr':
            add_constraint('Belirsiz terimleri netleştir: ' + ", ".join(sorted(ambiguous)), 'ambiguous_terms')
        else:
            add_constraint('Clarify ambiguous terms: ' + ", ".join(sorted(ambiguous)), 'ambiguous_terms')

    conflicts = detect_conflicts(constraints + [text])

    ir = IR(
        language=lang,
        persona=persona,
        role=role,
        domain=domain,
        goals=goals,
        tasks=tasks,
        inputs=inputs,
        constraints=_canonical_constraints(constraints),
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
            'clarify_questions_struct': clarify_struct,
            'code_request': code_req,
            'pii_flags': pii_flags,
            'domain_candidates': domain_candidates,
            'heuristic_version': HEURISTIC_VERSION,
            'domain_scores': domain_scores,
            'domain_confidence': domain_confidence,
            'domain_score_mode': 'ratio',
            'temporal_flags': temporal_flags,
            'quantities': quantities
        }
    )

    ir.metadata['constraint_origins'] = {c: constraint_origins.get(c,'') for c in ir.constraints}
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
    # Domain confidence & scores
    if md.get('domain_confidence') is not None:
        add('domain_conf', f"{md.get('domain_confidence'):.2f}")
    dscores = md.get('domain_scores') or {}
    if dscores:
        packed = ",".join(f"{k}:{v}" for k,v in sorted(dscores.items()))
        add('domain_scores', packed)
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
    pii = md.get('pii_flags') or []
    if pii:
        add('pii_flags', ",".join(pii))
    candidates = md.get('domain_candidates') or []
    if candidates and len(candidates) > 1:
        add('domain_candidates', ",".join(candidates))
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
