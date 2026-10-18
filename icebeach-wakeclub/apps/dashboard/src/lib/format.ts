/**
 * Безопасное форматирование чисел для интерфейса.
 * Любое отсутствующее или нечисловое значение показывается как «—», NaN на экран не попадает.
 */

export const EMPTY_VALUE = "—";

/** Приводит значение из API (число или строку) к конечному числу, иначе null. */
export function toFiniteNumber(value: unknown): number | null {
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value.replace(",", "."));
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

/** true, если значение — конечное число больше нуля. */
export function isPositive(value: unknown): boolean {
  const n = toFiniteNumber(value);
  return n !== null && n > 0;
}

export function formatCount(value: unknown): string {
  const n = toFiniteNumber(value);
  return n === null ? EMPTY_VALUE : String(Math.round(n));
}

export function formatMinutes(value: unknown): string {
  const n = toFiniteNumber(value);
  return n === null ? EMPTY_VALUE : `${Math.round(n)} мин`;
}

/** Секунды → «ММ:СС»; без значения — «—». */
export function formatClock(value: unknown): string {
  const n = toFiniteNumber(value);
  if (n === null) return EMPTY_VALUE;
  const safe = Math.max(Math.floor(n), 0);
  const minutes = Math.floor(safe / 60);
  const seconds = safe % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

/** Рубли → «12 000 ₽». */
export function formatRub(value: unknown): string {
  const n = toFiniteNumber(value);
  return n === null ? EMPTY_VALUE : `${n.toLocaleString("ru-RU")} ₽`;
}

/** Копейки (minor units) → «120 ₽». */
export function formatRubMinor(value: unknown): string {
  const n = toFiniteNumber(value);
  return n === null ? EMPTY_VALUE : `${(n / 100).toLocaleString("ru-RU")} ₽`;
}

export function formatPercent(value: unknown, digits = 0): string {
  const n = toFiniteNumber(value);
  return n === null ? EMPTY_VALUE : `${n.toFixed(digits)} %`;
}
