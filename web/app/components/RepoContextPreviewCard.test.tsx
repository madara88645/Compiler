import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import RepoContextPreviewCard from "./RepoContextPreviewCard";
import type { GitHubRepoContextPayload } from "@/lib/api/types";

function makePayload(overrides: Partial<GitHubRepoContextPayload> = {}): GitHubRepoContextPayload {
  return {
    repo_full_name: "madara88645/Compiler",
    default_branch: "main",
    summary: "A prompt compiler tool.",
    detected_stack: ["Python", "Next.js"],
    highlights: ["FastAPI backend", "Vitest test suite"],
    files_used: ["README.md", "pyproject.toml"],
    ...overrides,
  };
}

describe("RepoContextPreviewCard", () => {
  it("renders repo name and default branch", () => {
    render(<RepoContextPreviewCard repoContext={makePayload()} accent="green" />);
    expect(screen.getByText("madara88645/Compiler")).toBeInTheDocument();
    expect(screen.getByText("main")).toBeInTheDocument();
  });

  it("renders summary text", () => {
    render(<RepoContextPreviewCard repoContext={makePayload()} accent="green" />);
    expect(screen.getByText("A prompt compiler tool.")).toBeInTheDocument();
  });

  it("renders detected stack items", () => {
    render(<RepoContextPreviewCard repoContext={makePayload()} accent="yellow" />);
    expect(screen.getByText("Python")).toBeInTheDocument();
    expect(screen.getByText("Next.js")).toBeInTheDocument();
  });

  it("renders highlights section when non-empty", () => {
    render(<RepoContextPreviewCard repoContext={makePayload()} accent="green" />);
    expect(screen.getByText("Highlights")).toBeInTheDocument();
    expect(screen.getByText("FastAPI backend")).toBeInTheDocument();
    expect(screen.getByText("Vitest test suite")).toBeInTheDocument();
  });

  it("renders files used section when non-empty", () => {
    render(<RepoContextPreviewCard repoContext={makePayload()} accent="green" />);
    expect(screen.getByText("Files Used")).toBeInTheDocument();
    expect(screen.getByText("README.md")).toBeInTheDocument();
    expect(screen.getByText("pyproject.toml")).toBeInTheDocument();
  });

  it("omits highlights section when empty", () => {
    render(
      <RepoContextPreviewCard
        repoContext={makePayload({ highlights: [] })}
        accent="green"
      />,
    );
    expect(screen.queryByText("Highlights")).not.toBeInTheDocument();
  });

  it("omits stack section when empty", () => {
    render(
      <RepoContextPreviewCard
        repoContext={makePayload({ detected_stack: [] })}
        accent="green"
      />,
    );
    expect(screen.queryByText("Python")).not.toBeInTheDocument();
  });

  it("omits files used section when empty", () => {
    render(
      <RepoContextPreviewCard
        repoContext={makePayload({ files_used: [] })}
        accent="green"
      />,
    );
    expect(screen.queryByText("Files Used")).not.toBeInTheDocument();
  });

  it("omits branch badge when default_branch is falsy", () => {
    render(
      <RepoContextPreviewCard
        repoContext={makePayload({ default_branch: "" })}
        accent="yellow"
      />,
    );
    expect(screen.queryByText("main")).not.toBeInTheDocument();
  });

  it("applies green accent classes", () => {
    const { container } = render(
      <RepoContextPreviewCard repoContext={makePayload()} accent="green" />,
    );
    expect(container.firstElementChild?.className).toContain("ring-green-500/20");
  });

  it("applies yellow accent classes", () => {
    const { container } = render(
      <RepoContextPreviewCard repoContext={makePayload()} accent="yellow" />,
    );
    expect(container.firstElementChild?.className).toContain("ring-yellow-500/20");
  });
});
