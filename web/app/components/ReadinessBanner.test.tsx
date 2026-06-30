import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ReadinessBanner, { VERDICT_META, READINESS_FOOTER } from "./ReadinessBanner";

describe("ReadinessBanner", () => {
  it("renders nothing when there is no report", () => {
    const { container } = render(<ReadinessBanner report={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows the verdict title, plain-language meaning, signal, question, footer, and dot", () => {
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
    expect(screen.getByText(VERDICT_META.clarify.meaning)).toBeInTheDocument();
    expect(screen.getByText(/couldn't be verified/i)).toBeInTheDocument();
    expect(screen.getByText(/real, documented tool/i)).toBeInTheDocument();
    expect(screen.getByText(READINESS_FOOTER)).toBeInTheDocument();
    expect(screen.getByTestId("readiness-dot")).toBeInTheDocument();
  });

  it("compact variant shows title and meaning but hides signals, questions, and footer", () => {
    render(
      <ReadinessBanner
        variant="compact"
        report={{
          verdict: "noise",
          signals: [{ kind: "noise", message: "Nothing actionable here." }],
          questions: ["What do you want to build?"],
        }}
      />,
    );
    expect(screen.getByText(VERDICT_META.noise.title)).toBeInTheDocument();
    expect(screen.getByText(VERDICT_META.noise.meaning)).toBeInTheDocument();
    expect(screen.queryByText(/nothing actionable here/i)).not.toBeInTheDocument();
    expect(screen.queryByText(READINESS_FOOTER)).not.toBeInTheDocument();
  });
});
