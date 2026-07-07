/**
 * Triggers a browser download of `content` as a file named `filename`.
 *
 * Shared by any page that offers a "download this output" action (e.g. the
 * compile result tabs, the PR Safety report) so there is a single
 * anchor+Blob implementation instead of one copy per page.
 */
export function downloadFile(
  content: string,
  filename: string,
  mimeType: string = "text/plain",
): void {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
