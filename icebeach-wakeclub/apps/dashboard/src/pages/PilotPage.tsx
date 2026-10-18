import { useEffect, useMemo, useState } from "react";

import { getBoats, getPilotToday, updateBookingStatus } from "../api/client";
import { PilotRideControls } from "../components/shift-timer/PilotRideControls";
import { StatusStepper } from "../components/shift-timer/StatusStepper";
import { onBookingUpdated } from "../lib/status-flow";
import { BoardChip } from "../components/equipment/BoardChip";
import { mergeBookingUpdate } from "../lib/equipment";
import { BoatItem, BookingStatus, PilotQueueItem, StaffSession } from "../types";
import {
  getPilotStepHint,
  PILOT_ACTIONS,
  STATUS_LABELS,
  getStatusTone,
  getToday,
} from "../mobile/pilot-utils";
import { formatDurationClock } from "../lib/shift-timer";
import { useRideQueueClock } from "../lib/use-ride-queue-clock";
import { formatCount, formatMinutes, isPositive } from "../lib/format";
import { formatDateRangeRu, formatDayMonth } from "../lib/dates";
import { boatLabel, rememberBoats, rideTypeLabel, useBoatNames } from "../lib/labels";

type PilotPageProps = {
  session: StaffSession;
};

type PilotPeriod = "day" | "week" | "season" | "custom";
type PilotStatusFilter = "all" | "waiting" | "ready" | "on_water" | "done" | "problem";

function getWeekBounds(dateText: string): { from: string; to: string } {
  const current = new Date(`${dateText}T00:00:00`);
  const day = current.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  const monday = new Date(current);
  monday.setDate(current.getDate() + diff);
  const sunday = new Date(monday);
  sunday.setDate(monday.getDate() + 6);
  return {
    from: monday.toISOString().slice(0, 10),
    to: sunday.toISOString().slice(0, 10),
  };
}

function getSeasonBounds(dateText: string): { from: string; to: string } {
  const year = Number(dateText.slice(0, 4)) || new Date().getFullYear();
  return {
    from: `${year}-05-01`,
    to: `${year}-09-25`,
  };
}

function matchesPilotFilter(item: PilotQueueItem, filter: PilotStatusFilter): boolean {
  if (filter === "all") return true;
  if (filter === "waiting") return item.status === "confirmed" || item.status === "arrived" || item.status === "late";
  if (filter === "ready") return item.status === "ready";
  if (filter === "on_water") return item.status === "in_progress";
  if (filter === "done") return item.status === "done";
  if (filter === "problem") return item.status === "late" || item.status === "no_show" || item.status === "cancelled";
  return true;
}

export function PilotPage({ session }: PilotPageProps): JSX.Element {
  useBoatNames(session);
  const [boatId, setBoatId] = useState(session.boat_id ?? "");
  const [boats, setBoats] = useState<BoatItem[]>([]);
  const [period, setPeriod] = useState<PilotPeriod>("day");
  const [date, setDate] = useState(() => getToday());
  const [dateFrom, setDateFrom] = useState(() => getToday());
  const [dateTo, setDateTo] = useState(() => getToday());
  const { items, setQueue, mergeItem, remainingSeconds } = useRideQueueClock();
  const [statusFilter, setStatusFilter] = useState<PilotStatusFilter>("all");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const effectiveBoatId = useMemo(() => (session.role === "pilot" ? session.boat_id ?? "" : boatId.trim()), [boatId, session.boat_id, session.role]);

  useEffect(() => {
    if (session.role === "pilot") return;
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
  }, [boatId, session.role, session.token]);

  useEffect(() => {
    if (period === "week") {
      const bounds = getWeekBounds(date);
      setDateFrom(bounds.from);
      setDateTo(bounds.to);
    }

    if (period === "season") {
      const bounds = getSeasonBounds(date);
      setDateFrom(bounds.from);
      setDateTo(bounds.to);
    }
  }, [period, date]);

  useEffect(() => {
    if (period === "custom" && dateTo < dateFrom) {
      setDateTo(dateFrom);
    }
  }, [dateFrom, dateTo, period]);

  const handleCustomFromChange = (value: string) => {
    setDateFrom(value);
    if (dateTo < value) {
      setDateTo(value);
    }
  };

  const handleCustomToChange = (value: string) => {
    setDateTo(value < dateFrom ? dateFrom : value);
  };

  const loadQueue = async () => {
    if (session.role !== "pilot" && !effectiveBoatId) {
      return;
    }
    setError(null);
    setLoading(true);
    try {
      const useRange = period === "week" || period === "season" || period === "custom";
      const data = await getPilotToday(
        session.token,
        session.role === "pilot" ? undefined : effectiveBoatId,
        useRange ? undefined : date,
        useRange ? dateFrom : undefined,
        useRange ? dateTo : undefined,
      );
      setQueue(data);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (session.role === "pilot" || effectiveBoatId) {
      void loadQueue();
    }
  }, [date, dateFrom, dateTo, effectiveBoatId, period, session.role]);

  const onStatusChange = async (bookingId: string, status: BookingStatus) => {
    setError(null);
    setLoading(true);
    try {
      await updateBookingStatus(bookingId, status, session.token);
      await loadQueue();
    } catch (err) {
      setError((err as Error).message);
      setLoading(false);
    }
  };


  // Статус сменили в живой полосе — обновляем карточку очереди без перезагрузки.
  useEffect(() => onBookingUpdated(mergeItem), [mergeItem]);

  const dateLabel = period === "week" ? "Опорная дата недели" : period === "season" ? "Опорная дата сезона" : "Дата";

  const filteredItems = useMemo(() => items.filter((item) => matchesPilotFilter(item, statusFilter)), [items, statusFilter]);
  const activeRide = useMemo(() => items.find((item) => item.status === "in_progress") ?? null, [items]);
  const nextRide = useMemo(() => items.find((item) => item.status === "ready") ?? items.find((item) => item.status === "arrived") ?? items.find((item) => item.status === "confirmed") ?? null, [items]);
  const nextRideHint = nextRide ? getPilotStepHint(nextRide.status) : null;

  return (
    <section className="space-y-5 sm:space-y-6">
      <header className="game-panel">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <h1 className="game-heading">Панель пилота</h1>
            <p className="game-subheading mt-2 max-w-2xl">
              Последовательный сценарий смены: принять спортсмена, подготовить к старту, вывести на воду и завершить заезд. На каждом этапе доступно одно главное следующее действие.
            </p>
          </div>
          <div className="grid gap-2 sm:grid-cols-3">
            <div className="game-stat p-3">
              <div className="text-xs uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">Катер</div>
              <div className="mt-1 text-sm font-black text-[color:var(--ink)]">{effectiveBoatId ? boatLabel(effectiveBoatId) : "Не выбран"}</div>
            </div>
            <div className="game-stat p-3">
              <div className="text-xs uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">Период</div>
              <div className="mt-1 text-sm font-black text-[color:var(--ink)]">{period === "season" ? "Сезон" : period === "week" ? "Неделя" : period === "custom" ? "Свои даты" : "День"}</div>
            </div>
            <div className="game-stat p-3">
              <div className="text-xs uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">Заездов</div>
              <div className="mt-1 text-sm font-black text-[color:var(--ink)]">{items.length}</div>
            </div>
          </div>
        </div>
      </header>

      <section className="game-panel space-y-4">
        <div>
          <label className="mb-2 block text-sm font-bold text-[color:var(--ink-muted)]">Период</label>
          <div className="grid grid-cols-2 gap-2 lg:grid-cols-4" role="group" aria-label="Период">
            <button type="button" onClick={() => setPeriod("day")} aria-pressed={period === "day"} className={`game-tab ${period === "day" ? "game-tab-active" : ""}`}>День</button>
            <button type="button" onClick={() => setPeriod("week")} aria-pressed={period === "week"} className={`game-tab ${period === "week" ? "game-tab-active" : ""}`}>Неделя</button>
            <button type="button" onClick={() => setPeriod("season")} aria-pressed={period === "season"} className={`game-tab ${period === "season" ? "game-tab-active" : ""}`}>Сезон</button>
            <button type="button" onClick={() => setPeriod("custom")} aria-pressed={period === "custom"} className={`game-tab ${period === "custom" ? "game-tab-active" : ""}`}>Свои даты</button>
          </div>
        </div>

        <div className={`grid gap-4 ${period === "custom" ? "xl:grid-cols-[1fr_220px_220px_180px]" : "xl:grid-cols-[1fr_220px_180px]"}`}>
          <div>
            <label htmlFor={session.role === "pilot" ? undefined : "pilot-boat"} className="mb-2 block text-sm font-bold text-[color:var(--ink-muted)]">Катер</label>
            {session.role === "pilot" ? (
              <div className="game-input flex items-center">{session.boat_id ? boatLabel(session.boat_id) : "Катер не закреплён за пилотом"}</div>
            ) : (
              <select id="pilot-boat" value={boatId} onChange={(e) => setBoatId(e.target.value)} className="game-input">
                {boats.length === 0 ? <option value="">Нет активных катеров</option> : null}
                {boats.map((boat) => (
                  <option key={boat.boat_id} value={boat.boat_id}>
                    {boat.boat_name && boat.boat_name !== boat.boat_id ? boat.boat_name : boatLabel(boat.boat_id)}
                  </option>
                ))}
              </select>
            )}
          </div>

          {period === "custom" ? (
            <>
              <div>
                <label className="mb-2 block text-sm font-bold text-[color:var(--ink-muted)]">Дата с</label>
                <input type="date" value={dateFrom} max={dateTo} onChange={(e) => handleCustomFromChange(e.target.value)} className="game-input" />
              </div>
              <div>
                <label className="mb-2 block text-sm font-bold text-[color:var(--ink-muted)]">Дата по</label>
                <input type="date" value={dateTo} min={dateFrom} onChange={(e) => handleCustomToChange(e.target.value)} className="game-input" />
              </div>
            </>
          ) : (
            <div>
              <label className="mb-2 block text-sm font-bold text-[color:var(--ink-muted)]">{dateLabel}</label>
              <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className="game-input" />
              {period === "season" ? <p className="mt-2 text-xs text-[color:var(--ink-muted)]">Сезон: {formatDateRangeRu(dateFrom, dateTo)}</p> : null}
            </div>
          )}

          <div className="flex items-end">
            <button className="game-button w-full" type="button" onClick={() => void loadQueue()}>
              {loading ? "Обновляем…" : "Загрузить очередь"}
            </button>
          </div>
        </div>
      </section>

      {error ? <div role="alert" className="game-panel border-red-600/25 bg-red-50 text-red-900">{error}</div> : null}

      <section className="grid gap-4">
        <div className="game-panel space-y-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="text-xs font-black uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">Оперативный блок</div>
              <h2 className="mt-1 text-xl font-black text-[color:var(--ink)]">Активный и следующий заезд</h2>
            </div>
            <span className="game-chip">Фильтр: {statusFilter === "all" ? "все" : statusFilter === "waiting" ? "ожидают" : statusFilter === "ready" ? "готовы" : statusFilter === "on_water" ? "на воде" : statusFilter === "done" ? "завершены" : "проблемные"}</span>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="game-card space-y-3">
              <div className="text-xs font-black uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">Сейчас на воде</div>
              {activeRide ? (
                <>
                  <div className="text-lg font-black text-[color:var(--ink)]">{activeRide.client_name}</div>
                  <div className="text-sm text-[color:var(--ink-muted)]">{activeRide.time} · {rideTypeLabel(activeRide.ride_type)}</div>
                  <span className={getStatusTone(activeRide.status)}>{STATUS_LABELS[activeRide.status] || activeRide.status}</span>
                  <div className="text-sm text-[color:var(--ink-muted)]">
                    Осталось {formatDurationClock(remainingSeconds(activeRide))} · план {formatMinutes(activeRide.planned_duration_minutes)}
                  </div>
                </>
              ) : (
                <div className="text-sm text-[color:var(--ink-muted)]">Сейчас нет активного заезда.</div>
              )}
            </div>
            <div className="game-card space-y-3">
              <div className="text-xs font-black uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">Следующий в очереди</div>
              {nextRide ? (
                <>
                  <div className="text-lg font-black text-[color:var(--ink)]">{nextRide.client_name}</div>
                  <div className="text-sm text-[color:var(--ink-muted)]">{nextRide.time} · {rideTypeLabel(nextRide.ride_type)}</div>
                  <span className={getStatusTone(nextRide.status)}>{STATUS_LABELS[nextRide.status] || nextRide.status}</span>
                  <div className="text-sm text-[color:var(--ink-muted)]">План {formatMinutes(nextRide.planned_duration_minutes)} · сетов: {formatCount(nextRide.sets_count)}</div>
                  <BoardChip board={nextRide.board} lastBoard={nextRide.last_board} compact />
                  {nextRideHint && nextRideHint.actor !== "pilot" ? (
                    <div className="rounded-2xl border border-amber-600/25 bg-amber-50 px-3 py-3 text-sm text-amber-900">
                      <div className="text-xs font-black uppercase tracking-[0.12em]">{nextRideHint.title}</div>
                      <div className="mt-2">{nextRideHint.description}</div>
                    </div>
                  ) : null}
                </>
              ) : (
                <div className="text-sm text-[color:var(--ink-muted)]">Следующий заезд пока не сформирован.</div>
              )}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6" role="group" aria-label="Фильтр очереди">
            <button type="button" onClick={() => setStatusFilter("all")} aria-pressed={statusFilter === "all"} className={`game-tab ${statusFilter === "all" ? "game-tab-active" : ""}`}>Все</button>
            <button type="button" onClick={() => setStatusFilter("waiting")} aria-pressed={statusFilter === "waiting"} className={`game-tab ${statusFilter === "waiting" ? "game-tab-active" : ""}`}>Ожидают</button>
            <button type="button" onClick={() => setStatusFilter("ready")} aria-pressed={statusFilter === "ready"} className={`game-tab ${statusFilter === "ready" ? "game-tab-active" : ""}`}>Готовы</button>
            <button type="button" onClick={() => setStatusFilter("on_water")} aria-pressed={statusFilter === "on_water"} className={`game-tab ${statusFilter === "on_water" ? "game-tab-active" : ""}`}>На воде</button>
            <button type="button" onClick={() => setStatusFilter("done")} aria-pressed={statusFilter === "done"} className={`game-tab ${statusFilter === "done" ? "game-tab-active" : ""}`}>Завершены</button>
            <button type="button" onClick={() => setStatusFilter("problem")} aria-pressed={statusFilter === "problem"} className={`game-tab ${statusFilter === "problem" ? "game-tab-active" : ""}`}>Проблемные</button>
          </div>
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        {filteredItems.map((item) => {
          const stepHint = getPilotStepHint(item.status);
          return (
            <article key={item.booking_id} className="game-card space-y-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="text-xs font-black uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">{formatDayMonth(item.date)} · {item.time} · {boatLabel(item.boat_id)}</div>
                  <div className="mt-1 text-xl font-black text-[color:var(--ink)]">{item.client_name || item.client_id}</div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <span className="game-chip">{rideTypeLabel(item.ride_type, { capitalize: true })}</span>
                    <span className={getStatusTone(item.status)}>{STATUS_LABELS[item.status] || item.status}</span>
                  </div>
                </div>
                <div className="game-stat p-3 text-center">
                  <div className="text-xs uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">Сетов</div>
                  <div className="mt-1 text-sm font-black text-[color:var(--ink)]">{formatCount(item.sets_count)}</div>
                </div>
              </div>

              <BoardChip board={item.board} lastBoard={item.last_board} />

              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                <div className="game-stat p-3">
                  <div className="text-xs uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">План</div>
                  <div className="mt-1 text-sm font-black text-[color:var(--ink)]">{formatMinutes(item.planned_duration_minutes)}</div>
                </div>
                <div className="game-stat p-3">
                  <div className="text-xs uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">Осталось</div>
                  <div className="mt-1 text-sm font-black text-[color:var(--ink)]">{formatDurationClock(remainingSeconds(item))}</div>
                </div>
                <div className="game-stat p-3">
                  <div className="text-xs uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">Разминка</div>
                  <div className="mt-1 text-sm font-black text-[color:var(--ink)]">{item.warmup_state === "warmed_up" ? "Размялся" : item.warmup_state === "no_warmup" ? "Без разминки" : "Ещё не отмечена"}</div>
                </div>
                <div className="game-stat p-3">
                  <div className="text-xs uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">Факт</div>
                  <div className="mt-1 text-sm font-black text-[color:var(--ink)]">
                    {isPositive(item.actual_duration_seconds) || (item.status === "done" && item.actual_duration_seconds !== null) ? formatDurationClock(item.actual_duration_seconds) : item.status === "done" ? "—" : "Ещё не начат"}
                  </div>
                </div>
              </div>

              <StatusStepper session={session} booking={item} onUpdated={mergeItem} labels="short" />

              <div className={`rounded-2xl border px-3 py-3 text-sm ${stepHint.actor === "operator" ? "border-amber-600/25 bg-amber-50 text-amber-900" : stepHint.actor === "pilot" ? "border-[color:var(--accent-border)] bg-[color:var(--accent-soft)] text-[color:var(--ink)]" : "border-[color:var(--border)] bg-[color:var(--panel-solid)] text-[color:var(--ink-muted)]"}`}>
                <div className="text-xs font-black uppercase tracking-[0.12em]">{stepHint.title}</div>
                <div className="mt-2">{stepHint.description}</div>
              </div>

              <PilotRideControls
                session={session}
                booking={item}
                onUpdated={mergeItem}
                allowTimerControls={session.role === "pilot" || session.role === "admin"}
              />
            </article>
          );
        })}

        {filteredItems.length === 0 ? (
          <div className="game-card text-sm text-[color:var(--ink-muted)]">
            {session.role === "pilot" && !session.boat_id
              ? "За пилотом пока не закреплён катер. Обратитесь к администратору."
              : "По текущему фильтру заездов нет."}
          </div>
        ) : null}
      </section>
    </section>
  );
}

