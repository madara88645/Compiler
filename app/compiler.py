from __future__ import annotations
import re
from typing import List
from .models import IR, DEFAULT_ROLE_TR, DEFAULT_ROLE_EN
from .heuristics import (
    detect_language, detect_domain, detect_recency, extract_format,
    detect_length_hint, extract_style_tone, detect_conflicts, extract_inputs,
    detect_teaching_intent
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

    # Include original text in conflict detection so opposing adjectives inside prompt are caught.
    conflicts = detect_conflicts(constraints + [text])

    role = DEFAULT_ROLE_TR if lang=='tr' else DEFAULT_ROLE_EN

    ir = IR(
        language=lang,
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
            'original_text': text
        }
    )
    # Teaching intent enrichment
    if detect_teaching_intent(text):
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
    return ir


def optimize_ir(ir: IR) -> IR:
    # Placeholder for future optimization passes: could merge similar tasks, etc.
    return ir
