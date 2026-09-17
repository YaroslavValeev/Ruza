import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

import {
  createBooking,
  createCheckin,
  createClient,
  createPayment,
  getAvailability,
  getBookings,
  getClientStats,
  getClients,
  updateBookingStatus,
} from "../api/client";
import { ConsentBadges } from "../components/ConsentBadges";
import { displayGenderForClient } from "../lib/gender";
import {
  AvailabilityItem,
  BookingItem,
  BookingStatus,
  ClientItem,
  ClientStats,
  RideType,
  PaymentMethod,
  StaffSession,
  WetsuitGender,
  WetsuitSize,
} from "../types";

type BookingsPageProps = {
  session: StaffSession;
};

type Toast = { type: "success" | "error"; message: string } | null;
type BookingViewFilter = "all" | BookingStatus;

const OPERATOR_ACTIONS: Partial<Record<BookingStatus, BookingStatus[]>> = {
  confirmed: ["arrived", "late", "cancelled", "no_show"],
  arrived: ["ready", "late", "cancelled"],
  ready: ["cancelled"],
  late: ["arrived", "no_show", "cancelled"],
};

const STATUS_LABELS: Record<BookingStatus, string> = {
  confirmed: "Подтверждена",
  arrived: "Приехал",
  ready: "Готов к старту",
  in_progress: "На воде",
  done: "Завершена",
  late: "Опаздывает",
  no_show: "Не пришел",
  cancelled: "Отменена",
};

const ACTION_LABELS: Record<BookingStatus, string> = {
  confirmed: "Подтвердить",
  arrived: "Отметить приезд",
  ready: "Передать пилоту",
  in_progress: "Старт",
  done: "Завершить",
  late: "Опаздывает",
  no_show: "Не пришел",
  cancelled: "Отменить",
};

const RIDE_TYPES: Array<{ value: RideType; label: string; accent: string }> = [
  { value: "wakeboard", label: "Вейкборд", accent: "text-cyan-200" },
  { value: "surf", label: "Серф", accent: "text-orange-200" },
  { value: "skim", label: "Ским", accent: "text-fuchsia-200" },
];
const DEFAULT_RIDE_TYPE: RideType = "wakeboard";
const WETSUIT_SIZES: WetsuitSize[] = ["XS", "S", "M", "L", "XL", "XXL"];
const WETSUIT_GENDERS: Array<{ value: WetsuitGender; label: string }> = [
  { value: "male", label: "Муж" },
  { value: "female", label: "Жен" },
];
const DEFAULT_WETSUIT_SIZE: WetsuitSize = "M";
const DEFAULT_WETSUIT_GENDER: WetsuitGender = "male";
const PAYMENT_METHODS: Array<{ value: PaymentMethod; label: string }> = [
  { value: "cash", label: "Наличные" },
  { value: "card_terminal", label: "Терминал" },
  { value: "sbp", label: "СБП" },
  { value: "online", label: "Онлайн" },
];
const PAYMENT_STATUS_LABELS: Record<BookingItem["payment_status"], string> = {
  unpaid: "Не оплачено",
  partially_paid: "Частично оплачено",
  paid: "Оплачено",
  overpaid: "Переплата",
  partially_refunded: "Частичный возврат",
  refunded: "Возвращено",
};
const SEASON_START = { month: 6, day: 1 };
const SEASON_END = { month: 10, day: 1 };
const OPERATING_HOURS_LABEL = "07:00-22:00";
const SLOT_RULE_LABEL = "30 минут: 25 мин катание + 5 мин техпауза";

function formatIsoDate(year: number, month: number, day: number): string {
  return `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

function getSeasonBounds(year: number): { start: string; end: string } {
  return {
    start: formatIsoDate(year, SEASON_START.month, SEASON_START.day),
    end: formatIsoDate(year, SEASON_END.month, SEASON_END.day),
  };
}

function getDefaultBookingDate(today = new Date()): string {
  const year = today.getFullYear();
  const { start, end } = getSeasonBounds(year);
  const current = today.toISOString().slice(0, 10);

  if (current < start) {
    return start;
  }
  if (current > end) {
    return getSeasonBounds(year + 1).start;
  }
  return current;
}

function isInSeason(dateText: string): boolean {
  const year = Number(dateText.slice(0, 4));
  const { start, end } = getSeasonBounds(year);
  return dateText >= start && dateText <= end;
}

function getSeasonHint(dateText: string): string | null {
  if (isInSeason(dateText)) {
    return null;
  }
  const year = Number(dateText.slice(0, 4));
  const { start, end } = getSeasonBounds(year);
  return `Дата вне сезона. Клуб работает с ${start} по ${end}, ежедневно ${OPERATING_HOURS_LABEL}.`;
}

function getWetsuitGenderLabel(fullName: string, gender?: WetsuitGender | null): string {
  return displayGenderForClient(fullName, gender);
}

function getRideTypeLabel(rideType?: RideType | null): string {
  const item = RIDE_TYPES.find((entry) => entry.value === rideType);
  return item?.label || "Вейкборд";
}

function getStatusLabel(status: BookingStatus): string {
  return STATUS_LABELS[status] || status;
}

function getActionLabel(status: BookingStatus): string {
  return ACTION_LABELS[status] || status;
}

function getStatusBadge(status: BookingStatus): string {
  if (status === "done") return "game-badge-success";
  if (status === "late" || status === "no_show" || status === "cancelled") return "game-badge-warn";
  return "game-badge-info";
}

function matchesBookingFilter(booking: BookingItem, statusFilter: BookingViewFilter, rideFilter: RideType | "all", wetsuitOnly: boolean): boolean {
  if (statusFilter !== "all" && booking.status !== statusFilter) {
    return false;
  }
  if (rideFilter !== "all" && (booking.ride_type || "wakeboard") !== rideFilter) {
    return false;
  }
  if (wetsuitOnly && !booking.wetsuit_required) {
    return false;
  }
  return true;
}

export function BookingsPage({ session }: BookingsPageProps): JSX.Element {
  const readOnly = session.role === "coach";
  const [date, setDate] = useState(() => getDefaultBookingDate());
  const [selectedClientId, setSelectedClientId] = useState("");
  const [boatId, setBoatId] = useState("");
  const [time, setTime] = useState("");
  const [coachRequired, setCoachRequired] = useState(false);
  const [rideType, setRideType] = useState<RideType>(DEFAULT_RIDE_TYPE);
  const [wetsuitRequired, setWetsuitRequired] = useState(false);
  const [wetsuitSize, setWetsuitSize] = useState<WetsuitSize>(DEFAULT_WETSUIT_SIZE);
  const [wetsuitGender, setWetsuitGender] = useState<WetsuitGender>(DEFAULT_WETSUIT_GENDER);
  const [notes, setNotes] = useState("");
  const [discount, setDiscount] = useState(0);
  const [availability, setAvailability] = useState<AvailabilityItem[]>([]);
  const [bookings, setBookings] = useState<BookingItem[]>([]);
  const [statusFilter, setStatusFilter] = useState<BookingViewFilter>("all");
  const [rideFilter, setRideFilter] = useState<RideType | "all">("all");
  const [wetsuitOnly, setWetsuitOnly] = useState(false);
  const [compactList, setCompactList] = useState(false);
  const [clientsQuery, setClientsQuery] = useState("");
  const [clients, setClients] = useState<ClientItem[]>([]);
  const [clientName, setClientName] = useState("");
  const [clientPhone, setClientPhone] = useState("");
  const [loading, setLoading] = useState(false);
  const [paymentBookingId, setPaymentBookingId] = useState("");
  const [paymentAmount, setPaymentAmount] = useState("");
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>("sbp");
  const [toast, setToast] = useState<Toast>(null);
  const [checkinPhone, setCheckinPhone] = useState("");
  const [checkinClient, setCheckinClient] = useState<ClientItem | null>(null);
  const [clientStats, setClientStats] = useState<ClientStats | null>(null);
  const dateInputRef = useRef<HTMLInputElement | null>(null);
  const dayRequestIdRef = useRef(0);

  const currentSeason = getSeasonBounds(Number(date.slice(0, 4)) || new Date().getFullYear());
  const seasonHint = getSeasonHint(date);

  const selectedClient = clients.find((client) => client.client_id === selectedClientId) || null;
  const selectedSlot = availableSlotKey(boatId, time);

  async function loadDayData(targetDate: string) {
    const requestId = dayRequestIdRef.current + 1;
    dayRequestIdRef.current = requestId;

    const results = await Promise.allSettled([
      getAvailability(session.token, targetDate),
      getBookings(targetDate, session.token),
    ]);

    if (requestId !== dayRequestIdRef.current) {
      return;
    }

    let nextToast: Toast = null;

    const availabilityResult = results[0];
    if (availabilityResult.status === "fulfilled") {
      setAvailability(availabilityResult.value);
    } else {
      nextToast = { type: "error", message: (availabilityResult.reason as Error).message };
    }

    const bookingsResult = results[1];
    if (bookingsResult.status === "fulfilled") {
      setBookings(bookingsResult.value);
    } else if (!nextToast) {
      nextToast = { type: "error", message: (bookingsResult.reason as Error).message };
    }

    if (nextToast) {
      setToast(nextToast);
    }
  }

  useEffect(() => {
    setLoading(true);
    loadDayData(date)
      .catch((err: Error) => setToast({ type: "error", message: err.message }))
      .finally(() => setLoading(false));
  }, [session.token, date]);

  useEffect(() => {
    getClients(clientsQuery, session.token)
      .then(setClients)
      .catch((err: Error) => setToast({ type: "error", message: err.message }));
  }, [clientsQuery, session.token]);

  useEffect(() => {
    if (!checkinPhone.trim()) {
      setCheckinClient(null);
      return;
    }
    const timer = window.setTimeout(() => {
      getClients(checkinPhone.trim(), session.token)
        .then((rows) => setCheckinClient(rows[0] ?? null))
        .catch(() => setCheckinClient(null));
    }, 300);
    return () => window.clearTimeout(timer);
  }, [checkinPhone, session.token]);

  useEffect(() => {
    if (!selectedClientId) {
      setClientStats(null);
      return;
    }
    getClientStats(selectedClientId, session.token)
      .then(setClientStats)
      .catch(() => setClientStats(null));
  }, [selectedClientId, session.token]);

  const availableSlots = useMemo(
    () => availability.filter((slot) => slot.available > 0 && slot.status === "active"),
    [availability],
  );

  const filteredBookings = useMemo(
    () => bookings.filter((booking) => matchesBookingFilter(booking, statusFilter, rideFilter, wetsuitOnly)),
    [bookings, rideFilter, statusFilter, wetsuitOnly],
  );

  const bookingStats = useMemo(() => ({
    total: bookings.length,
    waiting: bookings.filter((booking) => ["confirmed", "arrived", "ready", "late"].includes(booking.status)).length,
    onWater: bookings.filter((booking) => booking.status === "in_progress").length,
    done: bookings.filter((booking) => booking.status === "done").length,
  }), [bookings]);

  function openDatePicker() {
    const input = dateInputRef.current;
    if (!input) return;
    if (typeof input.showPicker === "function") {
      input.showPicker();
      return;
    }
    input.focus();
    input.click();
  }

  const onCreateClient = async (event: FormEvent) => {
    event.preventDefault();
    setToast(null);
    setLoading(true);
    try {
      const client = await createClient(
        {
          full_name: clientName.trim(),
          phone: clientPhone.trim(),
        },
        session.token,
      );
      setSelectedClientId(client.client_id);
      setClientName("");
      setClientPhone("");
      setClientsQuery(client.phone);
      setToast({ type: "success", message: `Клиент создан: ${client.full_name}` });
      const refreshed = await getClients("", session.token);
      setClients(refreshed);
    } catch (err) {
      setToast({ type: "error", message: (err as Error).message });
    } finally {
      setLoading(false);
    }
  };

  const onCreateBooking = async (event: FormEvent) => {
    event.preventDefault();
    setToast(null);
    setLoading(true);
    try {
      const result = await createBooking(session.token, {
        client_id: selectedClientId,
        date,
        time,
        boat_id: boatId,
        coach_required: coachRequired,
        ride_type: rideType,
        wetsuit_required: wetsuitRequired,
        wetsuit_size: wetsuitRequired ? wetsuitSize : undefined,
        wetsuit_gender: wetsuitRequired ? wetsuitGender : undefined,
        discount,
        notes: notes.trim() || undefined,
      });
      setToast({ type: "success", message: `Бронь создана: ${result.booking_id} (${result.total_price} ₽)` });
      setTime("");
      setBoatId("");
      setNotes("");
      setDiscount(0);
      setCoachRequired(false);
      setRideType(DEFAULT_RIDE_TYPE);
      setWetsuitRequired(false);
      setWetsuitSize(DEFAULT_WETSUIT_SIZE);
      setWetsuitGender(DEFAULT_WETSUIT_GENDER);
      await loadDayData(date);
    } catch (err) {
      setToast({ type: "error", message: (err as Error).message });
    } finally {
      setLoading(false);
    }
  };

  const onStatusChange = async (bookingId: string, status: BookingStatus) => {
    setToast(null);
    setLoading(true);
    try {
      await updateBookingStatus(bookingId, status, session.token);
      setToast({ type: "success", message: `Статус обновлён: ${getStatusLabel(status)}` });
      await loadDayData(date);
    } catch (err) {
      setToast({ type: "error", message: (err as Error).message });
    } finally {
      setLoading(false);
    }
  };

  const onPayment = async (booking: BookingItem) => {
    const amountRubles = Number(paymentAmount);
    if (!Number.isFinite(amountRubles) || amountRubles <= 0) {
      setToast({ type: "error", message: "Введите сумму оплаты больше нуля" });
      return;
    }
    const amountMinor = Math.round(amountRubles * 100);
    if (amountMinor > booking.balance_due_minor) {
      setToast({ type: "error", message: "Сумма больше остатка по брони" });
      return;
    }
    setLoading(true);
    setToast(null);
    try {
      await createPayment(session.token, {
        booking_id: booking.booking_id,
        amount_minor: amountMinor,
        method: paymentMethod,
        idempotency_key: `${booking.booking_id}-${Date.now()}-${crypto.randomUUID()}`,
      });
      setToast({ type: "success", message: `Оплата ${amountRubles.toLocaleString("ru-RU")} ₽ зафиксирована` });
      setPaymentBookingId("");
      setPaymentAmount("");
      await loadDayData(date);
    } catch (err) {
      setToast({ type: "error", message: (err as Error).message });
    } finally {
      setLoading(false);
    }
  };

  const handleCheckin = async (status: "arrived" | "ready") => {
    if (!checkinPhone.trim()) {
      setToast({ type: "error", message: "Введите телефон для check-in" });
      return;
    }
    setLoading(true);
    try {
      await createCheckin({ method: "phone", phone: checkinPhone.trim(), date, status }, session.token);
      setToast({ type: "success", message: status === "arrived" ? "Приезд отмечен" : "Готов к старту" });
      await loadDayData(date);
    } catch (err) {
      setToast({ type: "error", message: (err as Error).message });
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="space-y-5 sm:space-y-6">
      <header className="game-panel">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <h1 className="game-heading">Центр бронирования</h1>
            <p className="game-subheading mt-2 max-w-2xl">
              Рабочий экран оператора: выбери спортсмена, назначь слот, добавь экипировку и оформи тренировку за катером.
            </p>
          </div>
          <div className="grid gap-2 sm:grid-cols-3">
            <div className="game-stat min-w-[120px] p-3">
              <div className="text-xs uppercase tracking-[0.12em] text-cyan-100/60">Сезон</div>
              <div className="mt-1 text-sm font-black text-white">01.06 - 01.10</div>
            </div>
            <div className="game-stat min-w-[120px] p-3">
              <div className="text-xs uppercase tracking-[0.12em] text-cyan-100/60">Часы клуба</div>
              <div className="mt-1 text-sm font-black text-white">{OPERATING_HOURS_LABEL}</div>
            </div>
            <div className="game-stat min-w-[120px] p-3">
              <div className="text-xs uppercase tracking-[0.12em] text-cyan-100/60">Слот</div>
              <div className="mt-1 text-sm font-black text-white">{SLOT_RULE_LABEL}</div>
            </div>
          </div>
        </div>
      </header>

      {toast ? (
        <div className={`game-panel ${toast.type === "success" ? "border-emerald-400/30 bg-emerald-950/30 text-emerald-50" : "border-red-400/30 bg-red-950/30 text-red-50"}`}>
          <div className="text-xs font-black uppercase tracking-[0.12em]">{toast.type === "success" ? "Успех" : "Ошибка"}</div>
          <div className="mt-2 text-sm">{toast.message}</div>
        </div>
      ) : null}

      {!readOnly ? (
        <section className="game-panel space-y-3">
          <h2 className="text-lg font-black text-white">Check-in по телефону</h2>
          <div className="flex flex-col gap-3 sm:flex-row">
            <input
              className="game-input flex-1"
              placeholder="+79990000011"
              value={checkinPhone}
              onChange={(event) => setCheckinPhone(event.target.value)}
            />
            <button type="button" className="game-button-secondary" disabled={loading} onClick={() => void handleCheckin("arrived")}>
              Приехал
            </button>
            <button type="button" className="game-button" disabled={loading} onClick={() => void handleCheckin("ready")}>
              Готов
            </button>
          </div>
          {checkinClient ? (
            <div className="flex flex-wrap items-center gap-3 text-sm text-slate-300">
              <span>{checkinClient.full_name}</span>
              <ConsentBadges consentFace={checkinClient.consent_face} consentVoice={checkinClient.consent_voice} compact />
            </div>
          ) : null}
        </section>
      ) : null}

      <div className="grid gap-5 xl:grid-cols-[1.1fr_0.9fr]">
        {!readOnly ? (
        <>
        <section className="game-panel space-y-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="text-xs font-black uppercase tracking-[0.12em] text-cyan-100/70">Шаг 1</div>
              <h2 className="mt-1 text-xl font-black text-white">Спортсмен</h2>
            </div>
            <span className="game-chip text-cyan-100">Поиск + создание</span>
          </div>

          <div>
            <label className="mb-2 block text-sm font-bold text-cyan-100/70">Поиск по имени, телефону или ID</label>
            <input
              value={clientsQuery}
              onChange={(e) => setClientsQuery(e.target.value)}
              placeholder="Например: Ирина или +7..."
              className="game-input"
            />
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            {clients.length === 0 ? (
              <div className="game-card text-sm text-slate-300">Клиенты не найдены.</div>
            ) : (
              clients.map((client) => {
                const active = selectedClientId === client.client_id;
                return (
                  <button
                    key={client.client_id}
                    type="button"
                    onClick={() => setSelectedClientId(client.client_id)}
                    className={`game-card text-left transition ${active ? "border-cyan-300/70 shadow-[0_0_0_1px_rgba(89,227,255,0.25),0_18px_30px_rgba(19,91,176,0.25)]" : "hover:-translate-y-0.5 hover:border-cyan-200/40"}`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="text-lg font-black text-white">{client.full_name}</div>
                        <div className="mt-1 text-sm text-cyan-100/70">{client.phone}</div>
                        <div className="mt-2">
                          <ConsentBadges consentFace={client.consent_face} consentVoice={client.consent_voice} compact />
                        </div>
                      </div>
                      {active ? <span className="game-badge-success">Выбран</span> : <span className="game-badge-info">Выбрать</span>}
                    </div>
                  </button>
                );
              })
            )}
          </div>

          {clientStats ? (
            <div className="game-card grid gap-2 sm:grid-cols-4 text-sm">
              <div>
                <div className="text-xs uppercase text-slate-400">LTV визиты</div>
                <div className="text-lg font-black text-white">{clientStats.visits_count}</div>
              </div>
              <div>
                <div className="text-xs uppercase text-slate-400">Завершённые</div>
                <div className="text-lg font-black text-white">{clientStats.sessions_count}</div>
              </div>
              <div>
                <div className="text-xs uppercase text-slate-400">Выручка</div>
                <div className="text-lg font-black text-white">{clientStats.revenue_estimate.toLocaleString("ru-RU")} ₽</div>
              </div>
              <div>
                <div className="text-xs uppercase text-slate-400">Последний визит</div>
                <div className="text-lg font-black text-white">{clientStats.last_visit_date || "—"}</div>
              </div>
            </div>
          ) : null}

          <form className="game-card space-y-3" onSubmit={onCreateClient}>
            <div className="text-xs font-black uppercase tracking-[0.12em] text-cyan-100/70">Быстрое создание</div>
            <div className="grid gap-3 md:grid-cols-2">
              <input
                value={clientName}
                onChange={(e) => setClientName(e.target.value)}
                placeholder="Имя клиента"
                required
                className="game-input"
              />
              <input
                value={clientPhone}
                onChange={(e) => setClientPhone(e.target.value)}
                placeholder="Телефон"
                required
                className="game-input"
              />
            </div>
            <button className="game-button w-full md:w-auto" disabled={loading} type="submit">
              Создать спортсмена
            </button>
          </form>
        </section>

        <section className="game-panel space-y-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="text-xs font-black uppercase tracking-[0.12em] text-cyan-100/70">Шаги 2–4</div>
              <h2 className="mt-1 text-xl font-black text-white">Слот и экипировка</h2>
            </div>
            <span className="game-chip text-orange-100">Сценарий смены</span>
          </div>

          <div className="grid gap-2 sm:grid-cols-4">
            <div className={`game-card p-3 ${selectedClient ? "border-emerald-300/35" : "opacity-80"}`}>
              <div className="text-xs uppercase tracking-[0.12em] text-cyan-100/60">1. Спортсмен</div>
              <div className="mt-2 text-sm font-black text-white">{selectedClient ? selectedClient.full_name : "Не выбран"}</div>
            </div>
            <div className={`game-card p-3 ${selectedSlot ? "border-emerald-300/35" : "opacity-80"}`}>
              <div className="text-xs uppercase tracking-[0.12em] text-cyan-100/60">2. Слот</div>
              <div className="mt-2 text-sm font-black text-white">{selectedSlot || "Не выбран"}</div>
            </div>
            <div className="game-card p-3 border-fuchsia-300/25">
              <div className="text-xs uppercase tracking-[0.12em] text-cyan-100/60">3. Дисциплина</div>
              <div className="mt-2 text-sm font-black text-white">{getRideTypeLabel(rideType)}</div>
            </div>
            <div className="game-card p-3 border-orange-300/25">
              <div className="text-xs uppercase tracking-[0.12em] text-cyan-100/60">4. Готовность</div>
              <div className="mt-2 text-sm font-black text-white">{selectedClientId && boatId && time ? "Можно запускать" : "Собери шаги"}</div>
            </div>
          </div>

          <form className="space-y-4" onSubmit={onCreateBooking}>
            <div className="game-card space-y-3">
              <div className="text-xs font-black uppercase tracking-[0.12em] text-cyan-100/70">Дата и слот</div>
              <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
                <input
                  ref={dateInputRef}
                  type="date"
                  value={date}
                  min={currentSeason.start}
                  max={currentSeason.end}
                  onChange={(e) => setDate(e.target.value)}
                  required
                  className="game-input"
                />
                <button type="button" onClick={openDatePicker} className="game-button-secondary px-4">
                  Выбрать дату
                </button>
              </div>
              <div className="flex flex-wrap gap-2 text-xs">
                <button type="button" onClick={() => setDate(currentSeason.start)} className="game-chip text-cyan-100">Старт сезона</button>
                <button type="button" onClick={() => setDate(currentSeason.end)} className="game-chip text-cyan-100">Финиш сезона</button>
              </div>
              {seasonHint ? <p className="text-xs text-amber-200">{seasonHint}</p> : null}
              <select
                value={boatId && time ? `${boatId}|${time}` : ""}
                onChange={(e) => {
                  const value = e.target.value;
                  if (!value) {
                    setBoatId("");
                    setTime("");
                    return;
                  }
                  const [nextBoatId, nextTime] = value.split("|");
                  setBoatId(nextBoatId);
                  setTime(nextTime);
                }}
                required
                className="game-input"
              >
                <option value="">Выбери слот</option>
                {availableSlots.map((slot) => (
                  <option key={`${slot.boat_id}-${slot.time}`} value={`${slot.boat_id}|${slot.time}`}>
                    {slot.time} • {slot.boat_id} • свободно {slot.available}
                  </option>
                ))}
              </select>
              {availableSlots.length === 0 ? (
                <p className="text-xs text-slate-400">
                  {seasonHint || "На выбранную дату нет доступных слотов. Проверь schedule, boats, pricing и дату."}
                </p>
              ) : null}
            </div>

            <div className="game-card space-y-3">
              <div className="text-xs font-black uppercase tracking-[0.12em] text-cyan-100/70">Режим катания</div>
              <div className="grid gap-2 sm:grid-cols-3">
                {RIDE_TYPES.map((item) => (
                  <button
                    key={item.value}
                    type="button"
                    onClick={() => setRideType(item.value)}
                    className={`game-tab ${rideType === item.value ? "game-tab-active" : ""} ${item.accent}`}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="game-card space-y-3">
              <div className="text-xs font-black uppercase tracking-[0.12em] text-cyan-100/70">Бонусы и экипировка</div>
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="game-card flex items-center gap-3 p-3">
                  <input type="checkbox" checked={coachRequired} onChange={(e) => setCoachRequired(e.target.checked)} />
                  <span className="text-sm font-black text-white">Нужен тренер</span>
                </label>
                <div>
                  <label className="mb-2 block text-sm font-bold text-cyan-100/70">Скидка</label>
                  <input
                    type="number"
                    min={0}
                    value={discount}
                    onChange={(e) => setDiscount(Number(e.target.value) || 0)}
                    className="game-input"
                  />
                </div>
              </div>

              <div className="grid gap-3 sm:grid-cols-3">
                <label className="game-card flex items-center gap-3 p-3">
                  <input
                    type="checkbox"
                    checked={wetsuitRequired}
                    onChange={(e) => {
                      const checked = e.target.checked;
                      setWetsuitRequired(checked);
                      setWetsuitSize(DEFAULT_WETSUIT_SIZE);
                      setWetsuitGender(DEFAULT_WETSUIT_GENDER);
                    }}
                  />
                  <span className="text-sm font-black text-white">Нужен гидрокостюм</span>
                </label>
                <div>
                  <label className="mb-2 block text-sm font-bold text-cyan-100/70">Пол</label>
                  <select
                    value={wetsuitGender}
                    onChange={(e) => setWetsuitGender(e.target.value as WetsuitGender)}
                    disabled={!wetsuitRequired}
                    className="game-input disabled:opacity-50"
                  >
                    {WETSUIT_GENDERS.map((gender) => (
                      <option key={gender.value} value={gender.value}>{gender.label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="mb-2 block text-sm font-bold text-cyan-100/70">Размер</label>
                  <select
                    value={wetsuitSize}
                    onChange={(e) => setWetsuitSize(e.target.value as WetsuitSize)}
                    disabled={!wetsuitRequired}
                    className="game-input disabled:opacity-50"
                  >
                    {WETSUIT_SIZES.map((size) => (
                      <option key={size} value={size}>{size}</option>
                    ))}
                  </select>
                </div>
              </div>
            </div>

            <div className="game-card space-y-3">
              <div className="text-xs font-black uppercase tracking-[0.12em] text-cyan-100/70">Комментарий к заезду</div>
              <input
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Например: гидрокостюм нужен к старту, клиент новичок"
                className="game-input"
              />
            </div>

            <button type="submit" disabled={loading || !selectedClientId || !boatId || !time} className="game-button w-full">
              {loading ? "Создаём бронь..." : "Запустить бронь"}
            </button>
          </form>
        </section>
        </>
        ) : null}
      </div>

      <section className="game-panel space-y-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="text-xs font-black uppercase tracking-[0.12em] text-cyan-100/70">Список на день</div>
            <h2 className="mt-1 text-xl font-black text-white">Брони на {date}</h2>
          </div>
          <div className="game-chip text-cyan-100">{loading ? "Обновляем" : `${filteredBookings.length} из ${bookings.length} броней`}</div>
        </div>

        <div className="grid gap-2 sm:grid-cols-4">
          <div className="game-stat p-3">
            <div className="text-xs uppercase tracking-[0.12em] text-cyan-100/60">Всего</div>
            <div className="mt-1 text-lg font-black text-white">{bookingStats.total}</div>
          </div>
          <div className="game-stat p-3">
            <div className="text-xs uppercase tracking-[0.12em] text-cyan-100/60">Ожидают</div>
            <div className="mt-1 text-lg font-black text-white">{bookingStats.waiting}</div>
          </div>
          <div className="game-stat p-3">
            <div className="text-xs uppercase tracking-[0.12em] text-cyan-100/60">На воде</div>
            <div className="mt-1 text-lg font-black text-white">{bookingStats.onWater}</div>
          </div>
          <div className="game-stat p-3">
            <div className="text-xs uppercase tracking-[0.12em] text-cyan-100/60">Завершены</div>
            <div className="mt-1 text-lg font-black text-white">{bookingStats.done}</div>
          </div>
        </div>

        <div className="grid gap-3 xl:grid-cols-[1.4fr_1fr_auto]">
          <div className="game-card space-y-3">
            <div className="text-xs font-black uppercase tracking-[0.12em] text-cyan-100/70">Фильтр статуса</div>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              <button type="button" onClick={() => setStatusFilter("all")} className={`game-tab ${statusFilter === "all" ? "game-tab-active" : ""}`}>Все</button>
              {(["confirmed", "arrived", "ready", "in_progress", "done", "late", "cancelled", "no_show"] as BookingStatus[]).map((status) => (
                <button key={status} type="button" onClick={() => setStatusFilter(status)} className={`game-tab ${statusFilter === status ? "game-tab-active" : ""}`}>
                  {getStatusLabel(status)}
                </button>
              ))}
            </div>
          </div>

          <div className="game-card space-y-3">
            <div className="text-xs font-black uppercase tracking-[0.12em] text-cyan-100/70">Фильтр дисциплины</div>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              <button type="button" onClick={() => setRideFilter("all")} className={`game-tab ${rideFilter === "all" ? "game-tab-active" : ""}`}>Все дисциплины</button>
              {RIDE_TYPES.map((item) => (
                <button key={item.value} type="button" onClick={() => setRideFilter(item.value)} className={`game-tab ${rideFilter === item.value ? "game-tab-active" : ""}`}>
                  {item.label}
                </button>
              ))}
            </div>
          </div>

          <div className="game-card space-y-3">
            <div className="text-xs font-black uppercase tracking-[0.12em] text-cyan-100/70">Вид</div>
            <label className="game-card flex items-center gap-3 p-3">
              <input type="checkbox" checked={wetsuitOnly} onChange={(e) => setWetsuitOnly(e.target.checked)} />
              <span className="text-sm font-black text-white">Только с гидрокостюмом</span>
            </label>
            <label className="game-card flex items-center gap-3 p-3">
              <input type="checkbox" checked={compactList} onChange={(e) => setCompactList(e.target.checked)} />
              <span className="text-sm font-black text-white">Компактный список</span>
            </label>
          </div>
        </div>

        <div className={`grid gap-4 ${compactList ? "" : "xl:grid-cols-2"}`}>
          {filteredBookings.map((booking) => (
            <article key={booking.booking_id} className={`game-card ${compactList ? "space-y-3" : "space-y-4"}`}>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="text-xs font-black uppercase tracking-[0.12em] text-cyan-100/60">{booking.time} • {booking.boat_id}</div>
                  <div className="mt-1 text-xl font-black text-white">{booking.client_name || booking.client_id}</div>
                  <div className="text-sm text-cyan-100/70">{booking.client_phone}</div>
                </div>
                <span className={`${getStatusBadge(booking.status)} max-w-[11rem] sm:max-w-[14rem]`}>{getStatusLabel(booking.status)}</span>
              </div>

              <div className={`grid gap-2 ${compactList ? "sm:grid-cols-2" : "sm:grid-cols-4"}`}>
                <div className="game-stat p-3">
                  <div className="text-xs uppercase tracking-[0.12em] text-cyan-100/60">Дисциплина</div>
                  <div className="mt-1 text-sm font-black text-white">{getRideTypeLabel(booking.ride_type)}</div>
                </div>
                <div className="game-stat p-3">
                  <div className="text-xs uppercase tracking-[0.12em] text-cyan-100/60">Гидрокостюм</div>
                  <div className="mt-1 text-sm font-black text-white">{booking.wetsuit_required ? "Да" : "Нет"}</div>
                </div>
                <div className="game-stat p-3">
                  <div className="text-xs uppercase tracking-[0.12em] text-cyan-100/60">Пол / размер</div>
                  <div className="mt-1 text-sm font-black text-white">{getWetsuitGenderLabel(booking.client_name || "", booking.wetsuit_gender)}{booking.wetsuit_size ? ` ${booking.wetsuit_size}` : ""}</div>
                </div>
                <div className="game-stat p-3">
                  <div className="text-xs uppercase tracking-[0.12em] text-cyan-100/60">Цена</div>
                  <div className="mt-1 text-sm font-black text-white">{booking.total_price} ₽</div>
                </div>
              </div>

              <div className="game-card space-y-3 border-emerald-300/20">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <div className="text-xs font-black uppercase tracking-[0.12em] text-cyan-100/60">Оплата</div>
                    <div className="mt-1 text-sm font-black text-white">{PAYMENT_STATUS_LABELS[booking.payment_status]}</div>
                  </div>
                  <div className="text-right">
                    <div className="text-xs text-cyan-100/60">Получено / остаток</div>
                    <div className="text-sm font-black text-white">
                      {(booking.net_paid_minor / 100).toLocaleString("ru-RU")} ₽ / {(booking.balance_due_minor / 100).toLocaleString("ru-RU")} ₽
                    </div>
                  </div>
                </div>
                {!readOnly && booking.balance_due_minor > 0 && !["cancelled", "no_show"].includes(booking.status) ? (
                  paymentBookingId === booking.booking_id ? (
                    <div className="grid gap-2 sm:grid-cols-[1fr_1fr_auto]">
                      <input
                        inputMode="decimal"
                        value={paymentAmount}
                        onChange={(event) => setPaymentAmount(event.target.value)}
                        className="game-input"
                        aria-label="Сумма оплаты в рублях"
                      />
                      <select value={paymentMethod} onChange={(event) => setPaymentMethod(event.target.value as PaymentMethod)} className="game-input">
                        {PAYMENT_METHODS.map((method) => <option key={method.value} value={method.value}>{method.label}</option>)}
                      </select>
                      <button type="button" disabled={loading} onClick={() => void onPayment(booking)} className="game-button px-4">Принять</button>
                    </div>
                  ) : (
                    <button
                      type="button"
                      onClick={() => {
                        setPaymentBookingId(booking.booking_id);
                        setPaymentAmount(String(booking.balance_due_minor / 100));
                      }}
                      className="game-button-secondary w-full"
                    >
                      Принять оплату
                    </button>
                  )
                ) : null}
              </div>

              {booking.notes ? <div className="rounded-2xl border border-cyan-200/10 bg-slate-950/70 px-3 py-3 text-sm text-slate-300">{booking.notes}</div> : null}

              {!readOnly ? (
              <div className="flex flex-wrap gap-2">
                {(OPERATOR_ACTIONS[booking.status] ?? []).map((nextStatus) => (
                  <button
                    key={nextStatus}
                    type="button"
                    onClick={() => void onStatusChange(booking.booking_id, nextStatus)}
                    className="game-button-secondary px-3 text-xs"
                  >
                    {getActionLabel(nextStatus)}
                  </button>
                ))}
              </div>
              ) : null}
            </article>
          ))}

          {filteredBookings.length === 0 ? (
            <div className="game-card text-sm text-slate-300">По текущим фильтрам броней нет.</div>
          ) : null}
        </div>
      </section>
    </section>
  );
}

function availableSlotKey(boatId: string, time: string): string {
  if (!boatId || !time) return "";
  return `${time} • ${boatId}`;
}


