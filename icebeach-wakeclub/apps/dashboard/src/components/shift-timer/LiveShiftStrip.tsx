import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";

import { getShiftLive } from "../../api/client";
import { BookingItem, StaffSession } from "../../types";
import { boatLabel, statusLabel, useBoatNames } from "../../lib/labels";
import { mergeBookingUpdate } from "../../lib/equipment";
import { StatusStepper } from "./StatusStepper";
import { formatMinutes, isPositive } from "../../lib/format";
import { formatDurationClock, getLiveRemainingSeconds, getLiveStripHint, getRemainingTone, getWarmupLabel } from "../../lib/shift-timer";

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
  useBoatNames(session);
  const location = useLocation();
  const [focusBooking, setFocusBooking] = useState<BookingItem | null>(null);
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

  const liveRemaining = focusBooking ? getLiveRemainingSeconds(focusBooking, fetchedAt, Date.now()) : null;

  const remainingTone = focusBooking ? getRemainingTone(liveRemaining, focusBooking.timer_state) : "cool";
  const hint = getLiveStripHint(session.role, focusBooking);
  const link = focusBooking ? getStripLink(session.role, focusBooking, compact) : null;
  const linkIsHere = link ? `${location.pathname}${location.search}` === link.to : false;

  return (
    <div className={`shift-strip game-panel-soft ${compact ? "px-3 py-3" : "px-4 py-3"} mt-3`}>
      <div className="shift-strip-shell">
        <div className="shift-strip-water" aria-hidden="true" />
        <div className="relative z-10 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="game-chip">Живая смена</span>
              {focusBooking ? <span className="game-chip">{statusLabel(focusBooking.status)}</span> : null}
              {focusBooking ? <span className="game-chip">{getWarmupLabel(focusBooking.warmup_state)}</span> : null}
            </div>
            <div className="mt-3 flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <div className="shift-strip-title">
                {focusBooking ? (focusBooking.client_name || focusBooking.client_id) : "Сейчас без активного заезда"}
              </div>
              {focusBooking ? <div className="shift-strip-meta">{focusBooking.time} · {boatLabel(focusBooking.boat_id)}</div> : null}
            </div>
            <p className="shift-strip-hint">{hint}</p>
          </div>

          <div className="flex min-w-[168px] flex-col items-start gap-2 lg:items-end">
            {focusBooking ? (
              <>
                <div className={`shift-clock shift-clock-${remainingTone}`}>
                  <span>{formatDurationClock(liveRemaining)}</span>
                </div>
                <div className="shift-strip-meta text-xs">
                  План {formatMinutes(focusBooking.planned_duration_minutes)}
                  {isPositive(focusBooking.actual_duration_seconds) ? ` · факт ${formatMinutes(Math.max(Math.round((focusBooking.actual_duration_seconds ?? 0) / 60), 1))}` : ""}
                </div>
              </>
            ) : (
              <div className="shift-strip-meta text-sm">Полоса обновится, как только на смене появится бронь.</div>
            )}
          </div>
        </div>

        <div className="relative z-10 mt-4">
          {focusBooking ? (
            <StatusStepper
              session={session}
              booking={focusBooking}
              onUpdated={(updated) => setFocusBooking((current) => (current ? mergeBookingUpdate(current, updated) : updated))}
            />
          ) : (
            <p className="status-step-reason">Этапы заезда появятся, когда на смене будет бронь.</p>
          )}
          {link && !linkIsHere ? (
            <Link to={link.to} className="mt-2 inline-flex min-h-11 items-center text-sm font-bold text-[color:var(--accent)] underline decoration-dotted underline-offset-4 hover:decoration-solid">
              {link.label} →
            </Link>
          ) : null}
        </div>
      </div>
    </div>
  );
}

/** Куда ведёт ссылка «Открыть…» из живой полосы — туда, где с бронью работают целиком. */
function getStripLink(role: StaffSession["role"], booking: BookingItem, compact: boolean): { to: string; label: string } | null {
  if (compact) {
    if (role === "admin" || role === "operator" || role === "pilot") return { to: "/m/pilot", label: "Открыть очередь катера" };
    return null;
  }
  if (role === "admin" || role === "operator" || role === "coach") {
    const params = new URLSearchParams({ date: booking.date, focus: booking.booking_id });
    return { to: `/bookings?${params.toString()}`, label: "Открыть бронь" };
  }
  if (role === "pilot") return { to: "/pilot", label: "Открыть очередь пилота" };
  return null;
}
