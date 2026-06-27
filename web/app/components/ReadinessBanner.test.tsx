import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ReadinessBanner from "./ReadinessBanner";

describe("ReadinessBanner", () => {
  it("renders nothing when there is no report", () => {
    const { container } = render(<ReadinessBanner report={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows the verdict title and a clarification question", () => {
    render(
      <ReadinessBanner
        report={{
          verdict: "clarify",
          signals: [{ kind: "unverifiable_reference", message: "'AcmeCloud SDK' couldn't be verified." }],
          questions: ["Is 'AcmeCloud SDK' a real, documented tool?"],
        }}
      />,
    );
    expect(screen.getByText(/clarify before compiling/i)).toBeInTheDocument();
    expect(screen.getByText(/couldn't be verified/i)).toBeInTheDocument();
    expect(screen.getByText(/real, documented tool/i)).toBeInTheDocument();
  });
});
