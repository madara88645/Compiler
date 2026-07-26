import re
with open("web/app/pr-safety/page.tsx", "r") as f:
    content = f.read()

# Add missingFields calculation
old_can_submit = """  const canSubmit =
    title.trim().length > 0 &&
    description.trim().length > 0 &&
    parsedFiles.length > 0 &&
    !loading;"""

new_can_submit = """  const canSubmit =
    title.trim().length > 0 &&
    description.trim().length > 0 &&
    parsedFiles.length > 0 &&
    !loading;

  const missingFields = [];
  if (!title.trim()) missingFields.push("Title");
  if (!description.trim()) missingFields.push("Description");
  if (parsedFiles.length === 0) missingFields.push("Changed files");
  const missingFieldsText = missingFields.length > 0 ? `Missing: ${missingFields.join(", ")}` : "";"""

content = content.replace(old_can_submit, new_can_submit)

# Update the button title attribute
old_button = """            <button
              type="button"
              onClick={handleAnalyze}
              disabled={!canSubmit}
              aria-busy={loading}
              title={!canSubmit ? "Fill in all fields to analyze PR" : "Analyze PR"}"""

new_button = """            <button
              type="button"
              onClick={handleAnalyze}
              disabled={!canSubmit}
              aria-busy={loading}
              title={!canSubmit ? missingFieldsText || "Analyze PR" : "Analyze PR"}"""

content = content.replace(old_button, new_button)

with open("web/app/pr-safety/page.tsx", "w") as f:
    f.write(content)
