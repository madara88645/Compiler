import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import PrSafetyPage from "./page";

const { apiJson } = vi.hoisted(() => ({
  apiJson: vi.fn(),
}));

const { showError } = vi.hoisted(() => ({
  showError: vi.fn(),
}));

vi.mock("@/config", () => ({
  apiJson,
  buildGeneratorApiHeaders: (headers: HeadersInit = {}) => headers,
  describeRequestError: (error: unknown) =>
    error instanceof Error ? error.message : "Connection failed.",
}));

vi.mock("../lib/showError", () => ({
  showError,
}));

const SAMPLE_REPORT = {
  verdict: "hold",
  title: "Add login endpoint",
  changed_files: {
    total: 2,
    groups: [
      { name: "auth", files: ["app/auth/login.py", "app/auth/session.py"] },
    ],
  },
  risky_areas: {
    status: "hit",
    hits: [
      {
        category: "auth",
        file: "app/auth/login.py",
        reason: "Touches authentication logic",
      },
    ],
  },
  test_coverage: {
    status: "gap",
    gaps: [
      {
        file: "app/auth/login.py",
        reason: "Source file changed without a matching test file in this PR",
      },
    ],
    test_files: [],
  },
  branch_freshness: {
    status: "ok",
    commits_behind: 2,
    notes: ["Branch is 2 commits behind the base branch"],
  },
  scope_match: { status: "ok", notes: [] },
  recommendations: [
    "Hold merge until the flagged safety signals are addressed",
    "Add or update tests covering `app/auth/login.py`",
  ],
};

function fillRequiredFields() {
  fireEvent.change(screen.getByLabelText("PR Title"), {
    target: { value: "Add login endpoint" },
  });
  fireEvent.change(screen.getByLabelText("PR Description"), {
    target: { value: "Adds POST /login" },
  });
  fireEvent.change(screen.getByLabelText("Changed Files"), {
    target: { value: "app/auth/login.py\napp/auth/session.py\n  \n" },
  });
}

describe("PR Safety page", () => {
  beforeEach(() => {
    apiJson.mockReset();
    showError.mockReset();
    apiJson.mockResolvedValue(SAMPLE_REPORT);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  test("renders the paste form fields", () => {
    render(<PrSafetyPage />);

    expect(screen.getByLabelText("PR Title")).toBeTruthy();
    expect(screen.getByLabelText("PR Description")).toBeTruthy();
    expect(screen.getByLabelText("Changed Files")).toBeTruthy();
    expect(screen.getByLabelText("Commits Behind")).toBeTruthy();
    expect(screen.getByRole("button", { name: /analyze pr/i })).toBeTruthy();
  });

  test("keeps Analyze disabled until required fields are filled", () => {
    render(<PrSafetyPage />);

    const button = screen.getByRole("button", { name: /analyze pr/i }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);

    fillRequiredFields();

    expect(button.disabled).toBe(false);
  });

  test("submits the parsed report request", async () => {
    render(<PrSafetyPage />);

    fillRequiredFields();
    fireEvent.change(screen.getByLabelText("Commits Behind"), {
      target: { value: "12" },
    });
    fireEvent.click(screen.getByRole("button", { name: /analyze pr/i }));

    await waitFor(() => expect(apiJson).toHaveBeenCalledTimes(1));

    const [path, options] = apiJson.mock.calls[0];
    expect(path).toBe("/pr-safety/report");
    expect(options.method).toBe("POST");

    const body = JSON.parse(options.body);
    expect(body.title).toBe("Add login endpoint");
    expect(body.description).toBe("Adds POST /login");
    expect(body.changed_files).toEqual(["app/auth/login.py", "app/auth/session.py"]);
    expect(body.commits_behind).toBe(12);
  });

  test("omits commits_behind when the field is left blank", async () => {
    render(<PrSafetyPage />);

    fillRequiredFields();
    fireEvent.click(screen.getByRole("button", { name: /analyze pr/i }));

    await waitFor(() => expect(apiJson).toHaveBeenCalledTimes(1));

    const body = JSON.parse(apiJson.mock.calls[0][1].body);
    expect("commits_behind" in body).toBe(false);
  });

  test("renders every report section from the API response", async () => {
    render(<PrSafetyPage />);

    fillRequiredFields();
    fireEvent.click(screen.getByRole("button", { name: /analyze pr/i }));

    expect((await screen.findByTestId("pr-verdict")).textContent).toMatch(/hold/i);
    // changed file group label
    expect(screen.getAllByText("auth").length).toBeGreaterThan(0);
    // risky area reason
    expect(screen.getByText("Touches authentication logic")).toBeTruthy();
    // test coverage gap reason
    expect(screen.getByText(/without a matching test file/i)).toBeTruthy();
    // branch freshness note
    expect(screen.getByText("Branch is 2 commits behind the base branch")).toBeTruthy();
    // recommendation
    expect(
      screen.getByText("Hold merge until the flagged safety signals are addressed"),
    ).toBeTruthy();
  });

  test("surfaces request failures through showError", async () => {
    apiJson.mockRejectedValueOnce(new Error("Failed to fetch"));

    render(<PrSafetyPage />);

    fillRequiredFields();
    fireEvent.click(screen.getByRole("button", { name: /analyze pr/i }));

    await waitFor(() => expect(showError).toHaveBeenCalledTimes(1));
  });
});
