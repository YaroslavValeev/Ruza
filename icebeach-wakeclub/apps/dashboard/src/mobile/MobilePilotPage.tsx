import { useEffect, useMemo, useRef, useState } from "react";

import { getPilotToday } from "../api/client";
import { PilotRideControls } from "../components/shift-timer/PilotRideControls";
import { PilotQueueItem, StaffSession } from "../types";
import {
  getPilotStepHint,
  RIDE_TYPE_LABELS,
  STATUS_LABELS,
  getStatusTone,
  getToday,
} from "./pilot-utils";
import { formatDurationClock } from "../lib/shift-timer";

type MobilePilotPageProps = {
  session: StaffSession;
};

const REFRESH_MS = 30000;

export function MobilePilotPage({ session }: MobilePilotPageProps): JSX.Element {
  const [boatId, setBoatId] = useState(session.boat_id ?? "");
  const [date, setDate] = useState(getToday);
  const [items, setItems] = useState<PilotQueueItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const effectiveBoatId = session.role === "pilot" ? session.boat_id ?? "" : boatId.trim();
  const needsBoatId = session.role !== "pilot" && !effectiveBoatId;

  const loadQueue = async () => {
    if (session.role !== "pilot" && session.role !== "admin" && session.role !== "operator") {
      return;
    }
    if (needsBoatId) {
      setItems([]);
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
      setItems(data);
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
  const mergeItem = (updatedItem: import("../types").BookingItem) => {
    setItems((currentItems) => currentItems.map((item) => (
      item.booking_id === updatedItem.booking_id ? { ...item, ...updatedItem } : item
    )));
  };

  return (
    <div className="space-y-4">
      <section className="game-panel space-y-3">
        <div className="flex items-end justify-between gap-3">
          <div>
            <div className="text-xs font-black uppercase tracking-[0.12em] text-cyan-100/70">Очередь на день</div>
            <p className="mt-1 text-sm text-slate-400">Автообновление каждые 30 сек.</p>
          </div>
          <button type="button" className="game-button-secondary min-h-[48px] px-4" onClick={() => void loadQueue()} disabled={loading}>
            {loading ? "..." : "Обновить"}
          </button>
        </div>

        {session.role === "pilot" ? (
          <div className="game-input flex min-h-[48px] items-center">
            {session.boat_id || "Лодка не привязана к профилю пилота"}
          </div>
        ) : (
          <div>
            <label className="mb-2 block text-sm font-bold text-cyan-100/70">Лодка (boat_id)</label>
            <input
              value={boatId}
              onChange={(event) => setBoatId(event.target.value)}
              className="game-input min-h-[48px]"
              placeholder="boat_id"
            />
          </div>
        )}

        <input type="date" value={date} onChange={(event) => setDate(event.target.value)} className="game-input min-h-[48px]" />
      </section>

      {needsBoatId ? (
        <section className="game-panel text-sm text-amber-100">Укажите boat_id, чтобы загрузить очередь пилота.</section>
      ) : null}

      {error ? <div className="game-panel border-red-400/30 bg-red-950/30 text-red-50">{error}</div> : null}

      {focusRide ? (
        <section className="game-panel space-y-4">
          <div className="text-xs font-black uppercase tracking-[0.12em] text-cyan-100/70">
            {activeRide ? "Сейчас на воде" : "Следующий заезд"}
          </div>
          <div className="text-2xl font-black text-white">{focusRide.client_name || focusRide.client_id}</div>
          <div className="text-sm text-cyan-100/70">
            {focusRide.time} • {RIDE_TYPE_LABELS[(focusRide.ride_type || "wakeboard") as keyof typeof RIDE_TYPE_LABELS]}
          </div>
          <span className={getStatusTone(focusRide.status)}>{STATUS_LABELS[focusRide.status] || focusRide.status}</span>
          <div className="text-sm text-cyan-100/70">
            {formatDurationClock(focusRide.remaining_seconds)} осталось • план {focusRide.planned_duration_minutes} мин
          </div>
          {focusRideHint ? (
            <div className={`rounded-2xl border p-4 text-sm ${focusRideHint.actor === "operator" ? "border-amber-300/20 bg-amber-950/20 text-amber-100" : focusRideHint.actor === "pilot" ? "border-cyan-300/15 bg-cyan-950/20 text-cyan-50" : "border-slate-800 bg-slate-900/70 text-slate-300"}`}>
              <div className="text-xs font-black uppercase tracking-[0.12em]">{focusRideHint.title}</div>
              <div className="mt-2">{focusRideHint.description}</div>
            </div>
          ) : null}

          <PilotRideControls session={session} booking={focusRide} onUpdated={mergeItem} allowTimerControls={session.role === "pilot" || session.role === "admin"} compact />
        </section>
      ) : needsBoatId ? null : (
        <section className="game-panel text-sm text-slate-300">На выбранную дату активных заездов нет.</section>
      )}

      <section className="space-y-3">
        <div className="text-xs font-black uppercase tracking-[0.12em] text-cyan-100/70">Вся очередь ({items.length})</div>
        {items.map((item) => (
          <article key={item.booking_id} className="game-card space-y-3">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-lg font-black text-white">{item.client_name || item.client_id}</div>
                <div className="mt-1 text-sm text-slate-400">
                  {item.time} • {item.boat_id}
                </div>
              </div>
              <span className={getStatusTone(item.status)}>{STATUS_LABELS[item.status] || item.status}</span>
            </div>
            <div className="grid gap-2 sm:grid-cols-3">
              <div className="game-stat p-3">
                <div className="text-xs uppercase tracking-[0.12em] text-cyan-100/60">План</div>
                <div className="mt-1 text-sm font-black text-white">{item.planned_duration_minutes} мин</div>
              </div>
              <div className="game-stat p-3">
                <div className="text-xs uppercase tracking-[0.12em] text-cyan-100/60">Осталось</div>
                <div className="mt-1 text-sm font-black text-white">{formatDurationClock(item.remaining_seconds)}</div>
              </div>
              <div className="game-stat p-3">
                <div className="text-xs uppercase tracking-[0.12em] text-cyan-100/60">Факт</div>
                <div className="mt-1 text-sm font-black text-white">{item.status === "done" || item.actual_duration_seconds > 0 ? formatDurationClock(item.actual_duration_seconds) : "Ещё в процессе"}</div>
              </div>
            </div>
            <PilotRideControls session={session} booking={item} onUpdated={mergeItem} allowTimerControls={session.role === "pilot" || session.role === "admin"} compact />
          </article>
        ))}
      </section>
    </div>
  );
}
