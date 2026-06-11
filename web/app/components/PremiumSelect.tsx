import React, { forwardRef } from "react";

export interface PremiumSelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  containerClassName?: string;
  selectClassName?: string;
  focusVariant?: "blue" | "green" | "yellow" | "cyan" | "default";
}

const variantStyles = {
  blue: "focus:ring-blue-500/50 focus:border-blue-500/50",
  green: "focus:ring-emerald-500/50 focus:border-emerald-500/50",
  yellow: "focus:ring-amber-500/50 focus:border-amber-500/50",
  cyan: "focus:ring-cyan-500/50 focus:border-cyan-500/50",
  default: "focus:ring-zinc-500/50 focus:border-zinc-500/50",
};

export const PremiumSelect = forwardRef<HTMLSelectElement, PremiumSelectProps>(
  (
    {
      children,
      containerClassName = "",
      selectClassName = "",
      focusVariant = "default",
      disabled,
      className, // Deprecated in favor of selectClassName but merged if passed
      ...props
    },
    ref
  ) => {
    const focusClass = variantStyles[focusVariant];

    return (
      <div className={`relative w-full ${containerClassName}`}>
        <select
          ref={ref}
          disabled={disabled}
          className={`w-full appearance-none cursor-pointer rounded-xl border border-white/10 bg-zinc-900/60 px-3 pr-9 py-2 text-xs text-zinc-200 transition-all hover:bg-zinc-900/80 hover:border-white/20 focus:outline-none focus:ring-2 disabled:opacity-50 disabled:cursor-not-allowed ${focusClass} ${selectClassName} ${className || ""}`}
          {...props}
        >
          {children}
        </select>
        <div className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 flex items-center text-zinc-400">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="m6 9 6 6 6-6" />
          </svg>
        </div>
      </div>
    );
  }
);

PremiumSelect.displayName = "PremiumSelect";
export default PremiumSelect;
