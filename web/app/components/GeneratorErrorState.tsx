"use client";

import { describeRequestError } from "@/config";

export type GeneratorErrorStateProps = {
  error: unknown;
  onRetry: () => void;
  title: string;
  retryLabel: string;
  reassurance?: string;
};

const DEFAULT_REASSURANCE =
  "Your description is still in the editor on the left. Try again — if it keeps failing, your connection or the generator service may be down.";

export default function GeneratorErrorState({
  error,
  onRetry,
  title,
  retryLabel,
  reassurance = DEFAULT_REASSURANCE,
}: GeneratorErrorStateProps) {
  return (
    <div className="flex flex-1 items-center justify-center p-10 text-center" role="alert">
      <div className="max-w-md rounded-lg border border-red-500/20 bg-red-500/10 p-6 shadow-xl shadow-red-950/10">
        <div className="mx-auto mb-4 flex h-10 w-10 items-center justify-center rounded-lg border border-red-400/30 bg-red-400/10 text-lg font-semibold text-red-200">
          !
        </div>
        <h3 className="text-base font-semibold text-white">{title}</h3>
        <p className="mt-2 text-sm leading-relaxed text-red-100/80">{describeRequestError(error)}</p>
        <p className="mt-3 text-xs leading-relaxed text-zinc-400">{reassurance}</p>
        <button
          type="button"
          onClick={onRetry}
          className="mt-5 rounded-lg border border-red-400/30 bg-red-500/20 px-4 py-2 text-sm font-medium text-red-50 transition-colors hover:bg-red-500/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400"
        >
          {retryLabel}
        </button>
      </div>
    </div>
  );
}
