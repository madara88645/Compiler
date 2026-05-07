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
});
