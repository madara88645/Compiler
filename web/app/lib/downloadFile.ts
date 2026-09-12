/**
 * Triggers a browser download of `content` as a file named `filename`.
 *
 * Shared by any page that offers a "download this output" action (e.g. the
 * compile result tabs, the PR Safety report) so there is a single
 * anchor+Blob implementation instead of one copy per page.
 */
export function downloadFile(
  content: string | Blob,
  filename: string,
  mimeType: string = "text/plain",
): void {
  const blob = content instanceof Blob ? content : new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  // Let the browser consume the download before releasing the blob URL.
  // Revoking it in the click's task can cancel downloads in some browsers.
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
