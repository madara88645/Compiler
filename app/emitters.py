from __future__ import annotations
from typing import List
import os
from .models import IR
from .models_v2 import IRv2, ConstraintV2, StepV2


def emit_system_prompt(ir: IR) -> str:
    parts = [
        f"Persona: {ir.persona}",
        f"Role: {ir.role}",
        "Rules:",
        "- Follow goals, tasks, constraints, and style/tone.",
        f"- Output format: {ir.output_format}; length: {ir.length_hint}.",
    ]
    if ir.persona == "developer":
        parts.append(
            "- Prefer code-first, minimal narration; annotate only where clarity improves."
        )
        parts.append(
            "- When debugging: focus on reproduction, error analysis, and iterative fixes."
        )
    if ir.style:
        parts.append("Style: " + ", ".join(ir.style))
    if ir.tone:
        parts.append("Tone: " + ", ".join(ir.tone))
    if ir.banned:
        parts.append("Avoid: " + ", ".join(ir.banned))
    return "\n".join(parts)


def emit_user_prompt(ir: IR) -> str:
    lines = []
    if ir.goals:
        lines.append("Goals:")
        for g in ir.goals:
            lines.append(f"- {g}")
    if ir.tasks:
        lines.append("Tasks:")
        for t in ir.tasks:
            lines.append(f"- {t}")
    if ir.inputs:
        lines.append("Inputs:")
        for k, v in ir.inputs.items():
            lines.append(f"- {k}: {v}")
    if ir.examples:
        lines.append("Examples:")
        for ex in ir.examples:
            lines.append(f"---\n{ex}\n---")
    return "\n".join(lines)


def emit_plan(ir: IR) -> str:
    out = []
    for i, step in enumerate(ir.steps or ir.tasks, start=1):
        rationale = "Rationale: execute task effectively"
        out.append(f"{i}. {step}\n   {rationale}")
    return "\n".join(out) if out else "1. Analyze request\n   Rationale: establish understanding"


def _is_conservative_mode(conservative: bool | None) -> bool:
    if conservative is not None:
        return bool(conservative)
    mode = (os.environ.get("PROMPT_COMPILER_MODE") or "conservative").strip().lower()
    return mode != "default"


def _is_trivial_input(original_text: str, domain: str, complexity: str) -> bool:
    """Return True for very short or greeting-only inputs that should not be expanded with generic boilerplate."""
    stripped = original_text.strip()
    if len(stripped) < 30 and domain == "general" and complexity in ("low", None, ""):
        return True
    return False


def _minimal_greeting_prompt(original_text: str, lang: str) -> str:
    """Return a minimal, sensible prompt for greeting/very-short inputs instead of boilerplate."""
    orig = original_text.strip()
    if lang == "tr":
        return f"{orig.capitalize()}\n\nNasil yardimci olabilirim?"
    return f"{orig.capitalize()}\n\nHow can I help you?"


def emit_expanded_prompt(
    ir: IR, diagnostics: bool = False, conservative: bool | None = None
) -> str:
    # Natural, example-based one-shot style expansion for everyday users
    conservative_on = _is_conservative_mode(conservative)
    lang = ir.language

    # Short/greeting inputs: skip the generic suggestions template entirely
    orig_text = (ir.metadata or {}).get("original_text") or ""
    complexity = (ir.metadata or {}).get("complexity") or ""
    if conservative_on and _is_trivial_input(orig_text, ir.domain, complexity):
        return _minimal_greeting_prompt(orig_text, lang)

    title = (
        "Genişletilmiş İstem"
        if lang == "tr"
        else ("Instrucción Ampliada" if lang == "es" else "Expanded Prompt")
    )
    intro = (
        "Aşağıdaki bağlama göre net ve eyleme dönük öneriler üret."
        if lang == "tr"
        else (
            "Genera sugerencias claras y accionables según el contexto."
            if lang == "es"
            else "Generate clear, actionable suggestions based on the context below."
        )
    )
    ctx_lines = []
    if ir.goals:
        ctx_lines.append(
            ("Amaçlar" if lang == "tr" else ("Objetivos" if lang == "es" else "Goals"))
            + ": "
            + " | ".join(ir.goals[:3])
        )
    # Persona context first for visibility
    ctx_lines.insert(0, ("Persona" if lang != "tr" else "Persona") + ": " + ir.persona)
    if ir.tasks:
        ctx_lines.append(
            ("Görevler" if lang == "tr" else ("Tareas" if lang == "es" else "Tasks"))
            + ": "
            + " | ".join(ir.tasks[:3])
        )
    if ir.constraints:
        ctx_lines.append(
            ("Kısıtlar" if lang == "tr" else ("Restricciones" if lang == "es" else "Constraints"))
            + ": "
            + " | ".join(ir.constraints[:3])
        )
    if ir.inputs:
        kv = [f"{k}={v}" for k, v in list(ir.inputs.items())[:4]]
        ctx_lines.append(
            (
                "Girdi ipuçları"
                if lang == "tr"
                else ("Pistas de entrada" if lang == "es" else "Input hints")
            )
            + ": "
            + ", ".join(kv)
        )
    if ir.style:
        ctx_lines.append(
            ("Stil" if lang == "tr" else ("Estilo" if lang == "es" else "Style"))
            + ": "
            + ", ".join(ir.style)
        )
    if ir.tone:
        ctx_lines.append(
            ("Ton" if lang == "tr" else ("Tono" if lang == "es" else "Tone"))
            + ": "
            + ", ".join(ir.tone)
        )
    # Example template
    example_header = (
        "Örnek çıktı formatı"
        if lang == "tr"
        else ("Ejemplo de formato de salida" if lang == "es" else "Example output format")
    )
    example_block = (
        "- Öneri 1: … (Neden: …)\n- Öneri 2: … (Neden: …)"
        if lang == "tr"
        else (
            "- Sugerencia 1: … (Por qué: …)\n- Sugerencia 2: … (Por qué: …)"
            if lang == "es"
            else "- Suggestion 1: … (Why: …)\n- Suggestion 2: … (Why: …)"
        )
    )
    fmt_line = (
        f"Biçim: {ir.output_format}, Uzunluk: {ir.length_hint}"
        if lang == "tr"
        else (
            f"Formato: {ir.output_format}, Longitud: {ir.length_hint}"
            if lang == "es"
            else f"Format: {ir.output_format}, Length: {ir.length_hint}"
        )
    )
    orig = (ir.metadata or {}).get("original_text") or ""
    prompt = [
        f"{title}",
        intro,
        "",
        ("Girdi" if lang == "tr" else ("Entrada" if lang == "es" else "Input")) + f": {orig}",
        "",
        ("Bağlam" if lang == "tr" else ("Contexto" if lang == "es" else "Context")) + ":",
        *ctx_lines,
        "",
        fmt_line,
        "",
        example_header + ":",
        example_block,
    ]
    # Assumptions / grounding note (conservative avoids prompting fabrication)
    meta = ir.metadata or {}
    risk_flags = meta.get("risk_flags") or []
    variant_count = meta.get("variant_count") or 0
    notes: list[str] = []
    if conservative_on:
        if lang == "tr":
            notes.append("Eksik ayrıntılar varsa uydurma yapma; netleştirici soru sor.")
        else:
            notes.append("If details are missing, do not fabricate them; ask clarifying questions.")
        if variant_count and variant_count > 1:
            notes.append(
                'Each variant begins with "Distinct Angle:" to mark a unique perspective.'
                if lang != "tr"
                else 'Her varyant benzersiz bir bakış açısı için "Distinct Angle:" satırı ile başlayacaktır.'
            )
        header_notes = "Notlar" if lang == "tr" else "Notes"
    else:
        # Legacy behavior
        if lang == "tr":
            notes.append("Eksik ayrıntılar makul örnek değerlerle doldurulacaktır.")
        else:
            notes.append("Missing details will be filled with reasonable sample values.")
        if risk_flags:
            notes.append(
                "Profesyonel tavsiye değildir; yalnızca bilgilendiricidir."
                if lang == "tr"
                else "Not professional advice; informational only."
            )
        if variant_count and variant_count > 1:
            notes.append(
                'Her varyant benzersiz bir bakış açısı için "Distinct Angle:" satırı ile başlayacaktır.'
                if lang == "tr"
                else 'Each variant begins with "Distinct Angle:" to mark a unique perspective.'
            )
        header_notes = "Varsayımlar" if lang == "tr" else "Assumptions"
    if notes:
        prompt.extend(["", f"{header_notes}:"])
        for a in notes[:5]:
            prompt.append(f"- {a}")
    # Clarification questions block (always if present) before diagnostics
    clarify_all = (ir.metadata or {}).get("clarify_questions") or []
    if clarify_all:
        prompt.extend(
            [
                "",
                ("Clarification Questions" if lang != "tr" else "Açıklama Soruları") + ":",
            ]
        )
        for q in clarify_all[:5]:
            prompt.append(f"- {q}")
    # Follow-up Questions (simple heuristic: if no clarify questions or even if present, add 2 generic next-step questions)
    followups = []
    if lang == "tr":
        followups = [
            "Ek olarak hangi başarı ölçütleri önemli?",
            "Bir sonraki yinelemede ne derinleştirilmeli?",
        ]
        header_fu = "Follow-up Soruları"
    elif lang == "es":
        followups = [
            "¿Qué métricas de éxito importan ahora?",
            "¿Qué se debe profundizar en la siguiente iteración?",
        ]
        header_fu = "Preguntas de seguimiento"
    else:
        followups = [
            "Which success metrics matter most next?",
            "What should be deepened in the next iteration?",
        ]
        header_fu = "Follow-up Questions"
    if followups:
        prompt.extend(["", header_fu + ":"])
        for f in followups[:2]:
            prompt.append(f"- {f}")

    if diagnostics:
        diag_lines = []
        risk_flags = (ir.metadata or {}).get("risk_flags") or []
        ambiguous = (ir.metadata or {}).get("ambiguous_terms") or []
        clarify = (ir.metadata or {}).get("clarify_questions") or []
        if risk_flags:
            diag_lines.append(
                (
                    "Risk Flags"
                    if lang == "en"
                    else ("Banderas de riesgo" if lang == "es" else "Risk Flags")
                )
                + ": "
                + ", ".join(risk_flags[:5])
            )
        if ambiguous:
            diag_lines.append(
                (
                    "Ambiguous Terms"
                    if lang == "en"
                    else ("Términos ambiguos" if lang == "es" else "Ambiguous Terms")
                )
                + ": "
                + ", ".join(sorted(ambiguous)[:10])
            )
        if clarify:
            diag_lines.append(
                (
                    "Clarify Questions"
                    if lang == "en"
                    else ("Preguntas de aclaración" if lang == "es" else "Clarify Questions")
                )
                + ":"
            )
            for q in clarify[:3]:
                diag_lines.append(f"- {q}")
        if diag_lines:
            prompt.extend(["", "Diagnostics:", *diag_lines])
    return "\n".join([line for line in prompt if line is not None])


# ==============================
# IR v2 Emitters (non-breaking)
# ==============================


def _top_constraints_text_v2(cons: List[ConstraintV2], limit: int = 3) -> str:
    if not cons:
        return ""
    top = sorted(cons, key=lambda c: c.priority, reverse=True)[:limit]

    def format_constraint(c: ConstraintV2) -> str:
        if c.id == "schema_enforcement":
            return "[JSON Schema Enforced]"
        return c.text

    return " | ".join(format_constraint(c) for c in top)


def emit_system_prompt_v2(ir: IRv2) -> str:
    parts: List[str] = [
        f"Persona: {ir.persona}",
        f"Role: {ir.role}",
        f"Domain: {ir.domain}",
        "Rules:",
        "- Follow goals, tasks, constraints, and style/tone.",
        f"- Output format: {ir.output_format}; length: {ir.length_hint}.",
    ]
    if ir.intents:
        parts.append("Intents: " + ", ".join(ir.intents))
    # Developer guidance parity with v1
    if ir.persona == "developer":
        parts.append(
            "- Prefer code-first, minimal narration; annotate only where clarity improves."
        )
        parts.append(
            "- When debugging: focus on reproduction, error analysis, and iterative fixes."
        )
    # Surface top constraints (by priority) succinctly
    c_line = _top_constraints_text_v2(ir.constraints, limit=3)
    if c_line:
        parts.append("Key Constraints: " + c_line)
    if ir.style:
        parts.append("Style: " + ", ".join(ir.style))
    if ir.tone:
        parts.append("Tone: " + ", ".join(ir.tone))
    if ir.banned:
        parts.append("Avoid: " + ", ".join(ir.banned))

    # --- Agent 6: The Strategist (Render Context) ---
    context_snippets = (ir.metadata or {}).get("context_snippets")
    if context_snippets:
        parts.append("\n### Context (Code & Knowledge)")
        for i, snippet in enumerate(context_snippets, 1):
            path = snippet.get("path", "unknown")
            content = snippet.get("snippet", "").strip()
            parts.append(f"#### File: {path}\n```\n{content}\n```")
    # ------------------------------------------------
    return "\n".join(parts)


def emit_user_prompt_v2(ir: IRv2) -> str:
    lines: List[str] = []
    if ir.goals:
        lines.append("Goals:")
        for g in ir.goals:
            lines.append(f"- {g}")
    if ir.tasks:
        lines.append("Tasks:")
        for t in ir.tasks:
            lines.append(f"- {t}")
    if ir.inputs:
        lines.append("Inputs:")
        for k, v in ir.inputs.items():
            lines.append(f"- {k}: {v}")
    if ir.tools:
        lines.append("Tools:")
        for tool in ir.tools:
            lines.append(f"- {tool}")
    if ir.examples:
        lines.append("Examples:")
        for ex in ir.examples:
            lines.append(f"---\n{ex}\n---")
    return "\n".join(lines)


def emit_plan_v2(ir: IRv2) -> str:
    out: List[str] = []
    steps = ir.steps if ir.steps else [StepV2(type="task", text=t) for t in ir.tasks]
    for i, step in enumerate(steps, start=1):
        rationale = "Rationale: execute task effectively"
        kind = step.type if hasattr(step, "type") else "task"
        out.append(f"{i}. [{kind}] {step.text}\n   {rationale}")
    return (
        "\n".join(out)
        if out
        else "1. [task] Analyze request\n   Rationale: establish understanding"
    )


def emit_expanded_prompt_v2(ir: IRv2, diagnostics: bool = False) -> str:
    conservative_on = _is_conservative_mode(None)
    lang = ir.language

    # Short/greeting inputs: skip the generic suggestions template entirely
    orig_text_v2 = (ir.metadata or {}).get("original_text") or ""
    complexity_v2 = (ir.metadata or {}).get("complexity") or ""
    if conservative_on and _is_trivial_input(orig_text_v2, ir.domain, complexity_v2):
        return _minimal_greeting_prompt(orig_text_v2, lang)

    title = (
        "Genişletilmiş İstem"
        if lang == "tr"
        else ("Instrucción Ampliada" if lang == "es" else "Expanded Prompt")
    )
    intro = (
        "Aşağıdaki bağlama göre net ve eyleme dönük öneriler üret."
        if lang == "tr"
        else (
            "Genera sugerencias claras y accionables según el contexto."
            if lang == "es"
            else "Generate clear, actionable suggestions based on the context below."
        )
    )
    ctx_lines: List[str] = []
    # Persona & intents first
    ctx_lines.append((("Persona" if lang != "tr" else "Persona") + ": " + ir.persona))
    if ir.intents:
        ctx_lines.append(
            (("Intents" if lang != "tr" else "Niyetler") + ": " + ", ".join(ir.intents))
        )
    if ir.goals:
        ctx_lines.append(
            ("Amaçlar" if lang == "tr" else ("Objetivos" if lang == "es" else "Goals"))
            + ": "
            + " | ".join(ir.goals[:3])
        )
    if ir.tasks:
        ctx_lines.append(
            ("Görevler" if lang == "tr" else ("Tareas" if lang == "es" else "Tasks"))
            + ": "
            + " | ".join(ir.tasks[:3])
        )
    # Top constraints (v2)
    c_line = _top_constraints_text_v2(ir.constraints, limit=3)
    if c_line:
        ctx_lines.append(
            ("Kısıtlar" if lang == "tr" else ("Restricciones" if lang == "es" else "Constraints"))
            + ": "
            + c_line
        )
    if ir.inputs:
        kv = [f"{k}={v}" for k, v in list(ir.inputs.items())[:4]]
        ctx_lines.append(
            (
                "Girdi ipuçları"
                if lang == "tr"
                else ("Pistas de entrada" if lang == "es" else "Input hints")
            )
            + ": "
            + ", ".join(kv)
        )
    if ir.style:
        ctx_lines.append(
            ("Stil" if lang == "tr" else ("Estilo" if lang == "es" else "Style"))
            + ": "
            + ", ".join(ir.style)
        )
    if ir.tone:
        ctx_lines.append(
            ("Ton" if lang == "tr" else ("Tono" if lang == "es" else "Tone"))
            + ": "
            + ", ".join(ir.tone)
        )

    # --- Agent 6: Context Injection ---
    context_snippets = (ir.metadata or {}).get("context_snippets")
    if context_snippets:
        header = (
            "Bağlam (Kod ve Bilgi)"
            if lang == "tr"
            else (
                "Contexto (Código y Conocimiento)" if lang == "es" else "Context (Code & Knowledge)"
            )
        )
        ctx_lines.append(f"{header}:")
        for s in context_snippets:
            path = s.get("path", "unknown").split("/")[-1]  # Short filename
            content = s.get("snippet", "").strip().replace("\n", " ")  # Flatten for compactness
            # Truncate if too long to avoid bloating the prompt
            if len(content) > 300:
                content = content[:300] + "..."
            ctx_lines.append(f"- {path}: {content}")
    # ----------------------------------

    fmt_line = (
        f"Biçim: {ir.output_format}, Uzunluk: {ir.length_hint}"
        if lang == "tr"
        else (
            f"Formato: {ir.output_format}, Longitud: {ir.length_hint}"
            if lang == "es"
            else f"Format: {ir.output_format}, Length: {ir.length_hint}"
        )
    )
    orig = (ir.metadata or {}).get("original_text") or ""
    prompt: List[str] = [
        f"{title}",
        intro,
        "",
        ("Girdi" if lang == "tr" else ("Entrada" if lang == "es" else "Input")) + f": {orig}",
        "",
        ("Bağlam" if lang == "tr" else ("Contexto" if lang == "es" else "Context")) + ":",
        *ctx_lines,
        "",
        fmt_line,
    ]
    # Follow-up Questions (same approach as v1)
    followups: List[str] = []
    if lang == "tr":
        followups = [
            "Ek olarak hangi başarı ölçütleri önemli?",
            "Bir sonraki yinelemede ne derinleştirilmeli?",
        ]
        header_fu = "Follow-up Soruları"
    elif lang == "es":
        followups = [
            "¿Qué métricas de éxito importan ahora?",
            "¿Qué se debe profundizar en la siguiente iteración?",
        ]
        header_fu = "Preguntas de seguimiento"
    else:
        followups = [
            "Which success metrics matter most next?",
            "What should be deepened in the next iteration?",
        ]
        header_fu = "Follow-up Questions"
    if followups:
        prompt.extend(["", header_fu + ":"])
        for f in followups[:2]:
            prompt.append(f"- {f}")

    if diagnostics:
        diag_lines: List[str] = []
        md = ir.metadata or {}

        # 1. Render Structured Diagnostics (V2)
        if ir.diagnostics:
            for d in ir.diagnostics:
                icon = "ℹ️"
                if d.severity == "warning":
                    icon = "⚠️"
                elif d.severity == "error" or d.category == "security":
                    icon = "🚨"

                msg = f"{icon} {d.message}"
                if d.suggestion:
                    msg += f" → {d.suggestion}"
                diag_lines.append(msg)

        # 2. Render Legacy Metadata (V1 compatibility)
        risk_flags = md.get("risk_flags") or []
        ambiguous = md.get("ambiguous_terms") or []
        clarify = md.get("clarify_questions") or []

        if risk_flags:
            diag_lines.append(
                (
                    "Risk Flags"
                    if lang == "en"
                    else ("Banderas de riesgo" if lang == "es" else "Risk Flags")
                )
                + ": "
                + ", ".join(risk_flags[:5])
            )
        if ambiguous:
            # Only show if not already covered by V2 diagnostics (simple dedup check could be added, but listing both is safer for now)
            diag_lines.append(
                (
                    "Ambiguous Terms"
                    if lang == "en"
                    else ("Términos ambiguos" if lang == "es" else "Ambiguous Terms")
                )
                + ": "
                + ", ".join(sorted(ambiguous)[:10])
            )
        if clarify:
            diag_lines.append(
                (
                    "Clarify Questions"
                    if lang == "en"
                    else ("Preguntas de aclaración" if lang == "es" else "Clarify Questions")
                )
                + ":"
            )
            for q in clarify[:3]:
                diag_lines.append(f"- {q}")

        if diag_lines:
            prompt.extend(["", "Diagnostics:", *diag_lines])

    # --- Domain-Specific Best Practices ---
    if conservative_on:
        # Keep this section minimal to avoid injecting new requirements.
        bp_header = "İpuçları" if lang == "tr" else ("Consejos" if lang == "es" else "Tips")
        tips = (
            [
                "Sadece kullanıcının istediğini yap; yeni gereksinim ekleme.",
                "Eksik bilgi varsa uydurma yapma; kısa netleştirici sorular sor.",
            ]
            if lang == "tr"
            else (
                [
                    "Stay within what the user asked; do not add new requirements.",
                    "If information is missing, ask short clarifying questions instead of guessing.",
                ]
            )
        )
        prompt.extend(["", f"{bp_header}:"])
        for t in tips[:3]:
            prompt.append(f"- {t}")
        return "\n".join(prompt)

    _BEST_PRACTICES_EN: dict = {
        "coding": [
            "Write defensive code and handle edge cases explicitly.",
            "Include unit tests or testable code structure.",
            "Use type hints and meaningful variable names.",
        ],
        "software": [
            "Write defensive code and handle edge cases explicitly.",
            "Include unit tests or testable code structure.",
            "Use type hints and meaningful variable names.",
        ],
        "finance": [
            "Ensure numerical precision (use Decimal, not float for money).",
            "Include a legal/liability disclaimer in any output.",
            "Validate all financial inputs and flag outliers.",
        ],
        "security": [
            "Apply the least-privilege principle throughout.",
            "Validate and sanitize all inputs before processing.",
            "Log audit events for every sensitive action.",
        ],
        "ai/nlp": [
            "Cite sources or flag statements that may be speculative.",
            "Acknowledge model limitations and potential hallucination risks.",
            "Avoid over-confident language; use hedging where appropriate.",
        ],
        "education": [
            "Adapt the explanation depth to the learner's stated level.",
            "Include at least one practical exercise or example.",
            "Encourage questions and confirm understanding at each step.",
        ],
        "health": [
            "Always recommend consulting a qualified healthcare professional.",
            "Avoid definitive diagnoses; present information as general guidance.",
            "Cite reputable sources (WHO, NHS, peer-reviewed literature).",
        ],
        "legal": [
            "Clarify this is not professional legal advice.",
            "Refer to jurisdiction-specific rules where relevant.",
            "Use precise language and avoid ambiguous legal terms.",
        ],
        "cloud": [
            "Prefer infrastructure-as-code over manual configuration.",
            "Document estimated resource costs and scaling limits.",
            "Plan for failure: include retry logic and circuit breakers.",
        ],
        "mlops": [
            "Document model versioning and reproducibility steps.",
            "Define monitoring metrics and alert thresholds.",
            "Include a rollback plan for model deployments.",
        ],
    }
    _BEST_PRACTICES_TR: dict = {
        "coding": [
            "Savunmacı kod yaz ve kenar durumları açıkça işle.",
            "Birim testleri veya test edilebilir kod yapısı ekle.",
            "Tür ipuçları ve anlamlı değişken adları kullan.",
        ],
        "software": [
            "Savunmacı kod yaz ve kenar durumları açıkça işle.",
            "Birim testleri veya test edilebilir kod yapısı ekle.",
            "Tür ipuçları ve anlamlı değişken adları kullan.",
        ],
        "finance": [
            "Sayısal hassasiyeti sağla (para için float değil Decimal kullan).",
            "Çıktılara yasal sorumluluk reddi ekle.",
            "Tüm finansal girdileri doğrula ve aykırı değerleri işaretle.",
        ],
        "security": [
            "En az ayrıcalık ilkesini uygula.",
            "Tüm girdileri işlemeden önce doğrula ve temizle.",
            "Her hassas işlem için denetim olaylarını kaydet.",
        ],
        "ai/nlp": [
            "Spekülatif ifadeleri kaynakla destekle veya işaretle.",
            "Model sınırlılıklarını ve halüsinasyon risklerini kabul et.",
            "Aşırı güvenli dilden kaçın; gerektiğinde çekinceli ifade kullan.",
        ],
        "education": [
            "Açıklama derinliğini öğrencinin seviyesine göre ayarla.",
            "En az bir pratik alıştırma veya örnek ekle.",
            "Her adımda soruları teşvik et ve anlamayı doğrula.",
        ],
        "health": [
            "Her zaman nitelikli bir sağlık profesyoneline danışılmasını tavsiye et.",
            "Kesin tanıdan kaçın; bilgiyi genel rehberlik olarak sun.",
            "Güvenilir kaynakları (WHO, TÜBİTAK, hakemli literatür) kaynak göster.",
        ],
        "legal": [
            "Bu bilginin profesyonel hukuki tavsiye olmadığını belirt.",
            "İlgili yargı yetki alanına özgü kurallara atıfta bulun.",
            "Kesin dil kullan ve belirsiz hukuki terimlerden kaçın.",
        ],
        "cloud": [
            "Manuel yapılandırma yerine kod olarak altyapıyı tercih et.",
            "Tahmini kaynak maliyetlerini ve ölçekleme sınırlarını belgele.",
            "Hata için plan yap: yeniden deneme mantığı ve devre kesiciler ekle.",
        ],
        "mlops": [
            "Model sürümleme ve yeniden üretilebilirlik adımlarını belgele.",
            "İzleme metriklerini ve uyarı eşiklerini tanımla.",
            "Model dağıtımları için geri alma planı ekle.",
        ],
    }
    domain_key_bp = (ir.domain or "").lower().split("/")[0].strip()
    bp_map = _BEST_PRACTICES_TR if lang == "tr" else _BEST_PRACTICES_EN
    best_practices = bp_map.get(domain_key_bp) or bp_map.get(ir.domain or "")
    if not best_practices:
        # Generic professional standards fallback
        if lang == "tr":
            best_practices = [
                "Net ve öz ol; belirsizlikten kaçın.",
                "Önemli kararlar için gerekçe sun.",
                "Çıktının ölçülebilir ya da doğrulanabilir olduğundan emin ol.",
            ]
        else:
            best_practices = [
                "Be clear and concise; avoid ambiguity.",
                "Provide rationale for important decisions.",
                "Ensure the output is measurable or verifiable.",
            ]
    bp_header = (
        "En İyi Uygulamalar"
        if lang == "tr"
        else ("Mejores prácticas" if lang == "es" else "Best Practices")
    )
    prompt.extend(["", f"{bp_header}:"])
    for bp in best_practices:
        prompt.append(f"- {bp}")

    # --- Chain-of-Thought Scaffold ---
    if lang == "tr":
        cot_header = "Yanıtlamadan Önce"
        cot_steps = [
            "Hedefi kendi cümlelerinle yeniden ifade et.",
            "Yaptığın varsayımları listele.",
            "Belirsizlikleri tespit et ve yanıt vermeden önce işaretle.",
        ]
    elif lang == "es":
        cot_header = "Antes de responder"
        cot_steps = [
            "Reformula el objetivo con tus propias palabras.",
            "Lista los supuestos que estás haciendo.",
            "Identifica ambigüedades y señálalas antes de continuar.",
        ]
    else:
        cot_header = "Before Responding"
        cot_steps = [
            "Restate the goal in your own words.",
            "List the assumptions you are making.",
            "Flag any ambiguities before proceeding.",
        ]
    prompt.extend(["", f"{cot_header}:"])
    for i, step in enumerate(cot_steps, 1):
        prompt.append(f"{i}. {step}")

    return "\n".join(prompt)
