import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import RagSearchPanel from "../context/RagSearchPanel";

describe("RagSearchPanel", () => {
  it("disables the search action for whitespace-only queries", () => {
    render(
      <RagSearchPanel
        query="   "
        setQuery={vi.fn()}
        searching={false}
        results={[]}
        onRunSearch={vi.fn()}
        onInsertContext={vi.fn()}
      />,
    );

    const button = screen.getByRole("button", { name: "Search" });
    expect(button.hasAttribute("disabled")).toBe(true);
  });

  it("runs search on Enter and inserts formatted context safely", () => {
    const onRunSearch = vi.fn();
    const onInsertContext = vi.fn();
    const onSubmit = vi.fn((event: SubmitEvent) => event.preventDefault());

    render(
      <form onSubmit={onSubmit}>
        <RagSearchPanel
          query="auth flow"
          setQuery={vi.fn()}
          searching={false}
          results={[
            {
              path: "src/auth.ts",
              snippet: "Handle session creation",
              score: 0.8123,
            },
          ]}
          onRunSearch={onRunSearch}
          onInsertContext={onInsertContext}
        />
      </form>,
    );

    fireEvent.keyDown(screen.getByLabelText("Search context..."), { key: "Enter" });
    expect(onRunSearch).toHaveBeenCalledTimes(1);

    const insertButton = screen.getByRole("button", { name: /insert into prompt/i });
    fireEvent.click(insertButton);

    expect(insertButton.getAttribute("type")).toBe("button");
    expect(onInsertContext).toHaveBeenCalledWith("[Source: src/auth.ts]\nHandle session creation");
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
