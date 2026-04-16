import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import ToastProvider from "../ToastProvider";

describe("ToastProvider", () => {
  it("renders without crashing", () => {
    const { container } = render(<ToastProvider />);
    expect(container).toBeTruthy();
  });
});
