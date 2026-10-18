import { useEffect, useMemo, useRef, useState } from "react";

import { getBoats, getPilotToday } from "../api/client";
import { PilotRideControls } from "../components/shift-timer/PilotRideControls";
import { BoardChip } from "../components/equipment/BoardChip";
import { mergeBookingUpdate } from "../lib/equipment";
import { boatLabel, rememberBoats, rideTypeLabel, statusLabel, useBoatNames } from "../lib/labels";
import { BoatItem, PilotQueueItem, StaffSession } from "../types";
import {
  getPilotStepHint,
  getStatusTone,
  getToday,
} from "./pilot-utils";
import { formatDurationClock } from "../lib/shift-timer";
import { useRideQueueClock } from "../lib/use-ride-queue-clock";
import { formatMinutes, isPositive } from "../lib/format";

type MobilePilotPageProps = {
  session: StaffSession;
};

const REFRESH_MS = 30000;

export function MobilePilotPage({ session }: MobilePilotPageProps): JSX.Element {
  useBoatNames(session);
  const [boatId, setBoatId] = useState(session.boat_id ?? "");
  const [boats, setBoats] = useState<BoatItem[]>([]);
  const [date, setDate] = useState(getToday);
  const { items, setQueue, mergeItem, remainingSeconds } = useRideQueueClock();
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const effectiveBoatId = session.role === "pilot" ? session.boat_id ?? "" : boatId.trim();
  const needsBoatId = session.role !== "pilot" && !effectiveBoatId;

  useEffect(() => {
    if (session.role !== "admin" && session.role !== "operator") return;
    let cancelled = false;
    void getBoats(session.token)
      .then((availableBoats) => {
        if (cancelled) return;
        const activeBoats = availableBoats.filter((boat) => boat.is_active);
        rememberBoats(activeBoats);
        setBoats(activeBoats);
        if (!boatId && activeBoats.length > 0) setBoatId(activeBoats[0].boat_id);
      })
      .catch((requestError: Error) => {
        if (!cancelled) setError(requestError.message);
      });
    return () => {
      cancelled = true;
    };
  }, [session.role, session.token]);

  const loadQueue = async () => {
    if (session.role !== "pilot" && session.role !== "admin" && session.role !== "operator") {
      return;
    }
    if (needsBoatId) {
      setQueue([]);
      return;
    }
    setError(null);
    setLoading(true);
    try {
      const data = await getPilotToday(
        session.token,
        session.role === "pilot" ? undefined : effectiveBoatId,
        date,
      );
      setQueue(data);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadQueue();
  }, [date, session.role, session.token, effectiveBoatId]);

  useEffect(() => {
    const id = window.setInterval(() => {
      if (document.visibilityState === "visible") {
        void loadQueue();
      }
    }, REFRESH_MS);
    return () => window.clearInterval(id);
  }, [date, session.role, session.token, effectiveBoatId]);

  const activeRide = useMemo(() => items.find((item) => item.status === "in_progress") ?? null, [items]);
  const nextRide = useMemo(
    () =>
      items.find((item) => item.status === "ready") ??
      items.find((item) => item.status === "arrived") ??
      items.find((item) => item.status === "confirmed") ??
      null,
    [items],
  );

  const focusRide = activeRide ?? nextRide;
  const prevFocusIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (!focusRide || focusRide.status !== "ready") {
      prevFocusIdRef.current = focusRide?.booking_id ?? null;
      return;
    }
    if (prevFocusIdRef.current !== focusRide.booking_id) {
      if (typeof navigator.vibrate === "function") {
        navigator.vibrate([120, 60, 120]);
      }
      prevFocusIdRef.current = focusRide.booking_id;
    }
  }, [focusRide]);

  const focusRideHint = focusRide ? getPilotStepHint(focusRide.status) : null;

  return (
    <div className="space-y-4">
      <section className="game-panel space-y-3">
        <div className="flex items-end justify-between gap-3">
          <div className="min-w-0">
            <div className="text-xs font-black uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">Очередь на день</div>
            <p className="mt-1 text-sm text-[color:var(--ink-muted)]">Автообновление каждые 30 сек.</p>
          </div>
          <button type="button" className="game-button-secondary min-h-[48px] shrink-0 whitespace-nowrap px-4" onClick={() => void loadQueue()} disabled={loading}>
            {loading ? "Обновляем…" : "Обновить"}
          </button>
        </div>

        {session.role === "pilot" ? (
          <div className="game-input flex min-h-[48px] items-center">
            {session.boat_id ? boatLabel(session.boat_id) : "Катер не закреплён за пилотом"}
          </div>
        ) : (
          <div>
            <label htmlFor="m-pilot-boat" className="mb-2 block text-sm font-bold text-[color:var(--ink-muted)]">Катер</label>
            <select id="m-pilot-boat" value={boatId} onChange={(event) => setBoatId(event.target.value)} className="game-input min-h-[48px]">
              <option value="">{boats.length === 0 ? "Нет активных катеров" : "Выберите катер"}</option>
              {boats.map((boat) => (
                <option key={boat.boat_id} value={boat.boat_id}>
                  {boat.boat_name && boat.boat_name !== boat.boat_id ? boat.boat_name : boatLabel(boat.boat_id)}
                </option>
              ))}
            </select>
          </div>
        )}

        <div>
          <label htmlFor="m-pilot-date" className="mb-2 block text-sm font-bold text-[color:var(--ink-muted)]">Дата</label>
          <input id="m-pilot-date" type="date" value={date} onChange={(event) => setDate(event.target.value)} className="game-input min-h-[48px]" />
        </div>
      </section>

      {needsBoatId ? (
        <section className="game-panel text-sm text-[color:var(--ink-muted)]">Выберите катер, чтобы загрузить очередь.</section>
      ) : null}

      {error ? <div role="alert" className="game-panel border-red-600/25 bg-red-50 text-red-900">{error}</div> : null}

      {focusRide ? (
        <section className="game-panel space-y-4">
          <div className="text-xs font-black uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">
            {activeRide ? "Сейчас на воде" : "Следующий заезд"}
          </div>
          <div className="text-2xl font-black text-[color:var(--ink)]">{focusRide.client_name || focusRide.client_id}</div>
          <div className="text-sm text-[color:var(--ink-muted)]">
            {focusRide.time} · {rideTypeLabel(focusRide.ride_type)}
          </div>
          <span className={getStatusTone(focusRide.status)}>{statusLabel(focusRide.status)}</span>
          <BoardChip board={focusRide.board} lastBoard={focusRide.last_board} />
          <div className="text-sm text-[color:var(--ink-muted)]">
            Осталось {formatDurationClock(remainingSeconds(focusRide))} · план {formatMinutes(focusRide.planned_duration_minutes)}
          </div>
          {focusRideHint ? (
            <div className={`rounded-2xl border p-4 text-sm ${focusRideHint.actor === "operator" ? "border-amber-600/25 bg-amber-50 text-amber-900" : focusRideHint.actor === "pilot" ? "border-[color:var(--accent-border)] bg-[color:var(--accent-soft)] text-[color:var(--ink)]" : "border-[color:var(--border)] bg-[color:var(--panel-solid)] text-[color:var(--ink-muted)]"}`}>
              <div className="text-xs font-black uppercase tracking-[0.12em]">{focusRideHint.title}</div>
              <div className="mt-2">{focusRideHint.description}</div>
            </div>
          ) : null}

          <PilotRideControls session={session} booking={focusRide} onUpdated={mergeItem} allowTimerControls={session.role === "pilot" || session.role === "admin"} compact />
        </section>
      ) : needsBoatId ? null : (
        <section className="game-panel text-sm text-[color:var(--ink-muted)]">На выбранную дату активных заездов нет.</section>
      )}

      <section className="space-y-3">
        <div className="text-xs font-black uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">Вся очередь ({items.length})</div>
        {items.map((item) => (
          <article key={item.booking_id} className="game-card space-y-3">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-lg font-black text-[color:var(--ink)]">{item.client_name || item.client_id}</div>
                <div className="mt-1 text-sm text-[color:var(--ink-muted)]">
                  {item.time} · {boatLabel(item.boat_id)} · {rideTypeLabel(item.ride_type)}
                </div>
              </div>
              <span className={getStatusTone(item.status)}>{statusLabel(item.status)}</span>
            </div>
            <BoardChip board={item.board} lastBoard={item.last_board} compact />
            <div className="grid grid-cols-3 gap-2">
              <div className="game-stat p-3">
                <div className="text-xs uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">План</div>
                <div className="mt-1 text-sm font-black text-[color:var(--ink)]">{formatMinutes(item.planned_duration_minutes)}</div>
              </div>
              <div className="game-stat p-3">
                <div className="text-xs uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">Осталось</div>
                <div className="mt-1 text-sm font-black text-[color:var(--ink)]">{formatDurationClock(remainingSeconds(item))}</div>
              </div>
              <div className="game-stat p-3">
                <div className="text-xs uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">Факт</div>
                <div className="mt-1 text-sm font-black text-[color:var(--ink)]">{isPositive(item.actual_duration_seconds) || item.status === "done" ? formatDurationClock(item.actual_duration_seconds) : "—"}</div>
              </div>
            </div>
            <PilotRideControls session={session} booking={item} onUpdated={mergeItem} allowTimerControls={session.role === "pilot" || session.role === "admin"} compact />
          </article>
        ))}
      </section>
    </div>
  );
}
