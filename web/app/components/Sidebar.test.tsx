import { render, screen } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";
import { usePathname } from "next/navigation";

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

  test("renders canonical navigation links in understandable groups", () => {
    mockUsePathname.mockReturnValue("/agentic-coding");
    render(<Sidebar />);

    const links = {
      Compiler: "/",
      "Token Optimizer": "/optimizer",
      Benchmark: "/benchmark",
      Projects: "/agentic-coding",
      Agents: "/agentic-coding/agents",
      "Skills & Tools": "/agentic-coding/skills",
      "PR Safety": "/pr-safety",
    };

    for (const [label, href] of Object.entries(links)) {
      expect(screen.getByRole("link", { name: label }).getAttribute("href")).toBe(href);
    }

    expect(screen.getByRole("link", { name: "Projects" }).getAttribute("aria-current")).toBe("page");
  });

  test("does not render a separate Offline navigation item", () => {
    render(<Sidebar />);

    // The heuristics-only engine moved into the main Compiler page as a
    // toggle; the standalone /offline surface no longer exists in the nav.
    expect(screen.queryByLabelText("Offline")).toBeNull();
  });

  test("renders a visible text label under every icon", () => {
    mockUsePathname.mockReturnValue("/");
    render(<Sidebar />);

    const labels = [
      "Compiler",
      "Token Optimizer",
      "Benchmark",
      "PR Safety",
      "Projects",
      "Agents",
      "Skills & Tools",
    ];

    for (const label of labels) {
      // getByLabelText matches the link's aria-label; getAllByText also
      // matches the visible <span> rendered under the icon.
      expect(screen.getAllByText(label).length).toBeGreaterThan(0);
    }
  });

  test("groups nav items into labeled sections with separators between them", () => {
    mockUsePathname.mockReturnValue("/");
    render(<Sidebar />);

    const groups = screen.getAllByRole("group");
    const groupLabels = groups.map((group) => group.getAttribute("aria-label"));

    expect(groupLabels).toEqual([
      "Prompt tools",
      "Agentic Coding",
      "Repo checks",
    ]);

    // One separator between each pair of groups.
    const separators = screen.getAllByRole("separator");
    expect(separators).toHaveLength(groups.length - 1);
  });

  test("keeps Compiler as the first item in the primary Prompt tools group", () => {
    mockUsePathname.mockReturnValue("/");
    render(<Sidebar />);

    const promptToolsGroup = screen.getByRole("group", { name: "Prompt tools" });
    const firstLink = promptToolsGroup.querySelector("a");
    expect(firstLink?.getAttribute("aria-label")).toBe("Compiler");
    expect(firstLink?.getAttribute("href")).toBe("/");
  });

  test.each([
    ["/agentic-coding", "Projects"],
    ["/agent-packs", "Projects"],
    ["/agentic-coding/projects/export", "Projects"],
    ["/agentic-coding/agents", "Agents"],
    ["/agent-generator", "Agents"],
    ["/agentic-coding/skills", "Skills & Tools"],
    ["/skills-generator", "Skills & Tools"],
  ])("marks %s as %s for canonical and legacy routes", (pathname, label) => {
    mockUsePathname.mockReturnValue(pathname);
    const { unmount } = render(<Sidebar />);

    expect(screen.getByRole("link", { name: label }).getAttribute("aria-current")).toBe("page");
    expect(screen.getAllByRole("link").filter((link) => link.getAttribute("aria-current") === "page")).toHaveLength(1);

    unmount();
  });

  test("renders outbound links for repo, CLI, VS Code, and MCP", () => {
    render(<Sidebar />);

    expect(screen.getByLabelText("GitHub repo").getAttribute("href")).toBe(
      "https://github.com/madara88645/Compiler",
    );
    expect(screen.getByLabelText("CLI install").getAttribute("href")).toContain("docs/cli.md");
    expect(screen.getByLabelText("VS Code extension").getAttribute("href")).toBe(
      "https://github.com/madara88645/Compiler/blob/main/integrations/vscode-extension/README.md#install",
    );
    expect(screen.getByLabelText("MCP setup").getAttribute("href")).toContain(
      "integrations/mcp-server/README.md",
    );

    for (const label of ["GitHub repo", "CLI install", "VS Code extension", "MCP setup"]) {
      const external = screen.getByLabelText(label);
      expect(external.getAttribute("target")).toBe("_blank");
      expect(external.getAttribute("rel")).toBe("noopener noreferrer");
    }
  });
});
