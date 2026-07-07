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

  test("renders a visible text label under every icon", () => {
    render(<Sidebar />);

    const labels = [
      "Compiler",
      "Optimizer",
      "Offline",
      "Benchmark",
      "PR Safety",
      "Agent Packs",
      "Agent Generator",
      "Skills Generator",
    ];

    for (const label of labels) {
      // getByLabelText matches the link's aria-label; getAllByText also
      // matches the visible <span> rendered under the icon.
      expect(screen.getAllByText(label).length).toBeGreaterThan(0);
    }
  });

  test("groups nav items into labeled sections with separators between them", () => {
    render(<Sidebar />);

    const groups = screen.getAllByRole("group");
    const groupLabels = groups.map((group) => group.getAttribute("aria-label"));

    expect(groupLabels).toEqual([
      "Compile",
      "Prove",
      "Ship agent assets",
      "Repo checks",
    ]);

    // One separator between each pair of groups.
    const separators = screen.getAllByRole("separator");
    expect(separators).toHaveLength(groups.length - 1);
  });

  test("keeps Compiler as the first item in the primary Compile group", () => {
    render(<Sidebar />);

    const compileGroup = screen.getByRole("group", { name: "Compile" });
    const firstLink = compileGroup.querySelector("a");
    expect(firstLink?.getAttribute("aria-label")).toBe("Compiler");
    expect(firstLink?.getAttribute("href")).toBe("/");
  });
});
