import React, { useState, useRef, useEffect, useId } from "react";

export interface PremiumSelectOption {
  value: string;
  label: string;
  description?: string;
  group?: string;
}

export interface PremiumSelectProps {
  id?: string;
  value: string;
  onChange: (value: string) => void;
  options: PremiumSelectOption[];
  placeholder?: string;
  focusVariant?: "blue" | "green" | "yellow" | "cyan" | "default";
  containerClassName?: string;
  selectClassName?: string;
  disabled?: boolean;
  "aria-label"?: string;
}

const variantStyles = {
  blue: "focus-visible:ring-blue-500/50 focus-visible:border-blue-500/50 border-white/10 hover:border-white/20",
  green: "focus-visible:ring-emerald-500/50 focus-visible:border-emerald-500/50 border-white/10 hover:border-white/20",
  yellow: "focus-visible:ring-amber-500/50 focus-visible:border-amber-500/50 border-white/10 hover:border-white/20",
  cyan: "focus-visible:ring-cyan-500/50 focus-visible:border-cyan-500/50 border-white/10 hover:border-white/20",
  default: "focus-visible:ring-zinc-500/50 focus-visible:border-zinc-500/50 border-white/10 hover:border-white/20",
};

export function PremiumSelect({
  id,
  value,
  onChange,
  options,
  placeholder = "Select an option...",
  focusVariant = "default",
  containerClassName = "",
  selectClassName = "",
  disabled = false,
  "aria-label": ariaLabel,
}: PremiumSelectProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const listboxId = useId();

  const selectedOption = options.find((opt) => opt.value === value);

  // Sync active index when dropdown opens
  useEffect(() => {
    if (isOpen) {
      const idx = options.findIndex((opt) => opt.value === value);
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setActiveIndex(idx >= 0 ? idx : 0);
    }
  }, [isOpen, value, options]);

  // Click outside to close
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleSelect = (val: string) => {
    onChange(val);
    setIsOpen(false);
    triggerRef.current?.focus();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLButtonElement>) => {
    if (disabled) return;

    if (e.key === "Enter" || e.key === " " || e.key === "Spacebar") {
      e.preventDefault();
      if (!isOpen) {
        setIsOpen(true);
      } else {
        if (options[activeIndex]) {
          handleSelect(options[activeIndex].value);
        }
      }
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      if (!isOpen) {
        setIsOpen(true);
      } else {
        setActiveIndex((prev) => (prev + 1) % options.length);
      }
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      if (!isOpen) {
        setIsOpen(true);
      } else {
        setActiveIndex((prev) => (prev - 1 + options.length) % options.length);
      }
    } else if (e.key === "Escape") {
      e.preventDefault();
      setIsOpen(false);
      triggerRef.current?.focus();
    } else if (e.key === "Tab") {
      setIsOpen(false);
    }
  };

  const focusClass = variantStyles[focusVariant];

  // Group options if group is specified
  const hasGroups = options.some((opt) => opt.group);

  // Helper to render options
  const renderOptionItem = (opt: PremiumSelectOption, index: number) => {
    const isSelected = opt.value === value;
    const isActive = index === activeIndex;
    const optionId = `${listboxId}-opt-${index}`;

    return (
      <li
        key={opt.value}
        id={optionId}
        role="option"
        aria-selected={isSelected}
        onClick={() => handleSelect(opt.value)}
        onMouseEnter={() => setActiveIndex(index)}
        className={`flex flex-col px-3 py-1.5 text-xs cursor-pointer select-none transition-colors ${
          isActive ? "bg-white/5 text-zinc-100" : "text-zinc-300"
        } ${isSelected ? "font-semibold text-emerald-400" : ""}`}
      >
        <div className="flex items-center justify-between">
          <span>{opt.label}</span>
          {isSelected && (
            <span className="text-emerald-400 text-[10px]" aria-hidden="true">
              ✓
            </span>
          )}
        </div>
        {opt.description && <span className="text-[10px] text-zinc-500 mt-0.5">{opt.description}</span>}
      </li>
    );
  };

  // Grouped render helper
  const renderOptions = () => {
    if (!hasGroups) {
      return options.map((opt, idx) => renderOptionItem(opt, idx));
    }

    // Accumulate groups
    const groups: { [key: string]: { opt: PremiumSelectOption; index: number }[] } = {};
    const noGroup: { opt: PremiumSelectOption; index: number }[] = [];

    options.forEach((opt, idx) => {
      if (opt.group) {
        if (!groups[opt.group]) groups[opt.group] = [];
        groups[opt.group].push({ opt, index: idx });
      } else {
        noGroup.push({ opt, index: idx });
      }
    });

    return (
      <>
        {noGroup.map(({ opt, index }) => renderOptionItem(opt, index))}
        {Object.keys(groups).map((groupName) => (
          <div key={groupName} role="group" aria-label={groupName}>
            <div className="text-[10px] font-mono uppercase tracking-wider text-zinc-500 px-3 py-1 bg-black/10 select-none">
              {groupName}
            </div>
            {groups[groupName].map(({ opt, index }) => renderOptionItem(opt, index))}
          </div>
        ))}
      </>
    );
  };

  const activeOptionId = isOpen && options[activeIndex] ? `${listboxId}-opt-${activeIndex}` : undefined;

  return (
    <div ref={containerRef} className={`relative w-full ${containerClassName}`}>
      <button
        id={id ? `${id}-btn` : undefined}
        ref={triggerRef}
        type="button"
        role="combobox"
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        aria-controls={listboxId}
        aria-activedescendant={activeOptionId}
        aria-label={ariaLabel}
        disabled={disabled}
        onKeyDown={handleKeyDown}
        onClick={() => !disabled && setIsOpen(!isOpen)}
        className={`w-full flex items-center justify-between cursor-pointer rounded-xl border bg-zinc-900/60 px-3 pr-9 py-2 text-xs text-zinc-200 transition-all hover:bg-zinc-900/80 focus:outline-none focus-visible:ring-2 disabled:opacity-50 disabled:cursor-not-allowed ${focusClass} ${selectClassName}`}
      >
        <span className="truncate">{selectedOption ? selectedOption.label : placeholder}</span>
        <span className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center text-zinc-400 pointer-events-none">
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
        </span>
      </button>

      {isOpen && options.length > 0 && (
        <ul
          id={listboxId}
          role="listbox"
          className="absolute left-0 mt-1 w-full z-50 bg-zinc-950/95 backdrop-blur-md border border-white/10 rounded-xl shadow-2xl py-1 max-h-60 overflow-y-auto focus:outline-none"
        >
          {renderOptions()}
        </ul>
      )}

      {/* Hidden native select for form state and test compatibility */}
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        tabIndex={-1}
        aria-hidden="true"
        className="absolute inset-0 opacity-0 pointer-events-none w-full h-full"
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  );
}

export default PremiumSelect;
