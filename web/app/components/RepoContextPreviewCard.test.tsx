import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import RepoContextPreviewCard from "./RepoContextPreviewCard";
import type { GitHubRepoContextPayload } from "@/lib/api/types";

function makeRepoContext(
  overrides: Partial<GitHubRepoContextPayload> = {},
): GitHubRepoContextPayload {
  return {
    normalized_repo_url: "https://github.com/org/repo",
    repo_full_name: "org/repo",
    default_branch: "main",
    summary: "A TypeScript monorepo with a Next.js frontend.",
    highlights: [],
    files_used: [],
    detected_stack: [],
    ...overrides,
  };
}

describe("RepoContextPreviewCard", () => {
  it("renders repo_full_name and default_branch", () => {
    render(
      <RepoContextPreviewCard
        accent="green"
        repoContext={makeRepoContext({
          repo_full_name: "madara88645/compiler",
          default_branch: "develop",
        })}
      />,
    );

    expect(screen.getByText("madara88645/compiler")).toBeInTheDocument();
    expect(screen.getByText("develop")).toBeInTheDocument();
    expect(screen.getByText(/TypeScript monorepo/i)).toBeInTheDocument();
  });

  it("omits the default_branch badge when default_branch is null", () => {
    render(
      <RepoContextPreviewCard
        accent="green"
        repoContext={makeRepoContext({ default_branch: null })}
      />,
    );

    expect(screen.getByText("org/repo")).toBeInTheDocument();
    expect(screen.queryByText("main")).not.toBeInTheDocument();
  });

  it("applies green accent styles", () => {
    const { container } = render(
      <RepoContextPreviewCard
        accent="green"
        repoContext={makeRepoContext({
          detected_stack: ["TypeScript"],
        })}
      />,
    );

    const card = container.firstElementChild;
    expect(card?.className).toContain("ring-green-500/20");

    const branchBadge = screen.getByText("main");
    expect(branchBadge.className).toContain("bg-green-500/10");
    expect(branchBadge.className).toContain("text-green-200");

    const stackBadge = screen.getByText("TypeScript");
    expect(stackBadge.className).toContain("text-green-300");
  });

  it("applies yellow accent styles", () => {
    const { container } = render(
      <RepoContextPreviewCard
        accent="yellow"
        repoContext={makeRepoContext({
          detected_stack: ["Python"],
        })}
      />,
    );

    const card = container.firstElementChild;
    expect(card?.className).toContain("ring-yellow-500/20");

    const branchBadge = screen.getByText("main");
    expect(branchBadge.className).toContain("bg-yellow-500/10");
    expect(branchBadge.className).toContain("text-yellow-200");

    const stackBadge = screen.getByText("Python");
    expect(stackBadge.className).toContain("text-yellow-300");
  });

  it("renders detected_stack, highlights, and files_used when non-empty", () => {
    render(
      <RepoContextPreviewCard
        accent="green"
        repoContext={makeRepoContext({
          detected_stack: ["Next.js", "Vitest"],
          highlights: ["Uses App Router", "Has focused unit tests"],
          files_used: ["package.json", "README.md"],
        })}
      />,
    );

    expect(screen.getByText("Next.js")).toBeInTheDocument();
    expect(screen.getByText("Vitest")).toBeInTheDocument();
    expect(screen.getByText("Uses App Router")).toBeInTheDocument();
    expect(screen.getByText("Has focused unit tests")).toBeInTheDocument();
    expect(screen.getByText("package.json")).toBeInTheDocument();
    expect(screen.getByText("README.md")).toBeInTheDocument();
    expect(screen.getByText("Highlights")).toBeInTheDocument();
    expect(screen.getByText("Files Used")).toBeInTheDocument();
  });

  it("hides detected_stack, highlights, and files_used sections when empty", () => {
    render(
      <RepoContextPreviewCard
        accent="yellow"
        repoContext={makeRepoContext({
          detected_stack: [],
          highlights: [],
          files_used: [],
        })}
      />,
    );

    expect(screen.queryByText("Highlights")).not.toBeInTheDocument();
    expect(screen.queryByText("Files Used")).not.toBeInTheDocument();
    expect(screen.getByText("org/repo")).toBeInTheDocument();
  });
});
