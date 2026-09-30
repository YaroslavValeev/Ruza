import { useState } from "react";

import { runBookingTimerAction, updateBookingPrep, updateBookingStatus } from "../../api/client";
import { BookingItem, StaffSession } from "../../types";
import { getPrimaryTimerAction, getTimerActionLabel } from "../../lib/shift-timer";
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

export function PilotRideControls({
  session,
  booking,
  onUpdated,
  allowTimerControls = false,
  allowCancel = false,
  compact = false,
}: PilotRideControlsProps): JSX.Element {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const beforeOnWater = !["in_progress", "done", "cancelled", "no_show"].includes(booking.status);
  const canMarkWarmup = booking.status === "arrived" || booking.status === "ready";
  const timerAction = getPrimaryTimerAction(booking);

  async function applyAction(task: () => Promise<BookingItem>) {
    setError(null);
    setLoading(true);
    try {
      const updated = await task();
      onUpdated(updated);
      emitShiftLiveRefresh();
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={`space-y-3 ${compact ? "" : ""}`}>
      {beforeOnWater ? (
        <div className="grid gap-3 lg:grid-cols-2">
          <div className="space-y-2">
            <div className="text-[11px] font-black uppercase tracking-[0.12em] text-cyan-100/70">Приезд</div>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                className={`game-button-secondary px-3 ${booking.status === "arrived" || booking.status === "ready" ? "ring-1 ring-emerald-300/45" : ""}`}
                disabled={loading}
                onClick={() => void applyAction(() => updateBookingPrep(booking.booking_id, { arrival_action: "arrived" }, session.token))}
              >
                Приехал
              </button>
              <button
                type="button"
                className={`game-button-secondary px-3 ${booking.status === "late" ? "ring-1 ring-amber-300/45" : ""}`}
                disabled={loading}
                onClick={() => void applyAction(() => updateBookingPrep(booking.booking_id, { arrival_action: "late" }, session.token))}
              >
                Не приехал
              </button>
            </div>
          </div>

          <div className="space-y-2">
            <div className="text-[11px] font-black uppercase tracking-[0.12em] text-cyan-100/70">Подготовка</div>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                className={`game-button-secondary px-3 ${booking.warmup_state === "warmed_up" ? "ring-1 ring-cyan-300/45" : ""}`}
                disabled={loading || !canMarkWarmup}
                onClick={() => void applyAction(() => updateBookingPrep(booking.booking_id, { warmup_state: "warmed_up" }, session.token))}
              >
                Размялся
              </button>
              <button
                type="button"
                className={`game-button-secondary px-3 ${booking.warmup_state === "no_warmup" ? "ring-1 ring-orange-300/45" : ""}`}
                disabled={loading || !canMarkWarmup}
                onClick={() => void applyAction(() => updateBookingPrep(booking.booking_id, { warmup_state: "no_warmup" }, session.token))}
              >
                Без разминки
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {allowTimerControls ? (
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
                  ? "Первое нажатие мягко выводит катер на глиссирование"
                  : booking.timer_state === "running"
                    ? "Пауза спокойно фиксирует оставшееся время"
                    : "Следующее нажатие мягко завершит заезд"}
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

      {beforeOnWater ? (
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className="game-button-secondary px-3 text-xs"
            disabled={loading}
            onClick={() => void applyAction(() => updateBookingStatus(booking.booking_id, "no_show", session.token))}
          >
            Не пришел
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

      {error ? <div className="rounded-2xl border border-red-400/20 bg-red-950/20 px-3 py-3 text-sm text-red-100">{error}</div> : null}
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
