import type { AgentPackFile, AgentPackFileKind, AgentPackManifest, AgentPackType } from "./types";

export type InstallChecklistSectionId =
  | "generatedFiles"
  | "reviewFirst"
  | "validationSteps"
  | "nextAction";

export interface InstallChecklistSection {
  id: InstallChecklistSectionId;
  title: string;
  items: string[];
}

const REVIEW_KINDS: ReadonlySet<AgentPackFileKind> = new Set([
  "settings",
  "workflow",
  "mcp",
  "agents",
]);

const EXECUTABLE_EXTENSIONS = [".py", ".sh", ".js", ".ts", ".mjs"];

function isExecutablePath(path: string): boolean {
  const lower = path.toLowerCase();
  return EXECUTABLE_EXTENSIONS.some((ext) => lower.endsWith(ext));
}

function buildReviewItems(files: AgentPackFile[]): string[] {
  const items: string[] = [];

  for (const file of files) {
    if (REVIEW_KINDS.has(file.kind)) {
      items.push(`Review ${file.path} for permissions, secrets, and unsafe defaults before committing.`);
      continue;
    }

    if (isExecutablePath(file.path)) {
      items.push(`Inspect ${file.path} as untrusted code before running or deploying it.`);
    }
  }

  return [...new Set(items)];
}

function buildValidationSteps(packType: AgentPackType, files: AgentPackFile[]): string[] {
  const paths = new Set(files.map((file) => file.path));
  const steps: string[] = [];

  const hasClaudeMd = paths.has("CLAUDE.md");
  const hasSettings = [...paths].some((path) => path.includes("settings.json"));
  const hasWorkflow = files.some((file) => file.kind === "workflow");
  const hasAgents = files.some((file) => file.kind === "agents");
  const hasMcp = files.some((file) => file.kind === "mcp");
  const hasReadme = files.some((file) => file.kind === "readme");

  switch (packType) {
    case "project-pack":
      if (hasClaudeMd) {
        steps.push("Place CLAUDE.md at your repository root so Claude Code can load repo memory.");
      }
      if (hasSettings) {
        steps.push("Merge .claude/settings.json carefully and confirm tool permissions match your risk tolerance.");
      }
      if (hasAgents) {
        steps.push("Copy generated agent files into .claude/agents/ and skim each prompt for your workflow.");
      }
      if (hasWorkflow) {
        steps.push("Review the GitHub workflow YAML permissions and triggers before enabling CI.");
      }
      if (hasMcp) {
        steps.push("Validate MCP config paths and only enable servers you trust.");
      }
      break;

    case "pr-reviewer":
      if (hasClaudeMd) {
        steps.push("Add CLAUDE.md to the repo root so review guidance is available to Claude Code.");
      }
      if (hasAgents) {
        steps.push("Install the pr-reviewer agent under .claude/agents/ and test it on a sample PR.");
      }
      if (hasWorkflow) {
        steps.push("Confirm the workflow only runs with the scopes you expect on pull requests.");
      }
      break;

    case "subagent":
      if (hasAgents) {
        steps.push("Drop the subagent markdown into .claude/agents/ and invoke it from Claude Code.");
      }
      if (hasReadme) {
        steps.push("Read the README for install notes and example prompts before first use.");
      }
      break;

    case "mcp-tool-stub":
      if (paths.has("server.py") || files.some((file) => isExecutablePath(file.path))) {
        steps.push("Review the generated server code, dependencies, and tool surface before running it.");
      }
      if (hasMcp) {
        steps.push("Wire the MCP config into your Claude client only after reviewing allowed tools.");
      }
      if (hasReadme) {
        steps.push("Follow the README setup steps and run a dry-run against a test workspace.");
      }
      break;
  }

  if (steps.length === 0) {
    steps.push("Open each generated file in your editor and confirm paths match your repository layout.");
  }

  return steps;
}

function buildNextAction(downloaded: boolean): string[] {
  if (downloaded) {
    return [
      "Unpack the zip into your repo, complete the review steps above, then commit only the files you trust.",
    ];
  }

  return [
    "Use Download Pack (or Copy All) to move files into your repo, then follow the review and validation steps.",
  ];
}

export function buildInstallChecklist(
  manifest: AgentPackManifest,
  options: { downloaded?: boolean } = {},
): InstallChecklistSection[] {
  const { downloaded = false } = options;
  const generatedFiles = manifest.files.map(
    (file) => `Add ${file.path} to the matching path in your repository.`,
  );

  const reviewItems = buildReviewItems(manifest.files);
  const validationSteps = buildValidationSteps(manifest.pack_type, manifest.files);

  return [
    {
      id: "generatedFiles",
      title: "Files in this pack",
      items: generatedFiles,
    },
    {
      id: "reviewFirst",
      title: "Review before use",
      items:
        reviewItems.length > 0
          ? reviewItems
          : ["Skim every generated file for prompts, permissions, and project-specific assumptions."],
    },
    {
      id: "validationSteps",
      title: "Suggested validation",
      items: validationSteps,
    },
    {
      id: "nextAction",
      title: downloaded ? "Downloaded — next step" : "Next step",
      items: buildNextAction(downloaded),
    },
  ];
}
