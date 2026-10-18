import { BookingItem, BookingStatus, RideTimerState, StaffRole, WarmupState } from "../types";
import { formatClock } from "./format";

export const SHIFT_STATUS_SEQUENCE: BookingStatus[] = ["confirmed", "arrived", "ready", "in_progress", "done"];
export const SET_DURATION_MINUTES = 25;

export function getLiveRemainingSeconds(
  booking: Pick<BookingItem, "timer_state" | "remaining_seconds"> | null,
  fetchedAt: number,
  now: number,
): number | null {
  if (!booking) return 0;
  // Нет данных таймера → null, чтобы на экране было «—», а не «00:00».
  if (booking.remaining_seconds === null || booking.remaining_seconds === undefined) return null;
  const driftSeconds = booking.timer_state === "running" ? Math.max(Math.floor((now - fetchedAt) / 1000), 0) : 0;
  return Math.max(booking.remaining_seconds - driftSeconds, 0);
}

// Focus and queue cards can render controls for the same booking in one tab.
const pendingBookingActions = new Set<string>();
const bookingActionListeners = new Set<() => void>();

export function subscribeBookingActions(listener: () => void): () => void {
  bookingActionListeners.add(listener);
  return () => { bookingActionListeners.delete(listener); };
}

export function isBookingActionPending(key: string): boolean {
  return pendingBookingActions.has(key);
}

export function beginBookingAction(key: string): (() => void) | null {
  if (pendingBookingActions.has(key)) return null;
  pendingBookingActions.add(key);
  bookingActionListeners.forEach((listener) => listener());
  return () => {
    pendingBookingActions.delete(key);
    bookingActionListeners.forEach((listener) => listener());
  };
}

/** Секунды → «ММ:СС». Пустое или нечисловое значение → «—» (никогда не «NaN:NaN»). */
export function formatDurationClock(totalSeconds: number | null | undefined): string {
  return formatClock(totalSeconds);
}

export function getStatusProgress(status: BookingStatus): number {
  const index = SHIFT_STATUS_SEQUENCE.indexOf(status);
  return index >= 0 ? index + 1 : 1;
}

export function getWarmupLabel(state: WarmupState): string {
  if (state === "warmed_up") return "Размялся";
  if (state === "no_warmup") return "Без разминки";
  return "Разминка не отмечена";
}

export function getPrimaryTimerAction(
  booking: Pick<BookingItem, "status" | "timer_state">,
): "start" | "pause" | "stop" | null {
  if (booking.status === "ready" && booking.timer_state === "idle") {
    return "start";
  }
  if (booking.status === "in_progress" && booking.timer_state === "running") {
    return "pause";
  }
  if (booking.status === "in_progress" && booking.timer_state === "paused") {
    return "stop";
  }
  return null;
}

export function getTimerActionLabel(action: "start" | "pause" | "stop" | null): string {
  if (action === "start") return "Запустить сет";
  if (action === "pause") return "Пауза";
  if (action === "stop") return "Завершить заезд";
  return "Таймер недоступен";
}

export function getLiveStripHint(role: StaffRole, booking: BookingItem | null | undefined): string {
  if (!booking) {
    return "Смена идёт спокойно. Активных событий сейчас нет.";
  }
  const viewer = role === "coach" || role === "marketing_read";
  if (booking.status === "confirmed" || booking.status === "late") {
    if (viewer) return "Ожидаем фактического приезда клиента — его отмечает оператор.";
    if (role === "pilot") return "Ждём прибытия. Если клиент уже у катера, нажмите «На месте» в этапах ниже.";
    return "Клиент приехал? Нажмите «На месте» в этапах ниже.";
  }
  if (booking.status === "arrived") {
    if (viewer) return "Клиент на месте. Оператор готовит его к старту.";
    if (role === "pilot") return "Клиент на месте. К старту его передаёт оператор.";
    if (booking.warmup_state === "pending") {
      return "Отметьте разминку, затем нажмите «Готово к старту» — заезд перейдёт пилоту.";
    }
    return "Подготовка отмечена. Нажмите «Готово к старту», чтобы передать клиента пилоту.";
  }
  if (booking.status === "ready") {
    return role === "pilot" || role === "admin" ? "Клиент готов. Нажмите «На воде», чтобы запустить сет." : "Клиент готов. Сет запускает пилот.";
  }
  if (booking.status === "in_progress") {
    if (booking.timer_state === "paused") {
      return role === "pilot" || role === "admin" ? "Сет на паузе. «Завершено» — закончить заезд." : "Сет на паузе, ждём завершения от пилота.";
    }
    return role === "pilot" || role === "admin" ? "Сет идёт. Когда клиент финиширует, нажмите «Завершено»." : "Сет идёт. Таймер показывает оставшееся время.";
  }
  if (booking.status === "done") {
    return "Заезд завершён. Фактическое время сохранено, оплата не изменилась.";
  }
  return "Следим за состоянием заезда.";
}

export function getRemainingTone(remainingSeconds: number | null, timerState: RideTimerState): "cool" | "warm" | "hot" {
  if ((timerState !== "running" && timerState !== "paused") || remainingSeconds === null) {
    return "cool";
  }
  if (remainingSeconds <= 60) {
    return "hot";
  }
  if (remainingSeconds <= 300) {
    return "warm";
  }
  return "cool";
}
