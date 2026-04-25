type PolicyLike = {
    risk_level?: string;
    risk_domains?: string[];
    allowed_tools?: string[];
    forbidden_tools?: string[];
    sanitization_rules?: string[];
    data_sensitivity?: string;
    execution_mode?: string;
};

type IRLike = {
    domain?: string;
    persona?: string;
    intents?: string[];
    metadata?: {
        risk_flags?: string[];
        [key: string]: unknown;
    };
    policy?: PolicyLike;
    [key: string]: unknown;
};

type CompileResultLike = {
    ir?: IRLike;
    ir_v2?: IRLike;
};

export type IntentDisplayGroup = "content" | "workflow" | "risk";

export type IntentDetail = {
    key: string;
    label: string;
    description: string;
    group: IntentDisplayGroup;
};

export type NormalizedIntentPolicy = {
    domain: string;
    persona: string;
    intents: string[];
    intentDetails: IntentDetail[];
    riskLevel: string;
    riskDomains: string[];
    allowedTools: string[];
    forbiddenTools: string[];
    sanitizationRules: string[];
    dataSensitivity: string;
    executionMode: string;
};

const emptyList = (value: string[] | undefined) => value ?? [];

const INTENT_GROUP_ORDER: Record<IntentDisplayGroup, number> = {
    content: 0,
    workflow: 1,
    risk: 2,
};

const INTENT_REGISTRY: Record<
    string,
    Omit<IntentDetail, "key"> & { order: number }
> = {
    teaching: {
        label: "Teaching",
        description: "The request is asking for step-by-step learning support.",
        group: "content",
        order: 0,
    },
    explanation: {
        label: "Explanation",
        description: "The user wants a concept clarified or broken down.",
        group: "content",
        order: 1,
    },
    summary: {
        label: "Summary",
        description:
            "The request asks for a condensed version of source material.",
        group: "content",
        order: 2,
    },
    summarize: {
        label: "Summarization",
        description:
            "The prompt benefits from compressing information into a shorter form.",
        group: "content",
        order: 3,
    },
    compare: {
        label: "Comparison",
        description:
            "The user wants trade-offs, differences, or side-by-side evaluation.",
        group: "content",
        order: 4,
    },
    creative: {
        label: "Creative",
        description:
            "The output should generate original copy, ideas, or expressive content.",
        group: "content",
        order: 5,
    },
    variants: {
        label: "Variants",
        description: "Multiple alternative outputs are expected.",
        group: "content",
        order: 6,
    },
    proposal: {
        label: "Proposal",
        description:
            "The request is asking for a recommendation, pitch, or suggested plan.",
        group: "workflow",
        order: 0,
    },
    review: {
        label: "Review",
        description:
            "The task is centered on checking, critiquing, or reviewing something.",
        group: "workflow",
        order: 1,
    },
    preparation: {
        label: "Preparation",
        description:
            "The user is preparing for an interview, exam, or upcoming task.",
        group: "workflow",
        order: 2,
    },
    troubleshooting: {
        label: "Troubleshooting",
        description:
            "The request is focused on diagnosing and fixing a failure.",
        group: "workflow",
        order: 3,
    },
    code: {
        label: "Code",
        description:
            "The prompt involves implementation, code changes, or technical examples.",
        group: "workflow",
        order: 4,
    },
    debug: {
        label: "Debug",
        description:
            "The prompt points to live debugging, reproduction, or error investigation.",
        group: "workflow",
        order: 5,
    },
    recency: {
        label: "Recency",
        description:
            "The request depends on up-to-date or time-sensitive information.",
        group: "workflow",
        order: 6,
    },
    decompose: {
        label: "Decomposition",
        description:
            "The system detected a need to break the task into smaller steps.",
        group: "workflow",
        order: 7,
    },
    risk: {
        label: "Risk",
        description:
            "The request touches a higher-risk area that needs tighter guardrails.",
        group: "risk",
        order: 0,
    },
    capability_mismatch: {
        label: "Capability Mismatch",
        description:
            "The request may exceed the model or tool capabilities available.",
        group: "risk",
        order: 1,
    },
    ambiguous: {
        label: "Ambiguity",
        description:
            "Important details are underspecified and may require clarification.",
        group: "risk",
        order: 2,
    },
};

function titleCase(value: string): string {
    return value
        .split(" ")
        .filter(Boolean)
        .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
        .join(" ");
}

export function humanizeIntentPolicyValue(value: string): string {
    return titleCase(value.replace(/[_-]+/g, " ").trim());
}

function buildIntentDetail(intent: string): IntentDetail {
    const entry = INTENT_REGISTRY[intent];
    if (entry) {
        return {
            key: intent,
            label: entry.label,
            description: entry.description,
            group: entry.group,
        };
    }

    return {
        key: intent,
        label: humanizeIntentPolicyValue(intent),
        description:
            "Detected from compiler heuristics; no custom explanation is registered yet.",
        group: "workflow",
    };
}

function getIntentOrder(intent: IntentDetail): number {
    return INTENT_REGISTRY[intent.key]?.order ?? 999;
}

function normalizeIntentDetails(intents: string[]): IntentDetail[] {
    const uniqueIntents = [...new Set(intents)];

    return uniqueIntents.map(buildIntentDetail).sort((left, right) => {
        const groupDelta =
            INTENT_GROUP_ORDER[left.group] - INTENT_GROUP_ORDER[right.group];
        if (groupDelta !== 0) {
            return groupDelta;
        }

        const orderDelta = getIntentOrder(left) - getIntentOrder(right);
        if (orderDelta !== 0) {
            return orderDelta;
        }

        return left.label.localeCompare(right.label);
    });
}

export function normalizeIntentPolicy(
    result: CompileResultLike,
): NormalizedIntentPolicy {
    const source = result.ir_v2 ?? result.ir ?? {};
    const legacyRiskFlags = emptyList(result.ir?.metadata?.risk_flags);
    const policy = source.policy ?? {};
    const intents = emptyList(source.intents ?? result.ir?.intents);

    return {
        domain: source.domain ?? result.ir?.domain ?? "general",
        persona: source.persona ?? result.ir?.persona ?? "assistant",
        intents,
        intentDetails: normalizeIntentDetails(intents),
        riskLevel:
            policy.risk_level ??
            (legacyRiskFlags.length > 0
                ? legacyRiskFlags.includes("security")
                    ? "medium"
                    : "high"
                : "low"),
        riskDomains: emptyList(policy.risk_domains ?? legacyRiskFlags),
        allowedTools: emptyList(policy.allowed_tools),
        forbiddenTools: emptyList(policy.forbidden_tools),
        sanitizationRules: emptyList(policy.sanitization_rules),
        dataSensitivity: policy.data_sensitivity ?? "public",
        executionMode: policy.execution_mode ?? "advice_only",
    };
}
