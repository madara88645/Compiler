import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { Skeleton, SkeletonBlock } from "../Skeleton";

describe("Skeleton", () => {
  it("renders with skeleton class", () => {
    const { container } = render(<Skeleton />);
    const el = container.firstChild as HTMLElement;
    expect(el.classList.contains("skeleton")).toBe(true);
  });

  it("applies custom className", () => {
    const { container } = render(<Skeleton className="h-4 w-full" />);
    const el = container.firstChild as HTMLElement;
    expect(el.classList.contains("h-4")).toBe(true);
    expect(el.classList.contains("w-full")).toBe(true);
  });
});

describe("SkeletonBlock", () => {
  it("renders the specified number of lines", () => {
    const { container } = render(<SkeletonBlock lines={3} />);
    const skeletons = container.querySelectorAll(".skeleton");
    expect(skeletons.length).toBe(3);
  });

  it("defaults to 5 lines", () => {
    const { container } = render(<SkeletonBlock />);
    const skeletons = container.querySelectorAll(".skeleton");
    expect(skeletons.length).toBe(5);
  });
});
