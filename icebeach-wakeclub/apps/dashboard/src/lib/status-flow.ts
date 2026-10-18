import { runBookingTimerAction, updateBookingPrep, updateBookingStatus } from "../api/client";
import { BookingItem, BookingStatus, StaffSession } from "../types";

/**
 * Этапы заезда и «следующий шаг» для текущей роли.
 * Права повторяют бэкенд (routes/bookings.py):
 *  - «На месте» (PATCH /prep arrival_action=arrived): администратор, оператор, пилот своего катера;
 *  - «Готово к старту» (PATCH /status ready, «Передать пилоту»): администратор, оператор;
 *  - «На воде» / «Завершено» — только через таймер (POST /timer-action start|stop): администратор, пилот своего катера.
 * Тренер и маркетинг статусы не меняют.
 */
export const FLOW_STEPS: Array<{ status: BookingStatus; full: string; short: string }> = [
  { status: "confirmed", full: "Подтверждено", short: "Бронь" },
  { status: "arrived", full: "На месте", short: "На месте" },
  { status: "ready", full: "Готово к старту", short: "Готово" },
  { status: "in_progress", full: "На воде", short: "На воде" },
  { status: "done", full: "Завершено", short: "Финиш" },
];

export type FlowAction = "arrive" | "ready" | "start" | "finish";

export type NextStep = {
  /** Индекс шага в FLOW_STEPS, в который переводит действие. */
  index: number;
  action: FlowAction;
  /** Подпись на кнопке. */
  label: string;
  allowed: boolean;
  /** Почему недоступно (для подсказки и текста под этапами). */
  reason: string | null;
  /** Перед «Передать пилоту» нужно отметить разминку — кнопки разминки показываются рядом. */
  needsWarmup: boolean;
  /** Можно ли текущей роли отметить разминку. */
  canWarmup: boolean;
};

type FlowBooking = Pick<BookingItem, "booking_id" | "status" | "warmup_state" | "timer_state" | "boat_id">;

/** Индекс текущего этапа: «Опоздание» стоит на месте «Подтверждено». Для отменённых/неявки — null. */
export function currentFlowIndex(status: BookingStatus): number | null {
  if (status === "late") return 0;
  const index = FLOW_STEPS.findIndex((step) => step.status === status);
  return index >= 0 ? index : null;
}

function pilotBoatReason(session: StaffSession, booking: FlowBooking): string | null {
  if (session.role !== "pilot") return null;
  if (!session.boat_id) return "За вами не закреплён катер — обратитесь к администратору.";
  if (booking.boat_id && booking.boat_id !== session.boat_id) return "Заезд на другом катере — его ведёт закреплённый пилот.";
  return null;
}

export function getNextStep(session: StaffSession, booking: FlowBooking): NextStep | null {
  const role = session.role;
  const viewer = role === "coach" || role === "marketing_read";
  const boatReason = pilotBoatReason(session, booking);

  if (booking.status === "confirmed" || booking.status === "late") {
    const allowed = (role === "admin" || role === "operator" || role === "pilot") && !boatReason;
    return {
      index: 1,
      action: "arrive",
      label: "На месте",
      allowed,
      reason: allowed ? null : boatReason ?? (viewer ? "Прибытие отмечает оператор." : "Нет прав на отметку прибытия."),
      needsWarmup: false,
      canWarmup: false,
    };
  }
  if (booking.status === "arrived") {
    const canWarmup = (role === "admin" || role === "operator" || role === "pilot") && !boatReason;
    const needsWarmup = booking.warmup_state === "pending";
    const roleAllowed = role === "admin" || role === "operator";
    const allowed = roleAllowed && !needsWarmup;
    let reason: string | null = null;
    if (!roleAllowed) {
      reason = role === "pilot" ? "К старту передаёт оператор — кнопкой «Передать пилоту» в разделе «Брони»." : "К старту передаёт оператор.";
    } else if (needsWarmup) {
      reason = "Сначала отметьте разминку: «Размялся» или «Без разминки».";
    }
    return { index: 2, action: "ready", label: "Готово к старту", allowed, reason, needsWarmup, canWarmup };
  }
  if (booking.status === "ready") {
    const allowed = (role === "admin" || role === "pilot") && !boatReason;
    return {
      index: 3,
      action: "start",
      label: "На воде",
      allowed,
      reason: allowed ? null : boatReason ?? "Сет запускает пилот на своём катере.",
      needsWarmup: false,
      canWarmup: false,
    };
  }
  if (booking.status === "in_progress") {
    const allowed = (role === "admin" || role === "pilot") && !boatReason;
    return {
      index: 4,
      action: "finish",
      label: "Завершено",
      allowed,
      reason: allowed ? null : boatReason ?? "Заезд завершает пилот.",
      needsWarmup: false,
      canWarmup: false,
    };
  }
  return null;
}

/** Подпись действия для кнопки и aria-label. */
export function flowActionTitle(action: FlowAction): string {
  switch (action) {
    case "arrive":
      return "Отметить «На месте»";
    case "ready":
      return "Передать пилоту — «Готово к старту»";
    case "start":
      return "Запустить сет — «На воде»";
    case "finish":
      return "Завершить заезд";
  }
}

export function runFlowAction(action: FlowAction, bookingId: string, token?: string): Promise<BookingItem> {
  switch (action) {
    case "arrive":
      return updateBookingPrep(bookingId, { arrival_action: "arrived" }, token);
    case "ready":
      return updateBookingStatus(bookingId, "ready", token);
    case "start":
      return runBookingTimerAction(bookingId, "start", token);
    case "finish":
      return runBookingTimerAction(bookingId, "stop", token);
  }
}

const BOOKING_UPDATED_EVENT = "icebeach:booking-updated";

/** Сообщить экранам (Брони, Пилот), что бронь изменилась из другого места — например, из живой полосы. */
export function emitBookingUpdated(booking: BookingItem): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent<BookingItem>(BOOKING_UPDATED_EVENT, { detail: booking }));
}

export function onBookingUpdated(listener: (booking: BookingItem) => void): () => void {
  const handler = (event: Event) => {
    const detail = (event as CustomEvent<BookingItem>).detail;
    if (detail?.booking_id) listener(detail);
  };
  window.addEventListener(BOOKING_UPDATED_EVENT, handler);
  return () => window.removeEventListener(BOOKING_UPDATED_EVENT, handler);
}
