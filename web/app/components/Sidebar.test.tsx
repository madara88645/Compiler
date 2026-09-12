import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { usePathname } from "next/navigation";
import { beforeEach, describe, expect, test, vi } from "vitest";

import Sidebar from "./Sidebar";

vi.mock("next/navigation", () => ({ usePathname: vi.fn() }));

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
    ...props
  }: React.PropsWithChildren<{ href: string } & React.AnchorHTMLAttributes<HTMLAnchorElement>>) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

describe("Sidebar", () => {
  const mockUsePathname = vi.mocked(usePathname);

  beforeEach(() => {
    mockUsePathname.mockReturnValue("/");
  });

  test("keeps prompt tools, repo checks, and external links available on prompt routes", () => {
    render(<Sidebar />);

    expect(screen.getByRole("group", { name: "Prompt tools" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Repo checks" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Compiler" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: "Token Optimizer" })).toHaveAttribute("href", "/optimizer");
    expect(screen.getByRole("link", { name: "Benchmark" })).toHaveAttribute("href", "/benchmark");
    expect(screen.getByRole("link", { name: "PR Safety" })).toHaveAttribute("href", "/pr-safety");
    expect(screen.getByRole("link", { name: "Compiler" })).toHaveAttribute("aria-current", "page");

    expect(screen.getByLabelText("GitHub repo")).toHaveAttribute(
      "href",
      "https://github.com/madara88645/Compiler",
    );
    expect(screen.getByLabelText("CLI install")).toHaveAttribute(
      "href",
      expect.stringContaining("docs/cli.md"),
    );
    expect(screen.getByLabelText("VS Code extension")).toHaveAttribute(
      "href",
      "https://github.com/madara88645/Compiler/blob/main/integrations/vscode-extension/README.md#install",
    );
    expect(screen.getByLabelText("MCP setup")).toHaveAttribute(
      "href",
      expect.stringContaining("integrations/mcp-server/README.md"),
    );
  });

  test("renders Agentic Coding as one keyboard-focusable collapsible trigger", () => {
    render(<Sidebar />);

    const trigger = screen.getByRole("button", { name: "Agentic Coding" });
    expect(trigger).toHaveAttribute("type", "button");
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(trigger).toHaveAttribute("aria-controls", "agentic-coding-navigation");
    expect(trigger).not.toHaveAttribute("href");
    expect(screen.queryByRole("link", { name: "Projects" })).not.toBeInTheDocument();

    trigger.focus();
    expect(document.activeElement).toBe(trigger);
  });

  test("shows only child links after opening and does not navigate when toggled", () => {
    render(<Sidebar />);

    const trigger = screen.getByRole("button", { name: "Agentic Coding" });
    fireEvent.click(trigger);

    expect(trigger).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("link", { name: "Projects" })).toHaveAttribute("href", "/agentic-coding");
    expect(screen.getByRole("link", { name: "Agent Generator" })).toHaveAttribute(
      "href",
      "/agentic-coding/agents",
    );
    expect(screen.getByRole("link", { name: "Skill Generator" })).toHaveAttribute(
      "href",
      "/agentic-coding/skills",
    );

    fireEvent.click(trigger);
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("link", { name: "Projects" })).not.toBeInTheDocument();
  });

  test.each([
    ["/agentic-coding", "Projects"],
    ["/agentic-coding/agents", "Agent Generator"],
    ["/agentic-coding/skills", "Skill Generator"],
    ["/agentic-coding/projects/export", "Projects"],
    ["/agent-packs", "Projects"],
    ["/agent-generator", "Agent Generator"],
    ["/skills-generator", "Skill Generator"],
  ])("auto-expands and marks %s active through %s", (pathname, label) => {
    mockUsePathname.mockReturnValue(pathname);
    const { unmount } = render(<Sidebar />);

    expect(screen.getByRole("button", { name: "Agentic Coding" })).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("link", { name: label })).toHaveAttribute("aria-current", "page");
    expect(screen.getAllByRole("link").filter((link) => link.getAttribute("aria-current") === "page")).toHaveLength(1);

    unmount();
  });

  test("auto-expands for future Agentic Coding routes without adding an instruction link", () => {
    mockUsePathname.mockReturnValue("/agentic-coding/instructions");
    render(<Sidebar />);

    expect(screen.getByRole("button", { name: "Agentic Coding" })).toHaveAttribute("aria-expanded", "true");
    expect(screen.queryByRole("link", { name: /instruction/i })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Projects" })).toHaveAttribute("aria-current", "page");
  });

  test("preserves a user toggle across rerenders and reopens when entering an active route", async () => {
    const { rerender } = render(<Sidebar />);
    const trigger = screen.getByRole("button", { name: "Agentic Coding" });

    fireEvent.click(trigger);
    expect(trigger).toHaveAttribute("aria-expanded", "true");
    rerender(<Sidebar />);
    expect(trigger).toHaveAttribute("aria-expanded", "true");

    fireEvent.click(trigger);
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    rerender(<Sidebar />);
    expect(trigger).toHaveAttribute("aria-expanded", "false");

    mockUsePathname.mockReturnValue("/agentic-coding/instructions");
    rerender(<Sidebar />);
    await waitFor(() => expect(trigger).toHaveAttribute("aria-expanded", "true"));
  });

  test("renders visible labels for every visible navigation icon", () => {
    render(<Sidebar />);
    fireEvent.click(screen.getByRole("button", { name: "Agentic Coding" }));

    for (const label of [
      "Prompt tools",
      "Compiler",
      "Token Optimizer",
      "Benchmark",
      "Agentic Coding",
      "Projects",
      "Agent Generator",
      "Skill Generator",
      "Repo checks",
      "PR Safety",
    ]) {
      expect(screen.getAllByText(label).length).toBeGreaterThan(0);
    }
  });

  test("renders outbound links with preserved new-tab behavior", () => {
    render(<Sidebar />);

    for (const label of ["GitHub repo", "CLI install", "VS Code extension", "MCP setup"]) {
      const external = screen.getByLabelText(label);
      expect(external).toHaveAttribute("target", "_blank");
      expect(external).toHaveAttribute("rel", "noopener noreferrer");
    }
  });
});
