import { BookingStatus, RideType } from "../types";

export const PILOT_ACTIONS: Partial<Record<BookingStatus, BookingStatus[]>> = {
  confirmed: ["arrived"],
  arrived: ["ready"],
  ready: ["in_progress"],
  late: ["arrived", "no_show"],
  in_progress: ["done"],
};

export const STATUS_LABELS: Partial<Record<BookingStatus, string>> = {
  confirmed: "Подтверждена",
  arrived: "Приехал",
  ready: "Готов к старту",
  in_progress: "На воде",
  done: "Завершена",
  late: "Опаздывает",
  no_show: "Не пришел",
  cancelled: "Отменена",
};

export const ACTION_LABELS: Partial<Record<BookingStatus, string>> = {
  arrived: "Принять клиента",
  ready: "Подготовить",
  in_progress: "На воду",
  done: "Завершить заезд",
  no_show: "Не пришел",
};

export const RIDE_TYPE_LABELS: Record<RideType, string> = {
  wakeboard: "Вейкборд",
  surf: "Серф",
  skim: "Ским",
};

export function getToday(): string {
  return new Date().toISOString().slice(0, 10);
}

export function getPrimaryActionText(status: BookingStatus): string {
  switch (status) {
    case "arrived":
      return "Принять спортсмена";
    case "ready":
      return "Подготовить к старту";
    case "in_progress":
      return "Вывести на воду";
    case "done":
      return "Завершить заезд";
    case "no_show":
      return "Не пришел";
    default:
      return ACTION_LABELS[status] || STATUS_LABELS[status] || status;
  }
}

export function getStatusTone(status: BookingStatus): string {
  if (status === "done") return "game-badge-success";
  if (status === "late" || status === "no_show" || status === "cancelled") return "game-badge-warn";
  return "game-badge-info";
}
