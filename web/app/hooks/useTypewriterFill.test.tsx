import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useState } from "react";

import { useTypewriterFill } from "./useTypewriterFill";

function Harness({ text }: { text: string }) {
  const [val, setVal] = useState("");
  const { fillExample } = useTypewriterFill(setVal, { id: "harness-input" });
  return (
    <>
      <textarea id="harness-input" aria-label="harness" value={val} readOnly />
      <button onClick={() => fillExample(text)}>fill</button>
    </>
  );
}

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
  // @ts-expect-error test cleanup of the matchMedia stub
  delete window.matchMedia;
});

describe("useTypewriterFill", () => {
  it("fills instantly when prefers-reduced-motion is set", () => {
    window.matchMedia = vi.fn().mockReturnValue({ matches: true }) as unknown as typeof window.matchMedia;
    render(<Harness text="hello world" />);

    fireEvent.click(screen.getByText("fill"));

    expect((screen.getByLabelText("harness") as HTMLTextAreaElement).value).toBe("hello world");
  });

  it("types the full text over the interval when motion is allowed", () => {
    vi.useFakeTimers();
    // no matchMedia -> guard is false -> animate
    render(<Harness text="abcdefghij" />);

    fireEvent.click(screen.getByText("fill"));
    act(() => {
      vi.advanceTimersByTime(16);
    });
    const mid = (screen.getByLabelText("harness") as HTMLTextAreaElement).value;
    expect(mid.length).toBeLessThan("abcdefghij".length);

    act(() => {
      vi.runAllTimers();
    });
    expect((screen.getByLabelText("harness") as HTMLTextAreaElement).value).toBe("abcdefghij");
  });

  it("focuses the target element", () => {
    window.matchMedia = vi.fn().mockReturnValue({ matches: true }) as unknown as typeof window.matchMedia;
    render(<Harness text="x" />);

    fireEvent.click(screen.getByText("fill"));

    expect(document.activeElement).toBe(screen.getByLabelText("harness"));
  });
});
