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
  };
  policy?: PolicyLike;
};

type CompileResultLike = {
  ir?: IRLike;
  ir_v2?: IRLike;
};

export type NormalizedIntentPolicy = {
  domain: string;
  persona: string;
  intents: string[];
  riskLevel: string;
  riskDomains: string[];
  allowedTools: string[];
  forbiddenTools: string[];
  sanitizationRules: string[];
  dataSensitivity: string;
  executionMode: string;
};

const emptyList = (value: string[] | undefined) => value ?? [];

export function normalizeIntentPolicy(result: CompileResultLike): NormalizedIntentPolicy {
  const source = result.ir_v2 ?? result.ir ?? {};
  const legacyRiskFlags = emptyList(result.ir?.metadata?.risk_flags);
  const policy = source.policy ?? {};

  return {
    domain: source.domain ?? result.ir?.domain ?? "general",
    persona: source.persona ?? result.ir?.persona ?? "assistant",
    intents: emptyList(source.intents ?? result.ir?.intents),
    riskLevel:
      policy.risk_level ?? (legacyRiskFlags.length > 0 ? (legacyRiskFlags.includes("security") ? "medium" : "high") : "low"),
    riskDomains: emptyList(policy.risk_domains ?? legacyRiskFlags),
    allowedTools: emptyList(policy.allowed_tools),
    forbiddenTools: emptyList(policy.forbidden_tools),
    sanitizationRules: emptyList(policy.sanitization_rules),
    dataSensitivity: policy.data_sensitivity ?? "public",
    executionMode: policy.execution_mode ?? "advice_only",
  };
}
