import { useId, useState, useSyncExternalStore } from "react";

import { runBookingTimerAction, updateBookingPrep, updateBookingStatus } from "../../api/client";
import { BookingItem, StaffSession } from "../../types";
import { isPositive } from "../../lib/format";
import { beginBookingAction, formatDurationClock, getPrimaryTimerAction, getTimerActionLabel, isBookingActionPending, subscribeBookingActions } from "../../lib/shift-timer";
import { emitShiftLiveRefresh } from "./LiveShiftStrip";

type PilotRideControlsProps = {
  session: StaffSession;
  booking: Pick<
    BookingItem,
    "booking_id" | "status" | "warmup_state" | "timer_state" | "planned_duration_minutes" | "actual_duration_seconds"
  >;
  onUpdated: (booking: BookingItem) => void;
  allowTimerControls?: boolean;
  allowCancel?: boolean;
  compact?: boolean;
};

const WARMUP_LOCKED_HINT = "Разминку отмечают после «На месте».";
const ARRIVAL_LOCKED_HINT = "Клиент уже готов к старту — прибытие менять поздно.";
const LATE_LOCKED_HINT = "Опоздание и неявку отмечают только до прибытия клиента.";

export function PilotRideControls({
  session,
  booking,
  onUpdated,
  allowTimerControls = false,
  allowCancel = false,
  compact = false,
}: PilotRideControlsProps): JSX.Element {
  // Общий флаг на бронь: карточка фокуса и очередь в одной вкладке не отправят действие дважды.
  const actionKey = JSON.stringify([session.club_id, booking.booking_id]);
  const loading = useSyncExternalStore(subscribeBookingActions, () => isBookingActionPending(actionKey), () => false);
  const [error, setError] = useState<string | null>(null);

  const canManageStatus = session.role === "admin" || session.role === "operator";
  const canManagePrep = canManageStatus || session.role === "pilot";
  const beforeOnWater = !["in_progress", "done", "cancelled", "no_show"].includes(booking.status);
  const canMarkArrival = ["confirmed", "late", "arrived"].includes(booking.status);
  const canMarkLate = booking.status === "confirmed" || booking.status === "late";
  const canUseTimer = allowTimerControls && (session.role === "admin" || session.role === "pilot");
  const canMarkWarmup = booking.status === "arrived" || booking.status === "ready";
  const timerAction = getPrimaryTimerAction(booking);
  const warmupHintId = useId();
  const arrivalHintId = useId();
  const arrivalHint = !canMarkArrival ? ARRIVAL_LOCKED_HINT : !canMarkLate ? LATE_LOCKED_HINT : null;

  async function applyAction(task: () => Promise<BookingItem>) {
    const release = beginBookingAction(actionKey);
    if (!release) return;
    setError(null);
    try {
      const updated = await task();
      onUpdated(updated);
      emitShiftLiveRefresh();
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      release();
    }
  }

  return (
    <div className={`space-y-3 ${compact ? "" : ""}`}>
      {canManagePrep && beforeOnWater ? (
        <div className="grid gap-3 lg:grid-cols-2">
          <div className="space-y-2">
            <div className="text-[11px] font-black uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">Прибытие</div>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                className={`game-button-secondary px-3 ${booking.status === "arrived" || booking.status === "ready" ? "border-[color:var(--accent)] bg-[color:var(--accent-soft)] text-[color:var(--accent)]" : ""}`}
                aria-pressed={booking.status === "arrived" || booking.status === "ready"}
                disabled={loading || !canMarkArrival}
                title={!canMarkArrival ? ARRIVAL_LOCKED_HINT : undefined}
                aria-describedby={!canMarkArrival ? arrivalHintId : undefined}
                onClick={() => void applyAction(() => updateBookingPrep(booking.booking_id, { arrival_action: "arrived" }, session.token))}
              >
                На месте
              </button>
              <button
                type="button"
                className={`game-button-secondary px-3 ${booking.status === "late" ? "border-[color:var(--warn)] bg-amber-50 text-amber-900" : ""}`}
                aria-pressed={booking.status === "late"}
                disabled={loading || !canMarkLate}
                title={!canMarkLate ? LATE_LOCKED_HINT : undefined}
                aria-describedby={!canMarkLate ? arrivalHintId : undefined}
                onClick={() => void applyAction(() => updateBookingPrep(booking.booking_id, { arrival_action: "late" }, session.token))}
              >
                Опаздывает
              </button>
            </div>
            {arrivalHint ? (
              <p id={arrivalHintId} className="text-xs text-[color:var(--ink-muted)]">
                {arrivalHint}
              </p>
            ) : null}
          </div>

          <div className="space-y-2">
            <div className="text-[11px] font-black uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">Подготовка</div>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                className={`game-button-secondary px-3 ${booking.warmup_state === "warmed_up" ? "border-[color:var(--accent)] bg-[color:var(--accent-soft)] text-[color:var(--accent)]" : ""}`}
                aria-pressed={booking.warmup_state === "warmed_up"}
                disabled={loading || !canMarkWarmup}
                aria-describedby={!canMarkWarmup ? warmupHintId : undefined}
                title={!canMarkWarmup ? WARMUP_LOCKED_HINT : undefined}
                onClick={() => void applyAction(() => updateBookingPrep(booking.booking_id, { warmup_state: "warmed_up" }, session.token))}
              >
                Размялся
              </button>
              <button
                type="button"
                className={`game-button-secondary px-3 ${booking.warmup_state === "no_warmup" ? "border-[color:var(--accent)] bg-[color:var(--accent-soft)] text-[color:var(--accent)]" : ""}`}
                aria-pressed={booking.warmup_state === "no_warmup"}
                disabled={loading || !canMarkWarmup}
                aria-describedby={!canMarkWarmup ? warmupHintId : undefined}
                title={!canMarkWarmup ? WARMUP_LOCKED_HINT : undefined}
                onClick={() => void applyAction(() => updateBookingPrep(booking.booking_id, { warmup_state: "no_warmup" }, session.token))}
              >
                Без разминки
              </button>
            </div>
            {!canMarkWarmup ? (
              <p id={warmupHintId} className="text-xs text-[color:var(--ink-muted)]">
                {WARMUP_LOCKED_HINT}
              </p>
            ) : null}
          </div>
        </div>
      ) : null}

      {canUseTimer && timerAction ? (
        <div className="space-y-3">
          <button
            type="button"
            className={`pilot-boat-button ${booking.timer_state === "running" ? "pilot-boat-button-running" : booking.timer_state === "paused" ? "pilot-boat-button-paused" : "pilot-boat-button-idle"}`}
            disabled={loading || !timerAction}
            onClick={() => timerAction && void applyAction(() => runBookingTimerAction(booking.booking_id, timerAction, session.token))}
          >
            <span className="pilot-boat-icon" aria-hidden="true">
              <TowBoatIcon running={booking.timer_state === "running"} paused={booking.timer_state === "paused"} />
            </span>
            <span className="pilot-boat-copy">
              <span className="pilot-boat-label">{getTimerActionLabel(timerAction)}</span>
              <span className="pilot-boat-subtitle">
                {booking.timer_state === "idle"
                  ? "Катер плавно выйдет на глиссирование, таймер начнёт отсчёт"
                  : booking.timer_state === "running"
                    ? "Пауза сохранит оставшееся время"
                    : "Следующее нажатие плавно завершит заезд"}
              </span>
            </span>
          </button>

          {booking.status === "in_progress" ? (
            <div className="grid gap-2 sm:grid-cols-2">
              <button
                type="button"
                className="game-button-secondary px-3"
                disabled={loading}
                onClick={() => void applyAction(() => runBookingTimerAction(booking.booking_id, "add_set", session.token))}
              >
                + Добавить сет
              </button>
              <button
                type="button"
                className="game-button-secondary px-3"
                disabled={loading}
                onClick={() => void applyAction(() => runBookingTimerAction(booking.booking_id, "notify_next_client", session.token))}
              >
                Предложить старт раньше
              </button>
            </div>
          ) : null}
        </div>
      ) : null}

      {allowTimerControls && !timerAction && isPositive(booking.actual_duration_seconds) ? (
        <div className="rounded-[24px] border border-[color:var(--accent-border)] bg-[color:var(--panel-solid)] px-4 py-4">
          <div className="text-xs font-black uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">Фактическое время</div>
          <div className="mt-2 text-lg font-black text-[color:var(--ink)]">
            {formatDurationClock(booking.actual_duration_seconds)} из {formatDurationClock(booking.planned_duration_minutes === null ? null : booking.planned_duration_minutes * 60)}
          </div>
          <div className="mt-1 text-sm text-[color:var(--ink-muted)]">Заезд завершён. План и факт сохранены отдельно, сумма оплаты не менялась.</div>
        </div>
      ) : null}

      {canManageStatus && beforeOnWater ? (
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className="game-button-secondary px-3 text-xs"
            disabled={loading || !canMarkLate}
            title={!canMarkLate ? LATE_LOCKED_HINT : undefined}
            onClick={() => void applyAction(() => updateBookingStatus(booking.booking_id, "no_show", session.token))}
          >
            Неявка
          </button>
          {allowCancel ? (
            <button
              type="button"
              className="game-button-secondary px-3 text-xs"
              disabled={loading}
              onClick={() => void applyAction(() => updateBookingStatus(booking.booking_id, "cancelled", session.token))}
            >
              Отменить
            </button>
          ) : null}
        </div>
      ) : null}

      {error ? <div role="alert" className="rounded-2xl border border-red-600/25 bg-red-50 px-3 py-3 text-sm text-red-900">{error}</div> : null}
    </div>
  );
}

function TowBoatIcon({ running, paused }: { running: boolean; paused: boolean }): JSX.Element {
  return (
    <svg viewBox="0 0 128 64" className={`h-12 w-24 ${running ? "pilot-boat-svg-running" : paused ? "pilot-boat-svg-paused" : "pilot-boat-svg-idle"}`}>
      <path d="M18 45c17 0 34-2 49-6l17-5 18 2v9H18z" fill="rgba(77,136,255,0.9)" />
      <path d="M60 24h12l4 10H52z" fill="rgba(224,242,255,0.92)" />
      <path d="M43 30l8-9h8l-4 9z" fill="rgba(89,227,255,0.78)" />
      <path d="M8 52c12-3 24-3 36 0" stroke="rgba(89,227,255,0.55)" strokeWidth="4" strokeLinecap="round" />
      <path d="M54 55c12-3 24-3 36 0" stroke="rgba(89,227,255,0.35)" strokeWidth="3" strokeLinecap="round" />
      <path className="pilot-boat-wake" d="M80 51c10-2 20-2 30 0" stroke="rgba(255,255,255,0.38)" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}
