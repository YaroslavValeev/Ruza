import { BookingItem, BookingStatus, RideTimerState, StaffRole, WarmupState } from "../types";

export const SHIFT_STATUS_SEQUENCE: BookingStatus[] = ["confirmed", "arrived", "ready", "in_progress", "done"];
export const SET_DURATION_MINUTES = 25;

export function formatDurationClock(totalSeconds: number): string {
  const safeSeconds = Math.max(totalSeconds, 0);
  const minutes = Math.floor(safeSeconds / 60);
  const seconds = safeSeconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
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
  if (action === "stop") return "Завершить мягко";
  return "Таймер недоступен";
}

export function getLiveStripHint(role: StaffRole, booking: BookingItem | null | undefined): string {
  if (!booking) {
    return "Смена идёт спокойно. Активных событий сейчас нет.";
  }
  if (booking.status === "confirmed" || booking.status === "late") {
    if (role === "coach" || role === "marketing_read") {
      return "Ожидаем подтверждения фактического приезда.";
    }
    return "Сейчас важно отметить фактический приезд клиента.";
  }
  if (booking.status === "arrived") {
    if (booking.warmup_state !== "pending") {
      if (role === "coach" || role === "marketing_read") {
        return "Подготовка отмечена. Ждём явную передачу пилоту.";
      }
      return "Подготовка отмечена. Теперь нужен явный handoff «Передать пилоту».";
    }
    if (role === "coach" || role === "marketing_read") {
      return "Клиент на месте. Следующий шаг — отметить готовность к старту.";
    }
    return "Отметьте разминку или старт без разминки, чтобы перевести клиента в «Готов к старту».";
  }
  if (booking.status === "ready") {
    return role === "pilot" ? "Клиент готов. Можно мягко запускать сет." : "Клиент готов. Пилот может запускать сет.";
  }
  if (booking.status === "in_progress") {
    if (booking.timer_state === "paused") {
      return role === "pilot" ? "Сет на паузе. Следующее нажатие мягко завершит текущий заезд." : "Сет на паузе, ждём мягкого завершения пилотом.";
    }
    return "Сет идёт. Таймер показывает оставшееся время.";
  }
  if (booking.status === "done") {
    return "Заезд завершён мягко. Сохранили фактическое время без изменения оплаты.";
  }
  return "Следим за состоянием заезда.";
}

export function getRemainingTone(remainingSeconds: number, timerState: RideTimerState): "cool" | "warm" | "hot" {
  if (timerState !== "running" && timerState !== "paused") {
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
