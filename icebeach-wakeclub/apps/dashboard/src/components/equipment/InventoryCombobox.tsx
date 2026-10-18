import { KeyboardEvent, useId, useMemo, useRef, useState } from "react";

export type ComboOption = {
  value: string;
  label: string;
  /** Короткая подсказка справа: «по брони», «выведен». */
  hint?: string;
  /** Текст для поиска: номер, название, размер. */
  keywords: string;
};

type Props = {
  id: string;
  label: string;
  options: ComboOption[];
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  emptyLabel?: string;
  disabled?: boolean;
};

function normalize(text: string): string {
  return text.toLowerCase().replace(/ё/g, "е").replace(/№/g, "").replace(/\s+/g, " ").trim();
}

/**
 * Поиск по номеру или названию с выпадающим списком (ARIA combobox).
 * Клавиатура: ↓/↑ — выбор, Enter — подтвердить, Esc — закрыть.
 */
export function InventoryCombobox({ id, label, options, value, onChange, placeholder = "№ или название", emptyLabel = "Не выдавать", disabled }: Props): JSX.Element {
  const listId = useId();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const selected = options.find((option) => option.value === value) ?? null;
  const items = useMemo(() => {
    const q = normalize(query);
    const all: ComboOption[] = [{ value: "", label: emptyLabel, keywords: "" }, ...options];
    if (!q) return all;
    const matched = options.filter((option) => normalize(`${option.keywords} ${option.label}`).includes(q));
    // Точное совпадение номера — первым.
    matched.sort((a, b) => Number(normalize(b.keywords).split(" ")[0] === q) - Number(normalize(a.keywords).split(" ")[0] === q));
    return matched;
  }, [emptyLabel, options, query]);

  function choose(option: ComboOption | undefined) {
    if (!option) return;
    onChange(option.value);
    setOpen(false);
    setQuery("");
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      if (!open) setOpen(true);
      setActive((index) => Math.min(index + 1, Math.max(items.length - 1, 0)));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((index) => Math.max(index - 1, 0));
    } else if (event.key === "Enter") {
      if (open) {
        event.preventDefault();
        choose(items[active]);
      }
    } else if (event.key === "Escape") {
      if (open) {
        event.preventDefault();
        setOpen(false);
        setQuery("");
      }
    }
  }

  const activeId = open && items[active] ? `${listId}-opt-${active}` : undefined;

  return (
    <div className="relative">
      <label htmlFor={id} className="mb-1.5 block text-sm font-bold text-[color:var(--ink-muted)]">
        {label}
      </label>
      <div className="relative">
        <input
          ref={inputRef}
          id={id}
          type="text"
          role="combobox"
          aria-expanded={open}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={activeId}
          autoComplete="off"
          disabled={disabled}
          className="game-input pr-10"
          placeholder={selected ? selected.label : placeholder}
          value={open ? query : selected?.label ?? ""}
          onFocus={() => {
            setOpen(true);
            setActive(0);
          }}
          onBlur={() => {
            setOpen(false);
            setQuery("");
          }}
          onChange={(event) => {
            setQuery(event.target.value);
            setActive(0);
            setOpen(true);
          }}
          onKeyDown={onKeyDown}
        />
        <span className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-[color:var(--ink-muted)]" aria-hidden="true">▾</span>
      </div>
      {open ? (
        <ul
          id={listId}
          role="listbox"
          aria-label={label}
          className="absolute left-0 right-0 z-30 mt-1 max-h-64 overflow-auto rounded-2xl border border-[color:var(--border)] bg-[#FFFCFA] p-1 shadow-xl"
        >
          {items.length === 0 ? (
            <li className="px-3 py-3 text-sm text-[color:var(--ink-muted)]" role="presentation">
              Ничего не найдено
            </li>
          ) : (
            items.map((option, index) => (
              <li
                key={option.value || "__none"}
                id={`${listId}-opt-${index}`}
                role="option"
                aria-selected={option.value === value}
                className={`flex min-h-11 cursor-pointer items-center justify-between gap-3 rounded-xl px-3 py-2 text-[15px] ${
                  index === active ? "bg-[color:var(--accent-soft)] text-[color:var(--accent)]" : "text-[color:var(--ink)]"
                } ${option.value === value ? "font-black" : ""} ${option.value ? "" : "text-[color:var(--ink-muted)]"}`}
                onMouseDown={(event) => {
                  event.preventDefault();
                  choose(option);
                }}
                onMouseEnter={() => setActive(index)}
              >
                <span>{option.label}</span>
                {option.hint ? <span className="shrink-0 text-xs font-bold text-[color:var(--ink-muted)]">{option.hint}</span> : null}
              </li>
            ))
          )}
        </ul>
      ) : null}
    </div>
  );
}
