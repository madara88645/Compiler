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

  it("focuses the search input on a single mouse click", () => {
    render(
      <RagSearchPanel
        query=""
        setQuery={vi.fn()}
        searching={false}
        results={[]}
        onRunSearch={vi.fn()}
        onInsertContext={vi.fn()}
      />,
    );

    const input = screen.getByLabelText("Search context...");
    expect(document.activeElement).not.toBe(input);

    fireEvent.click(input);

    // Clicking must focus the input so the user can type immediately,
    // without first pressing Tab (issue #762).
    expect(document.activeElement).toBe(input);
  });

  it("does not insert any result into the prompt just from rendering search results", () => {
    const onInsertContext = vi.fn();

    render(
      <RagSearchPanel
        query="auth flow"
        setQuery={vi.fn()}
        searching={false}
        results={[
          { path: "src/auth.ts", snippet: "Handle session creation", score: 0.8123 },
          { path: "src/session.ts", snippet: "Refresh tokens", score: 0.71 },
        ]}
        onRunSearch={vi.fn()}
        onInsertContext={onInsertContext}
      />,
    );

    // Results render but nothing is auto-inserted into the prompt.
    expect(screen.getByText("Handle session creation")).toBeTruthy();
    expect(onInsertContext).not.toHaveBeenCalled();
  });

  it("only updates the prompt when an explicit Insert button is clicked", () => {
    const onInsertContext = vi.fn();

    render(
      <RagSearchPanel
        query="auth flow"
        setQuery={vi.fn()}
        searching={false}
        results={[
          { path: "src/auth.ts", snippet: "Handle session creation", score: 0.8123 },
        ]}
        onRunSearch={vi.fn()}
        onInsertContext={onInsertContext}
      />,
    );

    expect(onInsertContext).not.toHaveBeenCalled();

    const insertButton = screen.getByRole("button", {
      name: /insert snippet from src\/auth\.ts into prompt/i,
    });
    fireEvent.click(insertButton);

    expect(onInsertContext).toHaveBeenCalledTimes(1);
    expect(onInsertContext).toHaveBeenCalledWith("[Source: src/auth.ts]\nHandle session creation");
  });

  it("strips search-highlight brackets when inserting a snippet into the prompt", () => {
    const onInsertContext = vi.fn();

    render(
      <RagSearchPanel
        query="launch date"
        setQuery={vi.fn()}
        searching={false}
        results={[
          { path: "docs/launch.md", snippet: "The [launch] [date] is confirmed", score: 0.5 },
        ]}
        onRunSearch={vi.fn()}
        onInsertContext={onInsertContext}
      />,
    );

    // The on-screen result keeps the highlighted snippet…
    expect(screen.getByText("The [launch] [date] is confirmed")).toBeTruthy();

    fireEvent.click(
      screen.getByRole("button", { name: /insert snippet from docs\/launch\.md into prompt/i }),
    );

    // …but the inserted prompt text is clean (issue #773).
    expect(onInsertContext).toHaveBeenCalledWith(
      "[Source: docs/launch.md]\nThe launch date is confirmed",
    );
  });

  it("shows a clear no-results state when a query returns nothing", () => {
    render(
      <RagSearchPanel
        query="nonexistent"
        setQuery={vi.fn()}
        searching={false}
        results={[]}
        onRunSearch={vi.fn()}
        onInsertContext={vi.fn()}
      />,
    );

    expect(screen.getByText(/No results found for/i)).toBeTruthy();
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

    const insertButton = screen.getByRole("button", { name: /insert snippet from src\/auth\.ts into prompt/i });
    fireEvent.click(insertButton);

    expect(insertButton.getAttribute("type")).toBe("button");
    expect(onInsertContext).toHaveBeenCalledWith("[Source: src/auth.ts]\nHandle session creation");
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
