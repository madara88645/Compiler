from __future__ import annotations
from typing import List
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


def emit_expanded_prompt(ir: IR, diagnostics: bool = False) -> str:
    # Natural, example-based one-shot style expansion for everyday users
    lang = ir.language
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
    # Assumptions block (lightweight) before clarification questions
    meta = ir.metadata or {}
    risk_flags = meta.get("risk_flags") or []
    variant_count = meta.get("variant_count") or 0
    assumptions = []
    if lang == "tr":
        assumptions.append("Eksik ayrıntılar makul örnek değerlerle doldurulacaktır.")
        if risk_flags:
            assumptions.append("Profesyonel tavsiye değildir; yalnızca bilgilendiricidir.")
        if variant_count and variant_count > 1:
            assumptions.append(
                'Her varyant benzersiz bir bakış açısı için "Distinct Angle:" satırı ile başlayacaktır.'
            )
        header_assump = "Varsayımlar" if assumptions else None
    else:
        assumptions.append("Missing details will be filled with reasonable sample values.")
        if risk_flags:
            assumptions.append("Not professional advice; informational only.")
        if variant_count and variant_count > 1:
            assumptions.append(
                'Each variant begins with "Distinct Angle:" to mark a unique perspective.'
            )
        header_assump = "Assumptions" if assumptions else None
    if assumptions:
        prompt.extend(["", f"{header_assump}:"])
        for a in assumptions[:5]:
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
    lang = ir.language
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
    return "\n".join(prompt)
