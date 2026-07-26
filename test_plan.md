1. **Identify the UX Opportunity**: Looking across the various Next.js pages (like `pr-safety/page.tsx`, `agent-generator/page.tsx`, `page.tsx`, `benchmark/page.tsx`, etc.), I found that many primary action buttons (like "Analyze PR", "Generate Agent", "Compile Prompt") become disabled based on certain conditions. Most of these disabled buttons have a static `title` attribute like `title={!canSubmit ? "Fill in all fields to analyze PR" : "Analyze PR"}` or `title={!prompt.trim() ? "Enter a prompt first to compile" : "Compile Prompt"}`. These existing titles are good, but for forms with *multiple* fields (like the PR Safety form, which requires Title, Description, and Changed Files), a static "Fill in all fields" is generic and doesn't tell the user *which* specific field is missing.

2. **Select the Best Micro-UX Improvement**: I will improve the disabled state feedback on the `pr-safety/page.tsx` "Analyze PR" button. Instead of a generic "Fill in all fields to analyze PR", I will dynamically calculate exactly which fields are missing (e.g., "Missing: title", "Missing: description, changed files") and display that in the `title` attribute when the button is disabled. This provides immediate, specific, and actionable feedback to the user, enhancing accessibility and reducing friction. This is a perfect micro-UX improvement (< 50 lines, high impact, no new dependencies).

3. **Modify `web/app/pr-safety/page.tsx`**:
   - Add a small helper calculation before the return statement to determine the missing fields:
     ```tsx
     const missingFields = [];
     if (!title.trim()) missingFields.push("Title");
     if (!description.trim()) missingFields.push("Description");
     if (parsedFiles.length === 0) missingFields.push("Changed files");
     const missingFieldsText = missingFields.length > 0 ? `Missing: ${missingFields.join(", ")}` : "";
     ```
   - Update the `title` attribute of the "Analyze PR" button:
     ```tsx
     title={!canSubmit ? missingFieldsText || "Analyze PR" : "Analyze PR"}
     ```

4. **Verify the Changes**:
   - Run `pnpm run format` and `pnpm run lint` in the `web` directory.
   - Run `pnpm test` in the `web` directory.
   - Run `pnpm run build` to verify the build completes successfully.

5. **Create a PR**:
   - Use `gh pr create` with the required Palette format.
