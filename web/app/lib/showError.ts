import { toast } from "sonner";
import { describeRequestError } from "../../config";

export function showError(error: unknown): void {
  toast.error(describeRequestError(error));
}
