import { useEffect, useRef } from "react";

type FocusTarget = { id?: string; selector?: string };

/**
 * Shared "type an example in" effect. Mirrors the original page.tsx behavior:
 * ~0.65s total, length-independent, honors prefers-reduced-motion, cancellable.
 */
export function useTypewriterFill(
  setter: (value: string) => void,
  focusTarget?: FocusTarget,
) {
  const intervalRef = useRef<number | null>(null);

  const stop = () => {
    if (intervalRef.current !== null) {
      window.clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  };

  useEffect(() => stop, []);

  const focus = () => {
    if (!focusTarget) return;
    const el = focusTarget.id
      ? document.getElementById(focusTarget.id)
      : focusTarget.selector
        ? document.querySelector<HTMLElement>(focusTarget.selector)
        : null;
    el?.focus();
  };

  const fillExample = (text: string) => {
    stop();
    focus();
    const prefersReduced =
      typeof window !== "undefined" &&
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (prefersReduced) {
      setter(text);
      return;
    }
    setter("");
    const stepChars = Math.max(1, Math.ceil(text.length / 40)); // ~0.65s total, length-independent
    let i = 0;
    intervalRef.current = window.setInterval(() => {
      i = Math.min(text.length, i + stepChars);
      setter(text.slice(0, i));
      if (i >= text.length) stop();
    }, 16);
  };

  return { fillExample, stop };
}
