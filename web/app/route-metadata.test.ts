import { describe, expect, it } from "vitest";

import { metadata as rootMetadata } from "./layout";
import { metadata as agentGeneratorMetadata } from "./agent-generator/layout";
import { metadata as agentPacksMetadata } from "./agent-packs/layout";
import { metadata as benchmarkMetadata } from "./benchmark/layout";
import { metadata as offlineMetadata } from "./offline/layout";
import { metadata as optimizerMetadata } from "./optimizer/layout";
import { metadata as prSafetyMetadata } from "./pr-safety/layout";
import { metadata as skillsGeneratorMetadata } from "./skills-generator/layout";

type RouteMetadataCase = {
  descriptionFragment: string;
  metadata: {
    description?: string | null;
    title?: string | null;
  };
  title: string;
};

const ROUTE_CASES: RouteMetadataCase[] = [
  {
    title: "Agent Generator — Prompt Compiler",
    metadata: agentGeneratorMetadata,
    descriptionFragment: "autonomous AI agent",
  },
  {
    title: "Agent Packs — Prompt Compiler",
    metadata: agentPacksMetadata,
    descriptionFragment: "repo-ready assets",
  },
  {
    title: "Prompt Benchmark — Prompt Compiler",
    metadata: benchmarkMetadata,
    descriptionFragment: "raw versus compiled",
  },
  {
    title: "Offline Compiler — Prompt Compiler",
    metadata: offlineMetadata,
    descriptionFragment: "local-only prompt compiler",
  },
  {
    title: "Token Optimizer — Prompt Compiler",
    metadata: optimizerMetadata,
    descriptionFragment: "OpenRouter cost estimates",
  },
  {
    title: "PR Safety — Prompt Compiler",
    metadata: prSafetyMetadata,
    descriptionFragment: "merge-readiness report",
  },
  {
    title: "Skill Generator — Prompt Compiler",
    metadata: skillsGeneratorMetadata,
    descriptionFragment: "Tool/Skill definition",
  },
];

describe("route metadata", () => {
  it("keeps the root brand metadata aligned across document and social fields", () => {
    expect(rootMetadata.title).toBe("Prompt Compiler");
    expect(rootMetadata.description).toBe("Catch weak prompts before you spend an agent run");
    expect(rootMetadata.openGraph?.title).toBe("Prompt Compiler");
    expect(rootMetadata.openGraph?.description).toBe("Catch weak prompts before you spend an agent run");
    expect(rootMetadata.openGraph?.type).toBe("website");
    expect(rootMetadata.twitter?.title).toBe("Prompt Compiler");
    expect(rootMetadata.twitter?.description).toBe("Catch weak prompts before you spend an agent run");
    expect(rootMetadata.twitter?.card).toBe("summary_large_image");
  });

  it.each(ROUTE_CASES)(
    "gives $title a route-specific title and product description",
    ({ descriptionFragment, metadata, title }) => {
      expect(metadata.title).toBe(title);
      expect(metadata.title).toMatch(/ — Prompt Compiler$/);
      expect(metadata.description).toEqual(expect.any(String));
      expect(metadata.description).toContain(descriptionFragment);
      expect(metadata.description?.length).toBeGreaterThan(60);
    },
  );
});
