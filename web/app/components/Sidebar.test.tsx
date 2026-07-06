import { render, screen } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";

import Sidebar from "./Sidebar";

vi.mock("next/navigation", () => ({
  usePathname: () => "/agent-packs",
}));

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
  test("renders Agent Packs as a top-level navigation item", () => {
    render(<Sidebar />);

    const link = screen.getByLabelText("Agent Packs");
    expect(link.getAttribute("href")).toBe("/agent-packs");
    expect(link.getAttribute("aria-current")).toBe("page");
  });

  test("renders outbound links for repo, CLI, VS Code, and MCP", () => {
    render(<Sidebar />);

    expect(screen.getByLabelText("GitHub repo").getAttribute("href")).toBe(
      "https://github.com/madara88645/Compiler",
    );
    expect(screen.getByLabelText("CLI install").getAttribute("href")).toContain("docs/cli.md");
    expect(screen.getByLabelText("VS Code extension").getAttribute("href")).toContain(
      "madara88645.promptc-vscode",
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
