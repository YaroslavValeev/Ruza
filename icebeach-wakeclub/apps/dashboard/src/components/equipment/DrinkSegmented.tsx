import { KeyboardEvent, useRef } from "react";

import { DRINK_OPTIONS } from "../../lib/equipment";
import type { DrinkChoice } from "../../types";

type Props = {
  value: DrinkChoice | "";
  onChange: (value: DrinkChoice | "") => void;
  labelId: string;
  disabled?: boolean;
};

/** Напиток: Кофе / Шоколад / Не нужно. Повторное нажатие снимает выбор. Стрелки ←/→ переключают. */
export function DrinkSegmented({ value, onChange, labelId, disabled }: Props): JSX.Element {
  const refs = useRef<Array<HTMLButtonElement | null>>([]);
  const currentIndex = Math.max(DRINK_OPTIONS.findIndex((option) => option.value === value), 0);

  function onKeyDown(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
    event.preventDefault();
    const delta = event.key === "ArrowRight" ? 1 : -1;
    const next = (index + delta + DRINK_OPTIONS.length) % DRINK_OPTIONS.length;
    onChange(DRINK_OPTIONS[next].value);
    refs.current[next]?.focus();
  }

  return (
    <div role="radiogroup" aria-labelledby={labelId} className="grid grid-cols-3 gap-1.5">
      {DRINK_OPTIONS.map((option, index) => {
        const checked = option.value === value;
        return (
          <button
            key={option.value}
            ref={(node) => {
              refs.current[index] = node;
            }}
            type="button"
            role="radio"
            aria-checked={checked}
            tabIndex={index === currentIndex ? 0 : -1}
            disabled={disabled}
            onClick={() => onChange(checked ? "" : option.value)}
            onKeyDown={(event) => onKeyDown(event, index)}
            className={`min-h-12 rounded-2xl border px-2 text-sm font-bold transition focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-[rgba(14,110,98,0.22)] ${
              checked
                ? "border-2 border-[color:var(--accent)] bg-[color:var(--accent-soft)] text-[color:var(--accent)]"
                : "border-[color:var(--border)] bg-[#FFFCFA] text-[color:var(--ink)] hover:border-[color:var(--accent-border)]"
            }`}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
