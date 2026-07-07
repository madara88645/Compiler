import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import OfflinePage from "../offline/page";

const replaceMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace: replaceMock,
  }),
}));

describe("Offline route", () => {
  beforeEach(() => {
    replaceMock.mockReset();
  });

  it("redirects to the main Compiler page instead of duplicating it", () => {
    render(<OfflinePage />);

    expect(replaceMock).toHaveBeenCalledWith("/");
  });

  it("explains the move instead of claiming a separate local-only engine", () => {
    render(<OfflinePage />);

    expect(screen.getByText(/moved/i)).toBeTruthy();
    expect(screen.getByRole("link", { name: /go to the compiler/i })).toBeTruthy();
    // The old copy claimed "local-only" / "no API keys" while still calling the
    // network — make sure that misleading claim doesn't come back here.
    expect(screen.queryByText(/local-only/i)).toBeNull();
    expect(screen.queryByText(/no api keys/i)).toBeNull();
  });
});
