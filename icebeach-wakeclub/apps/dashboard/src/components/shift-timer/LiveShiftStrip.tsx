import { useEffect, useMemo, useState } from "react";

import { getShiftLive } from "../../api/client";
import { StaffSession } from "../../types";
import { STATUS_LABELS } from "../../mobile/pilot-utils";
import { formatDurationClock, getLiveStripHint, getRemainingTone, getStatusProgress, getWarmupLabel } from "../../lib/shift-timer";

type LiveShiftStripProps = {
  session: StaffSession;
  compact?: boolean;
};

const REFRESH_MS = 10000;
const STRIP_REFRESH_EVENT = "icebeach:shift-live-refresh";

export function emitShiftLiveRefresh(): void {
  if (typeof window === "undefined") {
    return;
  }
  window.dispatchEvent(new CustomEvent(STRIP_REFRESH_EVENT));
}

export function LiveShiftStrip({ session, compact = false }: LiveShiftStripProps): JSX.Element {
  const [focusBooking, setFocusBooking] = useState<import("../../types").BookingItem | null>(null);
  const [fetchedAt, setFetchedAt] = useState(() => Date.now());

  const load = async () => {
    try {
      const payload = await getShiftLive(session.token);
      setFocusBooking(payload.focus_booking ?? null);
      setFetchedAt(Date.now());
    } catch {
      setFocusBooking(null);
    }
  };

  useEffect(() => {
    void load();
    const id = window.setInterval(() => {
      if (document.visibilityState === "visible") {
        void load();
      }
    }, REFRESH_MS);
    const refreshListener = () => {
      void load();
    };
    window.addEventListener(STRIP_REFRESH_EVENT, refreshListener);
    return () => {
      window.clearInterval(id);
      window.removeEventListener(STRIP_REFRESH_EVENT, refreshListener);
    };
  }, [session.token]);

  const [, setNowTick] = useState(0);
  useEffect(() => {
    const id = window.setInterval(() => setNowTick((value) => value + 1), 1000);
    return () => window.clearInterval(id);
  }, []);

  const liveRemaining = useMemo(() => {
    if (!focusBooking) return 0;
    if (focusBooking.timer_state !== "running") return focusBooking.remaining_seconds;
    const driftSeconds = Math.max(Math.floor((Date.now() - fetchedAt) / 1000), 0);
    return Math.max(focusBooking.remaining_seconds - driftSeconds, 0);
  }, [focusBooking, fetchedAt]);

  const progress = focusBooking ? getStatusProgress(focusBooking.status) : 0;
  const remainingTone = focusBooking ? getRemainingTone(liveRemaining, focusBooking.timer_state) : "cool";
  const hint = getLiveStripHint(session.role, focusBooking);

  return (
    <div className={`shift-strip game-panel-soft ${compact ? "px-3 py-3" : "px-4 py-3"} mt-3`}>
      <div className="relative overflow-hidden rounded-[22px] border border-cyan-200/10 bg-slate-950/70 px-4 py-3">
        <div className="shift-strip-water" aria-hidden="true" />
        <div className="relative z-10 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="game-chip text-cyan-100">Живая смена</span>
              {focusBooking ? <span className="game-chip text-orange-100">{STATUS_LABELS[focusBooking.status] || focusBooking.status}</span> : null}
              {focusBooking ? <span className="game-chip text-cyan-100">{getWarmupLabel(focusBooking.warmup_state)}</span> : null}
            </div>
            <div className="mt-3 flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <div className="min-w-0 text-lg font-black text-white sm:text-xl">
                {focusBooking ? (focusBooking.client_name || focusBooking.client_id) : "Сейчас без активного заезда"}
              </div>
              {focusBooking ? <div className="text-sm text-cyan-100/70">{focusBooking.time} • {focusBooking.boat_id}</div> : null}
            </div>
            <p className="mt-2 text-sm text-slate-300">{hint}</p>
          </div>

          <div className="flex min-w-[168px] flex-col items-start gap-2 lg:items-end">
            {focusBooking ? (
              <>
                <div className={`shift-clock shift-clock-${remainingTone}`}>
                  <span>{formatDurationClock(liveRemaining)}</span>
                </div>
                <div className="text-xs text-cyan-100/70">
                  План {focusBooking.planned_duration_minutes} мин
                  {focusBooking.actual_duration_seconds > 0 ? ` • факт ${Math.max(Math.round(focusBooking.actual_duration_seconds / 60), 1)} мин` : ""}
                </div>
              </>
            ) : (
              <div className="text-sm text-slate-400">Стрип обновится, как только появится бронирование на смене.</div>
            )}
          </div>
        </div>

        <div className="relative z-10 mt-4 grid grid-cols-5 gap-2">
          {["Подтверждена", "Приехал", "Готов", "На воде", "Завершена"].map((step, index) => (
            <div
              key={step}
              className={`shift-step ${focusBooking && progress > index ? "shift-step-active" : ""}`}
            >
              {step}
            </div>
          ))}
        </div>
        <div className="shift-progress mt-3">
          <div className="shift-progress-fill" style={{ width: `${focusBooking ? ((progress - 1) / 4) * 100 : 0}%` }} />
        </div>
      </div>
    </div>
  );
}
