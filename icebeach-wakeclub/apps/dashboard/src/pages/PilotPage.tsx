import { useEffect, useMemo, useState } from "react";

import { getPilotToday, updateBookingStatus } from "../api/client";
import { BookingStatus, PilotQueueItem, RideType, StaffSession } from "../types";

type PilotPageProps = {
  session: StaffSession;
};

const PILOT_ACTIONS: Partial<Record<BookingStatus, BookingStatus[]>> = {
  confirmed: ["arrived"],
  arrived: ["ready"],
  ready: ["in_progress"],
  late: ["arrived", "no_show"],
  in_progress: ["done"],
};

const STATUS_LABELS: Partial<Record<BookingStatus, string>> = {
  confirmed: "Подтверждена",
  arrived: "Приехал",
  ready: "Готов к старту",
  in_progress: "На воде",
  done: "Завершена",
  late: "Опаздывает",
  no_show: "Не пришел",
  cancelled: "Отменена",
};

const ACTION_LABELS: Partial<Record<BookingStatus, string>> = {
  arrived: "Принять клиента",
  ready: "Подготовить",
  in_progress: "На воду",
  done: "Завершить заезд",
  no_show: "Не пришел",
};

const RIDE_TYPE_LABELS: Record<RideType, string> = {
  wakeboard: "Вейкборд",
  surf: "Серф",
  skim: "Ским",
};

type PilotPeriod = "day" | "week" | "season" | "custom";
type PilotStatusFilter = "all" | "waiting" | "ready" | "on_water" | "done" | "problem";

function getToday(): string {
  return new Date().toISOString().slice(0, 10);
}

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
    from: `${year}-06-01`,
    to: `${year}-10-01`,
  };
}

function getStatusTone(status: BookingStatus): string {
  if (status === "done") return "game-badge-success";
  if (status === "late" || status === "no_show" || status === "cancelled") return "game-badge-warn";
  return "game-badge-info";
}

function getProgressStep(status: BookingStatus): number {
  switch (status) {
    case "confirmed":
      return 1;
    case "arrived":
      return 2;
    case "ready":
      return 3;
    case "in_progress":
      return 4;
    case "done":
      return 5;
    default:
      return 1;
  }
}

function matchesPilotFilter(item: PilotQueueItem, filter: PilotStatusFilter): boolean {
  if (filter === "all") return true;
  if (filter === "waiting") return item.status === "confirmed" || item.status === "arrived";
  if (filter === "ready") return item.status === "ready";
  if (filter === "on_water") return item.status === "in_progress";
  if (filter === "done") return item.status === "done";
  if (filter === "problem") return item.status === "late" || item.status === "no_show" || item.status === "cancelled";
  return true;
}

export function PilotPage({ session }: PilotPageProps): JSX.Element {
  const [boatId, setBoatId] = useState(session.boat_id ?? "");
  const [period, setPeriod] = useState<PilotPeriod>("day");
  const [date, setDate] = useState(() => getToday());
  const [dateFrom, setDateFrom] = useState(() => getToday());
  const [dateTo, setDateTo] = useState(() => getToday());
  const [items, setItems] = useState<PilotQueueItem[]>([]);
  const [statusFilter, setStatusFilter] = useState<PilotStatusFilter>("all");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const effectiveBoatId = useMemo(() => (session.role === "pilot" ? session.boat_id ?? "" : boatId.trim()), [boatId, session.boat_id, session.role]);

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
      setItems(data);
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

  const dateLabel = period === "week" ? "Опорная дата недели" : period === "season" ? "Опорная дата сезона" : "Дата";

  const filteredItems = useMemo(() => items.filter((item) => matchesPilotFilter(item, statusFilter)), [items, statusFilter]);
  const activeRide = useMemo(() => items.find((item) => item.status === "in_progress") ?? null, [items]);
  const nextRide = useMemo(() => items.find((item) => item.status === "ready") ?? items.find((item) => item.status === "arrived") ?? items.find((item) => item.status === "confirmed") ?? null, [items]);

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
              <div className="text-xs uppercase tracking-[0.12em] text-cyan-100/60">Лодка</div>
              <div className="mt-1 text-sm font-black text-white">{effectiveBoatId || "Не задана"}</div>
            </div>
            <div className="game-stat p-3">
              <div className="text-xs uppercase tracking-[0.12em] text-cyan-100/60">Период</div>
              <div className="mt-1 text-sm font-black text-white">{period === "season" ? "Сезон" : period === "week" ? "Неделя" : period === "custom" ? "Свои даты" : "День"}</div>
            </div>
            <div className="game-stat p-3">
              <div className="text-xs uppercase tracking-[0.12em] text-cyan-100/60">Карточек</div>
              <div className="mt-1 text-sm font-black text-white">{items.length}</div>
            </div>
          </div>
        </div>
      </header>

      <section className="game-panel space-y-4">
        <div>
          <label className="mb-2 block text-sm font-bold text-cyan-100/70">Период</label>
          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
            <button type="button" onClick={() => setPeriod("day")} className={`game-tab ${period === "day" ? "game-tab-active" : ""}`}>День</button>
            <button type="button" onClick={() => setPeriod("week")} className={`game-tab ${period === "week" ? "game-tab-active" : ""}`}>Неделя</button>
            <button type="button" onClick={() => setPeriod("season")} className={`game-tab ${period === "season" ? "game-tab-active" : ""}`}>Сезон</button>
            <button type="button" onClick={() => setPeriod("custom")} className={`game-tab ${period === "custom" ? "game-tab-active" : ""}`}>Свои даты</button>
          </div>
        </div>

        <div className={`grid gap-4 ${period === "custom" ? "xl:grid-cols-[1fr_220px_220px_180px]" : "xl:grid-cols-[1fr_220px_180px]"}`}>
          <div>
            <label className="mb-2 block text-sm font-bold text-cyan-100/70">Лодка</label>
            {session.role === "pilot" ? (
              <div className="game-input flex items-center">{session.boat_id || "Лодка не привязана к профилю пилота"}</div>
            ) : (
              <input value={boatId} onChange={(e) => setBoatId(e.target.value)} placeholder="boat_id" className="game-input" />
            )}
          </div>

          {period === "custom" ? (
            <>
              <div>
                <label className="mb-2 block text-sm font-bold text-cyan-100/70">Дата с</label>
                <input type="date" value={dateFrom} max={dateTo} onChange={(e) => handleCustomFromChange(e.target.value)} className="game-input" />
              </div>
              <div>
                <label className="mb-2 block text-sm font-bold text-cyan-100/70">Дата по</label>
                <input type="date" value={dateTo} min={dateFrom} onChange={(e) => handleCustomToChange(e.target.value)} className="game-input" />
              </div>
            </>
          ) : (
            <div>
              <label className="mb-2 block text-sm font-bold text-cyan-100/70">{dateLabel}</label>
              <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className="game-input" />
              {period === "season" ? <p className="mt-2 text-xs text-slate-400">Сезон: {dateFrom} - {dateTo}</p> : null}
            </div>
          )}

          <div className="flex items-end">
            <button className="game-button w-full" type="button" onClick={() => void loadQueue()}>
              {loading ? "Обновляем..." : "Загрузить очередь"}
            </button>
          </div>
        </div>
      </section>

      {error ? <div className="game-panel border-red-400/30 bg-red-950/30 text-red-50">{error}</div> : null}

      <section className="grid gap-4 xl:grid-cols-2">
        <div className="game-panel space-y-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="text-xs font-black uppercase tracking-[0.12em] text-cyan-100/70">Оперативный блок</div>
              <h2 className="mt-1 text-xl font-black text-white">Активный и следующий заезд</h2>
            </div>
            <span className="game-chip text-cyan-100">Фильтр: {statusFilter === "all" ? "Все" : statusFilter === "waiting" ? "Ожидают" : statusFilter === "ready" ? "Готовы" : statusFilter === "on_water" ? "На воде" : statusFilter === "done" ? "Завершены" : "Проблемные"}</span>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="game-card space-y-3">
              <div className="text-xs font-black uppercase tracking-[0.12em] text-cyan-100/70">Сейчас на воде</div>
              {activeRide ? (
                <>
                  <div className="text-lg font-black text-white">{activeRide.client_name}</div>
                  <div className="text-sm text-cyan-100/70">{activeRide.time} • {RIDE_TYPE_LABELS[(activeRide.ride_type || "wakeboard") as RideType]}</div>
                  <span className={getStatusTone(activeRide.status)}>{STATUS_LABELS[activeRide.status] || activeRide.status}</span>
                </>
              ) : (
                <div className="text-sm text-slate-300">Сейчас нет активного заезда.</div>
              )}
            </div>
            <div className="game-card space-y-3">
              <div className="text-xs font-black uppercase tracking-[0.12em] text-cyan-100/70">Следующий в очереди</div>
              {nextRide ? (
                <>
                  <div className="text-lg font-black text-white">{nextRide.client_name}</div>
                  <div className="text-sm text-cyan-100/70">{nextRide.time} • {RIDE_TYPE_LABELS[(nextRide.ride_type || "wakeboard") as RideType]}</div>
                  <span className={getStatusTone(nextRide.status)}>{STATUS_LABELS[nextRide.status] || nextRide.status}</span>
                </>
              ) : (
                <div className="text-sm text-slate-300">Следующий заезд пока не сформирован.</div>
              )}
            </div>
          </div>

          <div className="grid gap-2 sm:grid-cols-3 xl:grid-cols-6">
            <button type="button" onClick={() => setStatusFilter("all")} className={`game-tab ${statusFilter === "all" ? "game-tab-active" : ""}`}>Все</button>
            <button type="button" onClick={() => setStatusFilter("waiting")} className={`game-tab ${statusFilter === "waiting" ? "game-tab-active" : ""}`}>Ожидают</button>
            <button type="button" onClick={() => setStatusFilter("ready")} className={`game-tab ${statusFilter === "ready" ? "game-tab-active" : ""}`}>Готовы</button>
            <button type="button" onClick={() => setStatusFilter("on_water")} className={`game-tab ${statusFilter === "on_water" ? "game-tab-active" : ""}`}>На воде</button>
            <button type="button" onClick={() => setStatusFilter("done")} className={`game-tab ${statusFilter === "done" ? "game-tab-active" : ""}`}>Завершены</button>
            <button type="button" onClick={() => setStatusFilter("problem")} className={`game-tab ${statusFilter === "problem" ? "game-tab-active" : ""}`}>Проблемные</button>
          </div>
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        {filteredItems.map((item) => {
          const nextActions = PILOT_ACTIONS[item.status] ?? [];
          const nextPrimaryAction = nextActions[0];
          const progressStep = getProgressStep(item.status);
          return (
            <article key={item.booking_id} className="game-card space-y-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="text-xs font-black uppercase tracking-[0.12em] text-cyan-100/60">{item.date} • {item.time} • {item.boat_id}</div>
                  <div className="mt-1 text-xl font-black text-white">{item.client_name || item.client_id}</div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <span className="game-chip text-cyan-100">{RIDE_TYPE_LABELS[(item.ride_type || "wakeboard") as RideType]}</span>
                    <span className={getStatusTone(item.status)}>{STATUS_LABELS[item.status] || item.status}</span>
                  </div>
                </div>
                <div className="game-stat p-3 text-center">
                  <div className="text-xs uppercase tracking-[0.12em] text-cyan-100/60">Заезд</div>
                  <div className="mt-1 text-sm font-black text-white">#{item.booking_id.slice(-6)}</div>
                </div>
              </div>

              <div className="grid grid-cols-5 gap-2">
                {[1, 2, 3, 4, 5].map((step) => (
                  <div key={step} className={`rounded-2xl px-2 py-2 text-center text-xs font-black uppercase tracking-[0.08em] ${step <= progressStep ? "bg-cyan-400/20 text-cyan-50 ring-1 ring-cyan-300/35" : "bg-slate-950/80 text-slate-500 ring-1 ring-slate-800"}`}>
                    {step === 1 ? "Принят" : step === 2 ? "На базе" : step === 3 ? "Готов" : step === 4 ? "Вода" : "Финиш"}
                  </div>
                ))}
              </div>

              {nextPrimaryAction ? (
                <button
                  type="button"
                  onClick={() => void onStatusChange(item.booking_id, nextPrimaryAction)}
                  className="game-button w-full"
                >
                  {getPrimaryActionText(nextPrimaryAction)}
                </button>
              ) : (
                <div className="game-stat p-3 text-center text-sm font-black text-white">Для этого заезда следующий шаг не требуется.</div>
              )}

              {nextActions.length > 1 ? (
                <div className="flex flex-wrap gap-2">
                  {nextActions.slice(1).map((nextStatus) => (
                    <button
                      key={nextStatus}
                      type="button"
                      onClick={() => void onStatusChange(item.booking_id, nextStatus)}
                      className="game-button-secondary px-3 text-xs"
                    >
                      {ACTION_LABELS[nextStatus] || nextStatus}
                    </button>
                  ))}
                </div>
              ) : null}
            </article>
          );
        })}

        {filteredItems.length === 0 ? (
          <div className="game-card text-sm text-slate-300">
            {session.role === "pilot" && !session.boat_id
              ? "У пилота пока не задана лодка через boats.pilot_user_id."
              : "По текущему фильтру карточек нет."}
          </div>
        ) : null}
      </section>
    </section>
  );
}

function getPrimaryActionText(status: BookingStatus): string {
  switch (status) {
    case "arrived":
      return "Шаг 1. Принять спортсмена";
    case "ready":
      return "Шаг 2. Подготовить к старту";
    case "in_progress":
      return "Шаг 3. Вывести на воду";
    case "done":
      return "Шаг 4. Завершить заезд";
    case "no_show":
      return "Спортсмен не пришел";
    default:
      return ACTION_LABELS[status] || status;
  }
}

