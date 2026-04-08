import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import UploadProgressCard from "../context/UploadProgressCard";

describe("UploadProgressCard", () => {
  it("renders the current file and computed progress", () => {
    const { container } = render(
      <UploadProgressCard
        uploadProgress={{
          completed: 2,
          currentFile: "src/index.ts",
          total: 5,
        }}
      />,
    );

    expect(screen.getByText("Uploading context")).toBeTruthy();
    expect(screen.getByText("3/5")).toBeTruthy();
    expect(screen.getByText("src/index.ts")).toBeTruthy();

    const progressBar = container.querySelector('[style="width: 49%;"]');
    expect(progressBar).toBeTruthy();
  });
});
