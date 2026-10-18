import type { BookingStatus } from "../types";

/** Словари подписей без зависимостей (только типы): их можно импортировать из node-тестов. */

/**
 * Статусы брони в нейтральной форме (без рода): «Подтверждено», «На месте», «Готово к старту»…
 * Так подпись одинаково читается и про бронь, и про клиента.
 */
export const BOOKING_STATUS_LABELS: Record<BookingStatus, string> = {
  confirmed: "Подтверждено",
  arrived: "На месте",
  ready: "Готово к старту",
  in_progress: "На воде",
  done: "Завершено",
  late: "Опоздание",
  no_show: "Неявка",
  cancelled: "Отменено",
};

const RIDE_TYPE_RU: Record<string, string> = {
  wakeboard: "вейкборд",
  surf: "вейксерф",
  wakesurf: "вейксерф",
  skim: "вейкским",
  wakeskim: "вейкским",
};

/** Дисциплина по-русски. В строке-перечислении — строчными, как отдельная подпись — с заглавной. */
export function rideTypeLabel(value: string | null | undefined, options: { capitalize?: boolean } = {}): string {
  const key = (value || "wakeboard").toLowerCase();
  const label = RIDE_TYPE_RU[key] ?? "вейкборд";
  return options.capitalize ? label.charAt(0).toUpperCase() + label.slice(1) : label;
}
