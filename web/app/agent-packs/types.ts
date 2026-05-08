export type AgentPackType = "project-pack" | "subagent" | "pr-reviewer" | "mcp-tool-stub";
export type AgentPackRiskMode = "balanced" | "strict";
export type AgentPackFileKind =
  | "claude_md"
  | "settings"
  | "agents"
  | "workflow"
  | "mcp"
  | "readme"
  | "files";

export interface AgentPackRequest {
  project_type: string;
  stack: string;
  goal: string;
  pack_type: AgentPackType;
  risk_mode: AgentPackRiskMode;
}

export interface AgentPackFile {
  path: string;
  content: string;
  kind: AgentPackFileKind;
}

export interface AgentPackManifest {
  provider: string;
  pack_type: AgentPackType;
  files: AgentPackFile[];
  download_name: string;
  preview_order: AgentPackFileKind[];
}

export interface AgentPackProviderConfig {
  id: string;
  name: string;
  badge: string;
  summary: string;
  ctaLabel: string;
  accentClass: string;
  glowClass: string;
  buttonClass: string;
}
