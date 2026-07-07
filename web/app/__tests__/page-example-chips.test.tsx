import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import Home from "../page";

const useCompilerMock = vi.fn();

vi.mock("../hooks/useCompiler", () => ({
  useCompiler: () => useCompilerMock(),
}));

vi.mock("../components/ContextManager", () => ({
  default: () => <div data-testid="context-manager" />,
}));

vi.mock("../components/OutputSkeleton", () => ({
  default: () => <div data-testid="output-skeleton" />,
}));

describe("Empty state example chips", () => {
  beforeEach(() => {
    window.localStorage.clear();
    // Skip the typewriter animation so fillExample() sets the prompt synchronously.
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: true,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }));
    useCompilerMock.mockReturnValue({
      loading: false,
      result: null,
      status: "Ready",
      lastError: null,
      securityFindings: [],
      redactedText: "",
      runCompile: vi.fn(),
      retry: vi.fn(),
      resolveSecurityDecision: vi.fn(),
      cancelSecurityReview: vi.fn(),
    });
  });

  it("fills the prompt with a messy GitHub issue when the issue chip is clicked", () => {
    render(<Home />);

    fireEvent.click(screen.getByRole("button", { name: "GitHub issue → implementation brief" }));

    const textarea = screen.getByLabelText("Describe what you want compiled") as HTMLTextAreaElement;
    expect(textarea.value.length).toBeGreaterThan(0);
    expect(
      "bug: export button doesnt work on safari??? users complaining in slack, cant repro locally on chrome tho. might be related to the blob download thing we added last sprint. someone said it also happens on firefox mobile sometimes. need this fixed before the friday release, no repro steps written down anywhere sorry",
    ).toContain(textarea.value);
  });

  it("fills the prompt with a messy PR description when the PR chip is clicked", () => {
    render(<Home />);

    fireEvent.click(screen.getByRole("button", { name: "PR description → review checklist" }));

    const textarea = screen.getByLabelText("Describe what you want compiled") as HTMLTextAreaElement;
    expect(textarea.value.length).toBeGreaterThan(0);
    expect(
      "fixes the thing where auth tokens expire too early. changed the refresh logic in useAuth.ts and also touched the login page a bit bc it kept throwing an error. didnt write tests yet, will add if reviewers want. also bumped a couple deps while i was in there, hope thats fine",
    ).toContain(textarea.value);
  });

  it("fills the prompt with a messy spec when the spec chip is clicked", () => {
    render(<Home />);

    fireEvent.click(screen.getByRole("button", { name: "Spec → implementation plan" }));

    const textarea = screen.getByLabelText("Describe what you want compiled") as HTMLTextAreaElement;
    expect(textarea.value.length).toBeGreaterThan(0);
    expect(
      "we need a notifications system. users should get emails and maybe push too. admins need to be able to turn it off per user. should probably use some kind of queue so it doesnt slow down the main app but not sure which one, also needs to somehow work with the mobile app",
    ).toContain(textarea.value);
  });
});
