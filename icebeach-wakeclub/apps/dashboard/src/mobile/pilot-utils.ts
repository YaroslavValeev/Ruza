import type { BookingStatus, RideType } from "../types";
import { formatLocalIsoDate } from "../lib/dates";
import { BOOKING_STATUS_LABELS, rideTypeLabel } from "../lib/label-dict";

export const PILOT_ACTIONS: Partial<Record<BookingStatus, BookingStatus[]>> = {};

export const STATUS_LABELS: Partial<Record<BookingStatus, string>> = BOOKING_STATUS_LABELS;

export const ACTION_LABELS: Partial<Record<BookingStatus, string>> = {
  arrived: "Принять клиента",
  ready: "На воду",
  in_progress: "На воду",
  done: "Завершить заезд",
  no_show: "Неявка",
};

export const RIDE_TYPE_LABELS: Record<RideType, string> = {
  wakeboard: rideTypeLabel("wakeboard"),
  surf: rideTypeLabel("surf"),
  skim: rideTypeLabel("skim"),
};

export function getToday(): string {
  return formatLocalIsoDate();
}

export function getPrimaryActionText(status: BookingStatus): string {
  switch (status) {
    case "arrived":
      return "Принять спортсмена";
    case "ready":
      return "На воду";
    case "in_progress":
      return "На воду";
    case "done":
      return "Завершить заезд";
    case "no_show":
      return "Неявка";
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
        description: "Обычно прибытие отмечает оператор в разделе «Брони». Если клиент уже у катера, нажмите «На месте».",
      };
    case "arrived":
      return {
        actor: "operator",
        title: "Ждёт передачи от оператора",
        description: "После подготовки и инструктажа оператор или администратор нажимает «Передать пилоту» в разделе «Брони».",
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
        description: "Оператор или администратор отмечает «На месте» либо «Неявка».",
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
