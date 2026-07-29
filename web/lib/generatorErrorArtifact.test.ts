import { describe, expect, it } from "vitest";
import {
  assertUsableGeneratorArtifact,
  parseGeneratorErrorArtifact,
} from "./generatorErrorArtifact";

describe("generatorErrorArtifact", () => {
  it("parses agent timeout error artifacts", () => {
    expect(
      parseGeneratorErrorArtifact(
        "# Error\n\nFailed to generate agent: Agent generation timed out after 30s.",
      ),
    ).toBe("Agent generation timed out after 30s.");
  });

  it("parses skill error artifacts", () => {
    expect(
      parseGeneratorErrorArtifact("# Error\n\nFailed to generate skill: API Key is missing."),
    ).toBe("API Key is missing.");
  });

  it("ignores legitimate prompts that mention errors", () => {
    expect(
      parseGeneratorErrorArtifact(
        "# Support Agent\n\n## Error Handling\nFailed to generate agent: never treat this as an artifact error.",
      ),
    ).toBeNull();
  });

  it("throws for unusable artifacts and allows real prompts", () => {
    expect(() =>
      assertUsableGeneratorArtifact(
        "# Error\n\nFailed to generate agent: Agent generation timed out after 30s.",
      ),
    ).toThrow("Agent generation timed out after 30s.");

    expect(() => assertUsableGeneratorArtifact("# Reviewer\n\n## Role\nReview code.")).not.toThrow();
  });
});
