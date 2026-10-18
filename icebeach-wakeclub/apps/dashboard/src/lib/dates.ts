/** Calendar date in the operator's local timezone, not UTC. */
export function formatLocalIsoDate(value = new Date()): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

const MONTHS_SHORT = ["янв", "фев", "мар", "апр", "мая", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"];

function splitIso(value: string | null | undefined): [number, number, number] | null {
  if (!value) return null;
  const match = value.match(/^(\d{4})-(\d{2})-(\d{2})/);
  return match ? [Number(match[1]), Number(match[2]), Number(match[3])] : null;
}

/** 2026-10-17 → 17.10.2026 */
export function formatDateRu(value: string | null | undefined): string {
  const parts = splitIso(value);
  if (!parts) return value || "—";
  const [year, month, day] = parts;
  return `${String(day).padStart(2, "0")}.${String(month).padStart(2, "0")}.${year}`;
}

/** 2026-10-17 → 17 окт */
export function formatDayMonth(value: string | null | undefined): string {
  const parts = splitIso(value);
  if (!parts) return value || "—";
  const [, month, day] = parts;
  return `${day} ${MONTHS_SHORT[month - 1]}`;
}

/** 2026-10-17 → 17.10 */
export function formatDayMonthNumeric(value: string | null | undefined): string {
  const parts = splitIso(value);
  if (!parts) return value || "—";
  const [, month, day] = parts;
  return `${String(day).padStart(2, "0")}.${String(month).padStart(2, "0")}`;
}

/** Диапазон дат: один день → «17.10.2026», иначе «01.06.2026 — 01.10.2026». */
export function formatDateRangeRu(from: string | null | undefined, to: string | null | undefined): string {
  if (!from && !to) return "—";
  if (!to || from === to) return formatDateRu(from);
  return `${formatDateRu(from)} — ${formatDateRu(to)}`;
}

/** Время по-русски: 12:30 */
export function formatTimeRu(value: string | number | Date | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
}

/** 79990000021 → +7 999 000-00-21; нестандартные номера возвращаются как есть. */
export function formatPhoneRu(value: string | null | undefined): string {
  if (!value) return "—";
  const digits = value.replace(/\D/g, "");
  if (digits.length === 11 && (digits.startsWith("7") || digits.startsWith("8"))) {
    return `+7 ${digits.slice(1, 4)} ${digits.slice(4, 7)}-${digits.slice(7, 9)}-${digits.slice(9, 11)}`;
  }
  return value;
}

/** Сегодняшняя дата в часовом поясе устройства (YYYY-MM-DD). toISOString() дал бы дату по UTC — до 03:00 МСК это «вчера». */
export function localTodayIso(now: Date = new Date()): string {
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${now.getFullYear()}-${month}-${day}`;
}
