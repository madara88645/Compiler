from __future__ import annotations
from .models import IR

def emit_system_prompt(ir: IR) -> str:
    parts = [
        f"Role: {ir.role}",
        "Rules:",
        "- Follow goals, tasks, constraints, and style/tone.",
        f"- Output format: {ir.output_format}; length: {ir.length_hint}.",
    ]
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
        for k,v in ir.inputs.items():
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

def emit_expanded_prompt(ir: IR) -> str:
    # Natural, example-based one-shot style expansion for everyday users
    lang = ir.language
    title = "Genişletilmiş İstem" if lang == 'tr' else "Expanded Prompt"
    intro = (
        "Aşağıdaki bağlama göre net ve eyleme dönük öneriler üret." if lang=='tr'
        else "Generate clear, actionable suggestions based on the context below."
    )
    ctx_lines = []
    if ir.goals:
        ctx_lines.append(("Amaçlar" if lang=='tr' else "Goals")+": "+" | ".join(ir.goals[:3]))
    if ir.tasks:
        ctx_lines.append(("Görevler" if lang=='tr' else "Tasks")+": "+" | ".join(ir.tasks[:3]))
    if ir.constraints:
        ctx_lines.append(("Kısıtlar" if lang=='tr' else "Constraints")+": "+" | ".join(ir.constraints[:3]))
    if ir.inputs:
        kv = [f"{k}={v}" for k,v in list(ir.inputs.items())[:4]]
        ctx_lines.append(("Girdi ipuçları" if lang=='tr' else "Input hints")+": "+", ".join(kv))
    if ir.style:
        ctx_lines.append(("Stil" if lang=='tr' else "Style")+": "+", ".join(ir.style))
    if ir.tone:
        ctx_lines.append(("Ton" if lang=='tr' else "Tone")+": "+", ".join(ir.tone))
    # Example template
    example_header = "Örnek çıktı formatı" if lang=='tr' else "Example output format"
    example_block = (
        "- Öneri 1: … (Neden: …)\n- Öneri 2: … (Neden: …)" if lang=='tr'
        else "- Suggestion 1: … (Why: …)\n- Suggestion 2: … (Why: …)"
    )
    fmt_line = (
        f"Biçim: {ir.output_format}, Uzunluk: {ir.length_hint}" if lang=='tr' else
        f"Format: {ir.output_format}, Length: {ir.length_hint}"
    )
    orig = (ir.metadata or {}).get('original_text') or ""
    prompt = [
        f"{title}",
        intro,
        "",
        ("Girdi" if lang=='tr' else "Input")+f": {orig}",
        "",
        ("Bağlam" if lang=='tr' else "Context")+":",
        *ctx_lines,
        "",
        fmt_line,
        "",
        example_header+":",
        example_block
    ]
    return "\n".join([line for line in prompt if line is not None])
