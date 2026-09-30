import { BookingStatus, RideType } from "../types";

export const PILOT_ACTIONS: Partial<Record<BookingStatus, BookingStatus[]>> = {
  ready: ["in_progress"],
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

type PilotStepHint = {
  actor: "pilot" | "operator" | "none";
  title: string;
  description: string;
};

export function getPilotStepHint(status: BookingStatus): PilotStepHint {
  switch (status) {
    case "confirmed":
      return {
        actor: "operator",
        title: "Ждёт оператора",
        description: "На /bookings нужно отметить приезд клиента. Пилот не принимает confirmed-заезд.",
      };
    case "arrived":
      return {
        actor: "operator",
        title: "Ждёт передачи от оператора",
        description: "После подготовки и инструктажа оператор или админ должен нажать «Передать пилоту» на /bookings.",
      };
    case "ready":
      return {
        actor: "pilot",
        title: "Следующий шаг пилота",
        description: "Когда фактический старт подтверждён, переведите заезд в «На воде».",
      };
    case "in_progress":
      return {
        actor: "pilot",
        title: "Следующий шаг пилота",
        description: "После фактического финиша завершите заезд кнопкой «Завершить заезд».",
      };
    case "late":
      return {
        actor: "operator",
        title: "Ждёт решения оператора",
        description: "Оператор или админ должен вернуть клиента в «Приехал» либо отметить «Не пришел».",
      };
    case "done":
      return {
        actor: "none",
        title: "Заезд завершён",
        description: "Следующий шаг не требуется.",
      };
    case "cancelled":
      return {
        actor: "none",
        title: "Бронь отменена",
        description: "Следующий шаг не требуется.",
      };
    case "no_show":
      return {
        actor: "none",
        title: "Клиент не пришёл",
        description: "Следующий шаг не требуется.",
      };
    default:
      return {
        actor: "none",
        title: "Проверьте статус",
        description: "Для этого заезда нужен ручной разбор статуса.",
      };
  }
}
