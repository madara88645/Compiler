import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import ContextSuggestions from "../context/ContextSuggestions";

describe("ContextSuggestions", () => {
  it("formats inserted context and does not submit surrounding forms", () => {
    const onInsertContext = vi.fn();
    const onSubmit = vi.fn((event: SubmitEvent) => event.preventDefault());

    render(
      <form onSubmit={onSubmit}>
        <ContextSuggestions
          suggestions={[
            {
              path: "src/app.ts",
              name: "app.ts",
              reason: "Entry point",
            },
          ]}
          onInsertContext={onInsertContext}
        />
      </form>,
    );

    const button = screen.getByRole("button", { name: /app\.ts/ });
    fireEvent.click(button);

    expect(button.getAttribute("type")).toBe("button");
    expect(onInsertContext).toHaveBeenCalledWith("[File: app.ts]\n(Reason: Entry point)");
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("returns null when no suggestions exist", () => {
    const { container } = render(<ContextSuggestions suggestions={[]} onInsertContext={vi.fn()} />);

    expect(container.firstChild).toBeNull();
  });
});
