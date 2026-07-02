from __future__ import annotations
from typing import List
import itertools
import os
from .models import IR
from .models_v2 import IRv2, ConstraintV2, StepV2
from .heuristics import detect_frontend_download_feature


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


# Decisive, domain-aware follow-up questions. These replace generic filler
# ("which success metrics matter most?") with the questions a competent engineer
# would actually ask. They are conservative: questions, never invented facts.
_FOLLOWUP_SETS = {
    "perf": [
        "Have you profiled it (e.g. React DevTools Profiler) to see which components or calls dominate?",
        "Which components re-render, and is it from state/context placement or unmemoized props/children?",
        "What is the current versus target metric (render time, FPS, payload) and at what data size?",
    ],
    "browser": [
        "Which browser and version is affected, and does it work in others?",
        "What are the exact reproduction steps and any console or network errors?",
        "What is the expected behavior versus what actually happens?",
    ],
    "browser_feature": [
        "Which file format, filename, and data should the download include?",
        "Should the file be generated in the browser or returned by a server endpoint?",
        "Which browsers and accessibility states must the download control support?",
    ],
    "payment": [
        "Are API keys and secrets kept server-side only (never exposed in the browser)?",
        "Which figures and events matter (gross vs net, refunds, disputes, currency)?",
        "What is the data source, refresh cadence, and date range?",
    ],
    "security": [
        "What is the threat model and the attacker's assumed capability?",
        "What data sensitivity or compliance constraints apply?",
        "How should failed attempts, thresholds, and false positives be handled?",
    ],
    "ops": [
        "Is there a tested backup and a rollback plan before this runs?",
        "Has it been validated in a staging environment first?",
        "What is the blast radius if it goes wrong, and who must approve?",
    ],
    "software": [
        "Which language, framework, and version are targeted?",
        "What are the expected inputs, outputs, and key edge cases?",
        "How should errors, performance, and tests be handled?",
    ],
    "generic": [
        "What does a successful result look like concretely?",
        "Which constraints (time, tools, format) must the answer respect?",
    ],
}


# Conservative, hand-authored engineering gotchas for common scenarios. These
# are well-known true facts (not invented APIs), surfaced as considerations and
# tightly keyed (two signals required) so they do not misfire on the wrong task.
_SCENARIO_CONSIDERATIONS = {
    "browser_download": [
        "Trigger the download from a user gesture; Safari often needs a Blob + an <a download> link, or it opens the file instead of saving it.",
        "The File System Access API is unsupported in Safari — provide an anchor-download fallback and test large files.",
    ],
    "log_bruteforce": [
        "Parse the actual log format first (e.g. nginx combined); infer brute-force from repeated failed-auth responses (401/403) per client IP within a time window.",
        "Tune the threshold and window, and handle false positives from shared NAT/proxies and legitimate retries.",
    ],
    "payment": [
        "Keep the secret key server-side only — never ship it to the browser; use separate test and live keys.",
        "Reconcile gross vs net (fees, refunds, disputes, currency) and verify webhook signatures before trusting events.",
    ],
    "react_perf": [
        "Profile before changing code (React DevTools Profiler) to find which components actually re-render.",
        "Cut re-renders with memoization (React.memo / useMemo / useCallback) and better state placement; virtualize long lists.",
    ],
    "sql_query": [
        "Run EXPLAIN/ANALYZE on slow or complex queries to identify bottlenecks; ensure indexes exist on frequently filtered or joined columns.",
        "Identify and avoid ORM N+1 query patterns by using eager loading or joining strategies.",
    ],
    "file_upload": [
        "Perform server-side file size and type validation; do not trust client-supplied metadata or extensions.",
        "Stream uploads directly to disk or cloud storage, and store files outside the public web root directory.",
    ],
    "auth_login": [
        "Use salted slow hashing algorithms (like bcrypt, argon2, or scrypt) for password storage instead of fast hashes.",
        "Store session identifiers in cookies with Secure, httpOnly, and SameSite attributes, and enforce rate limiting on logins.",
    ],
    "datetime_tz": [
        "Store and perform calculations on datetimes in UTC; convert to local timezone only at the presentation layer.",
        "Use robust timezone libraries that automatically handle Daylight Saving Time (DST) changes to avoid offset calculation errors.",
    ],
    "frontend_perf": [
        "Use framework devtools (e.g. React DevTools Profiler) to profile component rendering and state updates first.",
        "Apply component memoization, debounced event handlers, and list virtualization for long lists to reduce rendering overhead.",
    ],
}


# Exploration-mode scheduling (see heuristics/handlers/exploration.py).
# Rendering reads only scheduling.mode; reason/confidence are for future
# consumers (agent packs, analytics, benchmarking). Behavioral text only —
# no sampling parameters, no jargon.
_PLAN_MODE_RATIONALE = {
    "explore": (
        "Rationale: the cause is not yet established; list plausible explanations "
        "and test them against evidence before committing to a fix"
    ),
    "decide": (
        "Rationale: converge on one option by impact, effort, and risk; "
        "do not keep exploring once a choice is justified"
    ),
    "verify": (
        "Rationale: high-impact change; confirm edge cases and regressions "
        "instead of assuming success"
    ),
}

_PLAN_PSEUDO_STEP_TEXT = {
    "decide": "Choose one likely cause or approach to pursue before making changes.",
    "verify": "Re-check the result against the original request before treating it as done.",
}

_MODE_DIRECTIVES = {
    "en": {
        "explore": (
            "Start by listing the plausible causes or approaches and check them against "
            "the evidence; do not commit to changes while the cause is still unknown."
        ),
        "decide": (
            "Pick one option based on impact, effort, and risk, and state briefly why it "
            "wins; stop exploring once a choice is justified."
        ),
        "execute": (
            "Carry out the chosen work exactly as scoped; do not add requirements, "
            "dependencies, or scope beyond what was asked."
        ),
        "verify": (
            "Before finishing, re-check the result against the original request, including "
            "edge cases and possible regressions; do not treat unverified output as done."
        ),
    },
    "tr": {
        "explore": (
            "Önce olası nedenleri veya yaklaşımları listele ve kanıtlarla karşılaştır; "
            "neden belirsizken değişiklik yapmaya başlama."
        ),
        "decide": (
            "Etki, maliyet ve riske göre tek bir seçenek belirle ve nedenini kısaca "
            "açıkla; karar verildikten sonra keşfe geri dönme."
        ),
        "execute": (
            "Seçilen işi tam olarak istenen kapsamda uygula; istenmeyen gereksinim, "
            "bağımlılık veya kapsam ekleme."
        ),
        "verify": (
            "Bitirmeden önce sonucu özgün istekle karşılaştır; uç durumları ve olası "
            "gerilemeleri kontrol etmeden işi bitmiş sayma."
        ),
    },
    "es": {
        "explore": (
            "Primero enumera las causas o enfoques plausibles y contrástalos con la "
            "evidencia; no hagas cambios mientras la causa siga siendo desconocida."
        ),
        "decide": (
            "Elige una opción según impacto, esfuerzo y riesgo, y explica brevemente por "
            "qué; deja de explorar una vez justificada la elección."
        ),
        "execute": (
            "Ejecuta el trabajo elegido exactamente según lo acordado; no añadas "
            "requisitos, dependencias ni alcance extra."
        ),
        "verify": (
            "Antes de terminar, contrasta el resultado con la solicitud original, "
            "incluidos casos límite y posibles regresiones; no des por terminado un "
            "resultado sin verificar."
        ),
    },
}

_MODE_LABELS = {
    "en": {"explore": "Explore", "decide": "Decide", "execute": "Execute", "verify": "Verify"},
    "tr": {"explore": "Keşfet", "decide": "Karar ver", "execute": "Uygula", "verify": "Doğrula"},
    "es": {"explore": "Explorar", "decide": "Decidir", "execute": "Ejecutar", "verify": "Verificar"},
}


def _step_mode(step) -> str | None:
    """Scheduling mode of a step, tolerating objects without the attribute."""
    return getattr(getattr(step, "scheduling", None), "mode", None)


def _scheduled_modes(ir) -> list[str]:
    """Modes to surface in the Working approach section, in fixed order.

    Empty for an untouched compile (suppression rule): the section renders only
    when explore/decide/verify was actually scheduled — a lone execute tag or a
    silent profile must not create a section.
    """
    modes: set[str] = set()
    for step in getattr(ir, "steps", None) or []:
        mode = _step_mode(step)
        if mode:
            modes.add(mode)
    profile = (getattr(ir, "metadata", None) or {}).get("uncertainty_profile") or {}
    profile_modes = profile.get("modes") or {}
    for name in ("explore", "decide", "verify"):
        if (profile_modes.get(name) or {}).get("scheduled"):
            modes.add(name)
    if not modes & {"explore", "decide", "verify"}:
        return []
    return [m for m in ("explore", "decide", "execute", "verify") if m in modes]


def _contains_any_marker(text: str, markers: tuple[str, ...]) -> bool:
    """Fast-path helper to bypass any() generator overhead."""
    for marker in markers:
        if marker in text:
            return True
    return False


def _scenario_considerations(ir) -> list[str]:
    """High-value, conservative gotchas for a recognized scenario (empty if none)."""
    parts: list[str] = []
    for attr in ("goals", "tasks"):
        parts.extend(getattr(ir, attr, None) or [])
    text = " ".join(parts).lower()
    if detect_frontend_download_feature(text):
        return _SCENARIO_CONSIDERATIONS["browser_download"]
    # Bolt Optimization: Replace any() generator expression with fast-path loop to avoid overhead
    is_log_source = (
        _contains_any_marker(text, ("log file", "log files", "logs", "logfile", "logfiles"))
        or " log " in f" {text} "
    )
    if is_log_source and _contains_any_marker(
        text, ("brute", "attack", "intrusion", "abuse", "bruteforce", "failed")
    ):
        return _SCENARIO_CONSIDERATIONS["log_bruteforce"]
    # Bolt Optimization: Replace any() generator expression with fast-path loop to avoid overhead
    if _contains_any_marker(text, ("stripe", "payment", "billing", "checkout", "invoice")):
        return _SCENARIO_CONSIDERATIONS["payment"]
    # Bolt Optimization: Replace any() generator expression with fast-path loop to avoid overhead
    if "react" in text and _contains_any_marker(
        text, ("re-render", "rerender", "render", "slow", "perf", "memo")
    ):
        return _SCENARIO_CONSIDERATIONS["react_perf"]
    has_orm = (
        "orm" in [w.strip(".,;:!?()") for w in text.split()] or "-orm" in text or "orm-" in text
    )
    if (
        _contains_any_marker(text, ("sql", "postgres", "mysql", "sqlite", "n+1"))
        or has_orm
        or (
            "query" in text
            and _contains_any_marker(
                text, ("database", "db", "select", "insert", "update", "delete")
            )
        )
    ):
        return _SCENARIO_CONSIDERATIONS["sql_query"]
    if _contains_any_marker(text, ("upload", "multipart")):
        return _SCENARIO_CONSIDERATIONS["file_upload"]
    if _contains_any_marker(
        text, ("login", "auth", "signup", "signin", "authenticate", "password")
    ):
        return _SCENARIO_CONSIDERATIONS["auth_login"]
    if _contains_any_marker(
        text, ("timezone", "utc", "daylight saving", "datetime")
    ) or _contains_any_marker(f" {text} ", (" dst ", " tz ")):
        return _SCENARIO_CONSIDERATIONS["datetime_tz"]
    if _contains_any_marker(
        text, ("frontend", "ui", "vue", "angular", "framework")
    ) and _contains_any_marker(
        text,
        (
            "re-render",
            "rerender",
            "render",
            "slow",
            "perf",
            "performance",
            "memo",
            "debounce",
            "virtualiz",
        ),
    ):
        return _SCENARIO_CONSIDERATIONS["frontend_perf"]
    return []


def _relevant_followups(ir) -> list[str]:
    """Pick decisive follow-up questions from the detected domain/intents/text."""
    parts: list[str] = []
    for attr in ("goals", "tasks"):
        parts.extend(getattr(ir, attr, None) or [])
    text = " ".join(parts).lower()
    intents = set(getattr(ir, "intents", None) or [])
    domain = (getattr(ir, "domain", "") or "").lower()
    # Bolt Optimization: Replace any() generator expression with fast-path loop to avoid overhead
    if _contains_any_marker(
        text,
        (
            "re-render",
            "rerender",
            "re render",
            "slow",
            "performance",
            "perf",
            "memo",
            "latency",
            "fps",
            "profil",
        ),
    ):
        return _FOLLOWUP_SETS["perf"]
    if detect_frontend_download_feature(text):
        return _FOLLOWUP_SETS["browser_feature"]
    # Bolt Optimization: Replace any() generator expression with fast-path loop to avoid overhead
    if _contains_any_marker(
        text, ("browser", "safari", "chrome", "firefox", "css", "render", "button")
    ):
        return _FOLLOWUP_SETS["browser"]
    # Bolt Optimization: Replace any() generator expression with fast-path loop to avoid overhead
    if _contains_any_marker(
        text, ("stripe", "payment", "billing", "invoice", "checkout", "revenue", "webhook")
    ):
        return _FOLLOWUP_SETS["payment"]
    # Bolt Optimization: Replace any() generator expression with fast-path loop to avoid overhead
    if "risk" in intents or _contains_any_marker(
        text,
        (
            "auth",
            "login",
            "brute",
            "token",
            "encrypt",
            "security",
            "secret",
            "vulnerab",
            "oauth",
            "jwt",
            "xss",
            "csrf",
            "sql injection",
            "password",
        ),
    ):
        return _FOLLOWUP_SETS["security"]
    # Bolt Optimization: Replace any() generator expression with fast-path loop to avoid overhead
    if _contains_any_marker(
        text,
        (
            "deploy",
            "production",
            "database",
            "migrate",
            "wipe",
            "kubernetes",
            "terraform",
            "docker",
            "helm",
            "rollback",
            "downtime",
            "cron",
            "ansible",
        ),
    ):
        return _FOLLOWUP_SETS["ops"]
    if domain == "software" or {"code", "debug", "troubleshooting"} & intents:
        return _FOLLOWUP_SETS["software"]
    return _FOLLOWUP_SETS["generic"]


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


_TRIVIAL_TASK_VERBS = (
    "make",
    "fix",
    "improve",
    "better",
    "build",
    "write",
    "create",
    "add",
    "optimi",
    "refactor",
    "debug",
    "implement",
    "design",
    "generate",
    "summar",
    "review",
    "analyze",
    "translate",
    "explain",
    "plan",
    "compare",
)


def _is_trivial_input(original_text: str, domain: str, complexity: str) -> bool:
    """Return True for greeting-only inputs that should not be expanded with boilerplate.

    A short but actionable request ("make it better") is NOT trivial — it needs
    clarifying questions, so it must not be short-circuited to the greeting reply
    (which tells the model not to add guidance, contradicting the plan).
    """
    stripped = original_text.strip()
    if len(stripped) >= 30 or domain != "general" or complexity not in ("low", None, ""):
        return False
    lowered = stripped.lower()
    # Bolt Optimization: Replace any() generator expression with fast-path loop to avoid overhead
    if _contains_any_marker(lowered, _TRIVIAL_TASK_VERBS):
        return False
    return True


def _minimal_greeting_prompt(original_text: str, lang: str) -> str:
    """Return a minimal downstream instruction for greeting/very-short inputs."""
    orig = " ".join(original_text.strip().split())
    if not orig:
        orig = "hello" if lang != "tr" else "merhaba"
    lowered = orig.lower()
    turkish_markers = ("merhaba", "selam", "slm", "gunaydin", "iyi aksamlar", "nasilsin")
    # Bolt Optimization: Replace any() generator expression with fast-path loop to avoid overhead
    if lang == "tr" or _contains_any_marker(lowered, turkish_markers):
        return (
            "Asagidaki kisa kullanici mesajina kisa, dogal ve dogrudan yanit ver. "
            "Yeni konu ekleme veya gereksiz yonlendirme yapma.\n\n"
            f'Kullanici mesaji: "{orig}"'
        )
    return (
        "Reply briefly, naturally, and directly to the short user message below. "
        "Do not introduce a new topic or unnecessary guidance.\n\n"
        f'User message: "{orig}"'
    )


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
        # Bolt Optimization: Avoid O(N) memory allocation by using itertools.islice instead of list()
        kv = [f"{k}={v}" for k, v in itertools.islice(ir.inputs.items(), 4)]
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
        followups = _relevant_followups(ir)
        header_fu = "Follow-up Questions"
    if followups:
        prompt.extend(["", header_fu + ":"])
        for f in followups[:3]:
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


def _policy_summary_text_v2(ir: IRv2) -> str:
    policy = ir.policy
    parts = [
        f"risk={policy.risk_level}",
        f"execution={policy.execution_mode}",
    ]
    if policy.risk_domains:
        parts.append("domains=" + ",".join(policy.risk_domains[:5]))
    if policy.forbidden_tools:
        parts.append("forbidden_tools=" + ",".join(policy.forbidden_tools[:5]))
    if policy.sanitization_rules:
        parts.append("sanitization=" + ",".join(policy.sanitization_rules[:5]))
    if policy.data_sensitivity and policy.data_sensitivity != "public":
        parts.append(f"data={policy.data_sensitivity}")
    return "; ".join(parts)


def _policy_reason_phrases_v2(ir: IRv2) -> List[str]:
    reasons = (ir.metadata or {}).get("policy_reasons") or []
    phrases: List[str] = []
    for reason in reasons:
        if not isinstance(reason, str):
            continue
        if reason.startswith("high_risk_domain:"):
            phrases.append(f"high-risk domain: {reason.split(':', 1)[1]}")
        elif reason.startswith("risk_domain:"):
            phrases.append(f"risk domain: {reason.split(':', 1)[1]}")
        elif reason.startswith("pii_detected:"):
            phrases.append(f"sensitive data detected: {reason.split(':', 1)[1]}")
        elif reason == "overlapping_risk_domains":
            phrases.append("overlapping risk domains")
        elif reason == "debug_request":
            phrases.append("debugging or code execution context")
        elif reason == "file_or_system_request":
            phrases.append("file or system access requested")
        else:
            phrases.append(reason.replace("_", " "))

    if not phrases and ir.policy.execution_mode == "human_approval_required":
        phrases.append(f"{ir.policy.risk_level} risk policy")
    return phrases


def _policy_check_lines_v2(ir: IRv2) -> List[str]:
    policy = ir.policy
    if (
        policy.execution_mode != "human_approval_required"
        and not policy.forbidden_tools
        and not policy.sanitization_rules
        and policy.data_sensitivity == "public"
    ):
        return []

    lines: List[str] = []
    reasons = _policy_reason_phrases_v2(ir)
    if policy.execution_mode == "human_approval_required":
        lines.append("Approval required because " + ", ".join(reasons) + ".")
    elif reasons:
        lines.append("Policy trigger: " + ", ".join(reasons) + ".")
    if policy.forbidden_tools:
        lines.append("Do not use: " + ", ".join(policy.forbidden_tools[:5]) + ".")
    if policy.sanitization_rules:
        lines.append("Apply sanitization: " + ", ".join(policy.sanitization_rules[:5]) + ".")
    if policy.data_sensitivity and policy.data_sensitivity != "public":
        lines.append(f"Data sensitivity: {policy.data_sensitivity}.")
    return lines


def _is_benign_policy_v2(ir: IRv2) -> bool:
    policy = ir.policy
    return (
        policy.execution_mode == "auto_ok"
        and policy.risk_level == "low"
        and policy.data_sensitivity == "public"
        and not policy.risk_domains
        and not policy.forbidden_tools
        and not policy.sanitization_rules
    )


def _emit_policy_header_v2(ir: IRv2) -> List[str]:
    if _is_benign_policy_v2(ir):
        return []
    summary = _policy_summary_text_v2(ir)
    if not summary:
        return []
    return ["Policy: " + summary]


def _clean_domain_suggestion_text(text: str) -> str:
    value = " ".join((text or "").strip().split())
    for marker in ("Include ", "Add ", "Review ", "Use ", "Follow ", "Consider ", "Handle "):
        index = value.find(marker)
        if 0 < index <= 8:
            return value[index:]
    return value


def _domain_suggestions_v2(ir: IRv2, limit: int = 3) -> List[str]:
    raw = (ir.metadata or {}).get("domain_suggestions") or []
    if not isinstance(raw, list):
        return []

    items: List[tuple[int, str]] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        text = _clean_domain_suggestion_text(str(item.get("text") or ""))
        key = text.lower()
        if not text or key in seen:
            continue
        seen.add(key)
        try:
            priority = int(item.get("priority") or 0)
        except (ValueError, TypeError):
            priority = 0
        items.append((priority, text))

    items.sort(key=lambda pair: pair[0], reverse=True)
    return [text for _, text in items[:limit]]


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
    policy_line = _policy_summary_text_v2(ir)
    if policy_line:
        parts.append("Policy: " + policy_line)
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
            # Basename only — never leak absolute local paths into the system
            # prompt (matches the path-safe rendering used by the other v2 emitter).
            path = (snippet.get("path") or "unknown").split("/")[-1]
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
    clarify_questions = (ir.metadata or {}).get("clarify_questions") or []
    if clarify_questions:
        out.append(
            "1. [clarify] Ask the unresolved clarification questions before choosing a final approach.\n"
            "   Rationale: missing details should be resolved instead of guessed"
        )
    if ir.policy.execution_mode == "human_approval_required":
        step_number = len(out) + 1
        policy_lines = _policy_check_lines_v2(ir)
        rationale = f"Rationale: policy requires human approval for {ir.policy.risk_level} risk"
        if policy_lines:
            rationale += "\n   " + "\n   ".join(policy_lines)
        out.append(
            f"{step_number}. [policy] Pause for human approval before executing or relying on tools.\n"
            f"   {rationale}"
        )
    profile_modes = ((ir.metadata or {}).get("uncertainty_profile") or {}).get("modes") or {}
    decide_pending = bool((profile_modes.get("decide") or {}).get("scheduled"))
    verify_scheduled = bool((profile_modes.get("verify") or {}).get("scheduled"))
    steps = ir.steps if ir.steps else [StepV2(type="task", text=t) for t in ir.tasks]
    for step in steps:
        step_number = len(out) + 1
        kind = step.type if hasattr(step, "type") else "task"
        mode = _step_mode(step)
        if mode in _PLAN_MODE_RATIONALE:
            # explore/verify tags; execute and untagged render identically below
            out.append(f"{step_number}. [{kind}] ({mode}) {step.text}\n   {_PLAN_MODE_RATIONALE[mode]}")
        else:
            rationale = (
                "Rationale: complete the user's stated task without adding unstated requirements"
            )
            out.append(f"{step_number}. [{kind}] {step.text}\n   {rationale}")
        if mode == "explore" and decide_pending:
            decide_pending = False  # one convergence point per plan
            out.append(
                f"{len(out) + 1}. [decide] {_PLAN_PSEUDO_STEP_TEXT['decide']}\n"
                f"   {_PLAN_MODE_RATIONALE['decide']}"
            )
    if verify_scheduled and out:
        out.append(
            f"{len(out) + 1}. [verify] {_PLAN_PSEUDO_STEP_TEXT['verify']}\n"
            f"   {_PLAN_MODE_RATIONALE['verify']}"
        )
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
    policy_checks = _policy_check_lines_v2(ir)
    if policy_checks:
        ctx_lines.append("Policy Checks:")
        for line in policy_checks:
            ctx_lines.append(f"- {line}")
    if ir.inputs:
        # Bolt Optimization: Avoid O(N) memory allocation by using itertools.islice instead of list()
        kv = [f"{k}={v}" for k, v in itertools.islice(ir.inputs.items(), 4)]
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
    scenario_considerations = _scenario_considerations(ir)
    if scenario_considerations:
        ctx_lines.append(
            (
                "Onemli noktalar"
                if lang == "tr"
                else ("Puntos clave" if lang == "es" else "Key considerations")
            )
            + ":"
        )
        for consideration in scenario_considerations:
            ctx_lines.append(f"- {consideration}")
    optional_suggestions = _domain_suggestions_v2(ir, limit=3)
    if optional_suggestions:
        ctx_lines.append(
            (
                "Istege bagli degerlendirmeler"
                if lang == "tr"
                else ("Consideraciones opcionales" if lang == "es" else "Optional considerations")
            )
            + ":"
        )
        for suggestion in optional_suggestions:
            ctx_lines.append(f"- {suggestion}")

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
    policy_header = _emit_policy_header_v2(ir)
    prompt: List[str] = [
        f"{title}",
        intro,
        "",
        *([*policy_header, ""] if policy_header else []),
        ("Girdi" if lang == "tr" else ("Entrada" if lang == "es" else "Input")) + f": {orig}",
        "",
        ("Bağlam" if lang == "tr" else ("Contexto" if lang == "es" else "Context")) + ":",
        *ctx_lines,
        "",
        fmt_line,
    ]
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

    # Working approach: latitude directives for the scheduled exploration modes.
    # Suppressed entirely when the scheduler did not engage (anti-boilerplate).
    scheduled_modes = _scheduled_modes(ir)
    if scheduled_modes:
        header_wa = (
            "Çalışma yaklaşımı"
            if lang == "tr"
            else ("Enfoque de trabajo" if lang == "es" else "Working approach")
        )
        directives = _MODE_DIRECTIVES.get(lang) or _MODE_DIRECTIVES["en"]
        labels = _MODE_LABELS.get(lang) or _MODE_LABELS["en"]
        prompt.extend(["", header_wa + ":"])
        for mode in scheduled_modes:
            prompt.append(f"- {labels[mode]}: {directives[mode]}")

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
        followups = _relevant_followups(ir)
        header_fu = "Follow-up Questions"
    if followups:
        prompt.extend(["", header_fu + ":"])
        for f in followups[:3]:
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
