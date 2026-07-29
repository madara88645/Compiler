/**
 * HybridCompiler catches generator failures and returns markdown like:
 *   # Error
 *
 *   Failed to generate agent: Agent generation timed out after 30s.
 *
 * That payload must be treated as an error state, not an exportable artifact.
 */
// Avoid the `s` (dotAll) flag — tsconfig target is ES2017.
const GENERATOR_ERROR_ARTIFACT_RE =
  /^#\s*Error\s*\n+Failed to generate (?:agent|skill):\s*([\s\S]+?)\s*$/i;

export function parseGeneratorErrorArtifact(content: string | null | undefined): string | null {
  if (typeof content !== "string") {
    return null;
  }
  const match = content.trim().match(GENERATOR_ERROR_ARTIFACT_RE);
  if (!match) {
    return null;
  }
  const message = match[1]?.trim();
  return message || null;
}

export function assertUsableGeneratorArtifact(content: string | null | undefined): void {
  const message = parseGeneratorErrorArtifact(content);
  if (message) {
    throw new Error(message);
  }
}
