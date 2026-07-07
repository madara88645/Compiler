import { toast } from "sonner";

interface CopyToClipboardOptions {
  /** Toast message shown when the copy succeeds. */
  successMessage?: string;
  /** Toast message shown when the copy fails (e.g. unfocused tab, non-HTTPS context). */
  failureMessage?: string;
}

/**
 * Copies text to the clipboard and centralizes the success/failure toast.
 *
 * `navigator.clipboard.writeText` rejects in several real-world situations
 * (unfocused tab, non-HTTPS/insecure context, permission denied), so callers
 * must not assume the copy succeeded just because they called this function.
 * Only treat the copy as successful — e.g. flipping a "Copied!" checkmark
 * state — when this resolves to `true`.
 */
export async function copyToClipboard(
  text: string,
  options: CopyToClipboardOptions = {},
): Promise<boolean> {
  const {
    successMessage = "Copied to clipboard",
    failureMessage = "Copy failed — select the text manually",
  } = options;

  try {
    await navigator.clipboard.writeText(text);
    toast.success(successMessage);
    return true;
  } catch {
    toast.error(failureMessage);
    return false;
  }
}
