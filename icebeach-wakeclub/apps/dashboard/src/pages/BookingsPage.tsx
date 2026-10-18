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
import { ClientPrefsPanel } from "../components/equipment/ClientPrefsPanel";
import { PilotRideControls } from "../components/shift-timer/PilotRideControls";
import { emitShiftLiveRefresh } from "../components/shift-timer/LiveShiftStrip";
import { displayGenderForClient } from "../lib/gender";
import { boardTitle, drinkLabel, hasIssuedEquipment, mergeBookingUpdate, supportsClientPrefs, useInventory, visitOrdinal, wetsuitTitle } from "../lib/equipment";
import { formatDateRu, formatDayMonth, formatPhoneRu, localTodayIso } from "../lib/dates";
import { onBookingUpdated } from "../lib/status-flow";
import { useSearchParams } from "react-router-dom";
import { formatCount, formatMinutes, formatRub, formatRubMinor, isPositive, toFiniteNumber } from "../lib/format";
import { BOOKING_STATUS_LABELS, boatLabel, rideTypeLabel, useBoatNames } from "../lib/labels";
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

const STATUS_LABELS: Record<BookingStatus, string> = BOOKING_STATUS_LABELS;
/** «Как в прошлый раз» раскрыт после прибытия: выдача снаряжения. */
const PREFS_PANEL_STATUSES = new Set<BookingStatus>(["arrived", "ready", "in_progress"]);

const ACTION_LABELS: Record<BookingStatus, string> = {
  confirmed: "Подтвердить",
  arrived: "Отметить прибытие",
  ready: "Передать пилоту",
  in_progress: "Старт",
  done: "Завершить",
  late: "Опаздывает",
  no_show: "Неявка",
  cancelled: "Отменить",
};

const RIDE_TYPES: Array<{ value: RideType; label: string; accent: string }> = [
  { value: "wakeboard", label: rideTypeLabel("wakeboard", { capitalize: true }), accent: "text-teal-800" },
  { value: "surf", label: rideTypeLabel("surf", { capitalize: true }), accent: "text-amber-800" },
  { value: "skim", label: rideTypeLabel("skim", { capitalize: true }), accent: "text-stone-700" },
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
const OPERATING_HOURS_LABEL = "07:00–22:00";
const SLOT_RULE_VALUE = "30 мин";
const SLOT_RULE_DETAILS = "25 мин катание · 5 мин техпауза";

function offsetSlotTime(timeText: string, slotOffset: number): string {
  const [hourText, minuteText] = timeText.split(":");
  const baseMinutes = Number(hourText) * 60 + Number(minuteText);
  const shifted = baseMinutes + slotOffset * 30;
  const hours = Math.floor(shifted / 60);
  const minutes = shifted % 60;
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`;
}

function formatIsoDate(year: number, month: number, day: number): string {
  return `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

function getSeasonBounds(year: number): { start: string; end: string } {
  return {
    start: formatIsoDate(year, SEASON_START.month, SEASON_START.day),
    end: formatIsoDate(year, SEASON_END.month, SEASON_END.day),
  };
}

/**
 * Дата по умолчанию. Сегодня — если сегодня день сезона.
 * Вне сезона — ближайший предстоящий день сезона (до сезона — его начало, после — начало следующего);
 * но если на сегодня есть брони (рабочий день вне календаря, демо), экран откроется на сегодня — см. эффект ниже.
 */
function getDefaultBookingDate(today: string = localTodayIso()): string {
  const year = Number(today.slice(0, 4));
  const { start, end } = getSeasonBounds(year);
  if (today < start) {
    return start;
  }
  if (today > end) {
    return getSeasonBounds(year + 1).start;
  }
  return today;
}

function isIsoDate(value: string | null): value is string {
  return Boolean(value && /^\d{4}-\d{2}-\d{2}$/.test(value) && !Number.isNaN(Date.parse(value)));
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
  return `Дата вне сезона. Клуб работает с ${formatDateRu(start)} по ${formatDateRu(end)}, ежедневно ${OPERATING_HOURS_LABEL}.`;
}

function getWetsuitGenderLabel(fullName: string, gender?: WetsuitGender | null): string {
  return displayGenderForClient(fullName, gender);
}

function getRideTypeLabel(rideType?: RideType | null): string {
  return rideTypeLabel(rideType, { capitalize: true });
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
  useBoatNames(session);
  const [searchParams] = useSearchParams();
  const urlDate = searchParams.get("date");
  const urlFocus = searchParams.get("focus") ?? "";
  const today = localTodayIso();
  // Вне сезона сначала открываем сегодня: если броней на сегодня нет — переходим на ближайший день сезона.
  const [date, setDate] = useState(() => (isIsoDate(urlDate) ? urlDate : today));
  const [dateResolved, setDateResolved] = useState(() => isIsoDate(urlDate) || isInSeason(today));
  /** Бронь, открытая из живой полосы (?focus=…): подсвечиваем и прокручиваем к ней. */
  const [highlightId, setHighlightId] = useState(urlFocus);
  const [selectedClientId, setSelectedClientId] = useState("");
  const [boatId, setBoatId] = useState("");
  const [time, setTime] = useState("");
  const [coachRequired, setCoachRequired] = useState(false);
  const [rideType, setRideType] = useState<RideType>(DEFAULT_RIDE_TYPE);
  const [setsCount, setSetsCount] = useState(1);
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
  /** Бронь, по которой только что отметили прибытие: карточка «Как в прошлый раз». */
  const [focusBookingId, setFocusBookingId] = useState("");
  const inventory = useInventory(session.token, ["admin", "operator", "coach"].includes(session.role));
  const dateInputRef = useRef<HTMLInputElement | null>(null);
  const dayRequestIdRef = useRef(0);

  const currentSeason = getSeasonBounds(Number(date.slice(0, 4)) || new Date().getFullYear());
  const seasonHint = getSeasonHint(date);

  const selectedClient = clients.find((client) => client.client_id === selectedClientId) || null;
  const focusBooking = focusBookingId ? bookings.find((booking) => booking.booking_id === focusBookingId) ?? null : null;
  const selectedSlot = availableSlotKey(boatId, time);

  function mergeUpdatedBooking(updatedBooking: BookingItem) {
    setBookings((currentBookings) => currentBookings.map((booking) => (
      booking.booking_id === updatedBooking.booking_id ? mergeBookingUpdate(booking, updatedBooking) : booking
    )));
  }

  /** Ответ выдачи снаряжения полный (с last_time) — заменяем карточку целиком. */
  function replaceBooking(updatedBooking: BookingItem) {
    setBookings((currentBookings) => currentBookings.map((booking) => (
      booking.booking_id === updatedBooking.booking_id ? { ...booking, ...updatedBooking } : booking
    )));
  }

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
    if (dateResolved) return;
    let cancelled = false;
    getBookings(today, session.token)
      .then((rows) => {
        if (!cancelled && rows.length === 0) setDate(getDefaultBookingDate(today));
      })
      .catch(() => undefined)
      .finally(() => {
        if (!cancelled) setDateResolved(true);
      });
    return () => {
      cancelled = true;
    };
  }, [dateResolved, today, session.token]);

  // Переход из живой полосы на уже открытый экран: подхватываем новые ?date и ?focus.
  useEffect(() => {
    if (isIsoDate(urlDate)) {
      setDate(urlDate);
      setDateResolved(true);
    }
    if (urlFocus) {
      setHighlightId(urlFocus);
      setStatusFilter("all");
    }
  }, [urlDate, urlFocus]);

  useEffect(() => {
    if (!highlightId) return;
    const element = document.getElementById(`booking-${highlightId}`);
    if (element) element.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [highlightId, bookings]);

  // Статус сменили в живой полосе — обновляем карточку в списке.
  useEffect(() => onBookingUpdated(mergeUpdatedBooking), []);

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
    () => availability.filter((slot) => {
      if (slot.available <= 0 || slot.status !== "active") {
        return false;
      }
      for (let index = 0; index < setsCount; index += 1) {
        const timeCandidate = offsetSlotTime(slot.time, index);
        const linkedSlot = availability.find((item) => item.boat_id === slot.boat_id && item.time === timeCandidate);
        if (!linkedSlot || linkedSlot.status !== "active" || linkedSlot.available <= 0) {
          return false;
        }
      }
      return true;
    }),
    [availability, setsCount],
  );

  const filteredBookings = useMemo(
    () => bookings.filter((booking) => matchesBookingFilter(booking, statusFilter, rideFilter, wetsuitOnly)),
    [bookings, rideFilter, statusFilter, wetsuitOnly],
  );

  const bookingStats = useMemo(() => ({
    total: bookings.length,
    // "Ожидают" в верхнем счётчике = ещё не отмечен фактический приезд.
    waiting: bookings.filter((booking) => ["confirmed", "late"].includes(booking.status)).length,
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
        sets_count: setsCount,
        wetsuit_required: wetsuitRequired,
        wetsuit_size: wetsuitRequired ? wetsuitSize : undefined,
        wetsuit_gender: wetsuitRequired ? wetsuitGender : undefined,
        discount,
        notes: notes.trim() || undefined,
      });
      setToast({ type: "success", message: `Бронь создана: ${formatDayMonth(date)}, ${time}, ${boatLabel(boatId)} — ${formatRub(result.total_price)}` });
      setTime("");
      setBoatId("");
      setNotes("");
      setDiscount(0);
      setCoachRequired(false);
      setRideType(DEFAULT_RIDE_TYPE);
      setSetsCount(1);
      setWetsuitRequired(false);
      setWetsuitSize(DEFAULT_WETSUIT_SIZE);
      setWetsuitGender(DEFAULT_WETSUIT_GENDER);
      emitShiftLiveRefresh();
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
      const updatedBooking = await updateBookingStatus(bookingId, status, session.token);
      mergeUpdatedBooking(updatedBooking);
      setToast({ type: "success", message: `Статус обновлён: ${getStatusLabel(status)}` });
      emitShiftLiveRefresh();
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
      setToast({ type: "success", message: `Оплата ${amountRubles.toLocaleString("ru-RU")} ₽ зафиксирована в журнале оплат` });
      setPaymentBookingId("");
      setPaymentAmount("");
      await loadDayData(date);
    } catch (err) {
      setToast({ type: "error", message: (err as Error).message });
    } finally {
      setLoading(false);
    }
  };

  const handleCheckin = async (status: "arrived" | "late") => {
    if (!checkinPhone.trim()) {
      setToast({ type: "error", message: "Введите телефон клиента" });
      return;
    }
    setLoading(true);
    try {
      // Прибытие бывает только сегодня — независимо от даты, выбранной в форме брони.
      const checkin = await createCheckin({ method: "phone", phone: checkinPhone.trim(), date: today, status }, session.token);
      setBookings((currentBookings) => currentBookings.map((booking) => (
        booking.booking_id === checkin.booking_id ? { ...booking, status: checkin.status as BookingStatus } : booking
      )));
      if (status === "arrived" && checkin.booking_id) {
        setFocusBookingId(checkin.booking_id);
      }
      setToast({ type: "success", message: status === "arrived" ? "Прибытие отмечено" : "Отмечено опоздание клиента" });
      emitShiftLiveRefresh();
      if (date !== today) {
        setDate(today);
      } else {
        await loadDayData(date);
      }
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
              Рабочий экран оператора: выберите спортсмена, назначьте слот, добавьте экипировку и оформите заезд.
            </p>
          </div>
          <div className="grid gap-2 sm:grid-cols-3">
            <div className="game-stat min-w-[120px] p-3">
              <div className="text-xs uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">Сезон</div>
              <div className="mt-1 text-sm font-black text-[color:var(--ink)]">01.06–01.10</div>
            </div>
            <div className="game-stat min-w-[120px] p-3">
              <div className="text-xs uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">Часы клуба</div>
              <div className="mt-1 text-sm font-black text-[color:var(--ink)]">{OPERATING_HOURS_LABEL}</div>
            </div>
            <div className="game-stat min-w-[120px] p-3">
              <div className="text-xs uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">Слот</div>
              <div className="mt-1 text-sm font-black text-[color:var(--ink)]">{SLOT_RULE_VALUE}</div>
              <div className="mt-0.5 text-xs leading-snug text-[color:var(--ink-muted)]">{SLOT_RULE_DETAILS}</div>
            </div>
          </div>
        </div>
      </header>

      {toast ? (
        <div className={`game-panel ${toast.type === "success" ? "border-emerald-600/25 bg-emerald-50 text-emerald-900" : "border-red-600/25 bg-red-50 text-red-900"}`}>
          <div className="text-xs font-black uppercase tracking-[0.12em]">{toast.type === "success" ? "Готово" : "Ошибка"}</div>
          <div className="mt-2 text-sm">{toast.message}</div>
        </div>
      ) : null}

      {!readOnly ? (
        <section className="game-panel space-y-3">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="text-lg font-black text-[color:var(--ink)]">Отметка о прибытии</h2>
            <span className="text-xs font-bold text-[color:var(--ink-muted)]">Сегодня, {formatDateRu(today)}</span>
          </div>
          <label htmlFor="checkin-phone" className="block text-sm font-bold text-[color:var(--ink-muted)]">Телефон клиента</label>
          <div className="flex flex-col gap-3 sm:flex-row">
            <input
              id="checkin-phone"
              className="game-input flex-1"
              placeholder="+7 999 000-00-11"
              type="tel"
              inputMode="tel"
              value={checkinPhone}
              onChange={(event) => setCheckinPhone(event.target.value)}
            />
            <button type="button" className="game-button px-5" disabled={loading} onClick={() => void handleCheckin("arrived")}>
              Отметить прибытие
            </button>
            <button type="button" className="game-button-secondary px-5" disabled={loading} onClick={() => void handleCheckin("late")}>
              Опаздывает
            </button>
          </div>
          {checkinClient ? (
            <div className="flex flex-wrap items-center gap-3 text-sm text-[color:var(--ink-muted)]">
              <span>{checkinClient.full_name}</span>
              <ConsentBadges consentFace={checkinClient.consent_face} consentVoice={checkinClient.consent_voice} compact />
            </div>
          ) : null}
        </section>
      ) : null}

      {!readOnly && focusBooking && supportsClientPrefs(focusBooking) ? (
        <section className="game-panel space-y-4" aria-labelledby="focus-booking-name">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="text-xs font-black uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">
                {formatDayMonth(focusBooking.date)} · {focusBooking.time} · {boatLabel(focusBooking.boat_id)}
              </div>
              <h2 id="focus-booking-name" className="mt-1 text-2xl font-black text-[color:var(--ink)]">{focusBooking.client_name || focusBooking.client_id}</h2>
              <div className="mt-2 flex flex-wrap gap-2">
                <span className="game-chip">{getRideTypeLabel(focusBooking.ride_type)}</span>
                <span className="game-chip">{getStatusLabel(focusBooking.status)}</span>
                <span className="game-chip">{focusBooking.coach_required ? "С тренером" : "Тренер не нужен"}</span>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <div className="text-right text-xs text-[color:var(--ink-muted)]">
                <div className="text-lg font-black text-[color:var(--ink)]">{visitOrdinal(focusBooking.visits_before)}</div>
                {focusBooking.last_time ? `прошлый — ${formatDateRu(focusBooking.last_time.date)}` : (focusBooking.visits_before ?? 0) === 0 ? "первый визит" : null}
              </div>
              <button
                type="button"
                className="game-button-secondary min-w-12 px-3"
                onClick={() => setFocusBookingId("")}
                aria-label="Скрыть карточку клиента"
                title="Скрыть"
              >
                ✕
              </button>
            </div>
          </div>
          <ClientPrefsPanel session={session} booking={focusBooking} inventory={inventory} onUpdated={replaceBooking} />
        </section>
      ) : null}

      <div className="grid gap-5 xl:grid-cols-[1.1fr_0.9fr]">
        {!readOnly ? (
        <>
        <section className="game-panel space-y-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="text-xs font-black uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">Шаг 1</div>
              <h2 className="mt-1 text-xl font-black text-[color:var(--ink)]">Спортсмен</h2>
            </div>
            <span className="game-chip">Поиск и создание</span>
          </div>

          <div>
            <label htmlFor="clients-search" className="mb-2 block text-sm font-bold text-[color:var(--ink-muted)]">Поиск по имени или телефону</label>
            <input
              id="clients-search"
              value={clientsQuery}
              onChange={(e) => setClientsQuery(e.target.value)}
              placeholder="Например: Ирина или +7..."
              className="game-input"
            />
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            {clients.length === 0 ? (
              <div className="game-card text-sm text-[color:var(--ink-muted)]">Клиенты не найдены.</div>
            ) : (
              clients.map((client) => {
                const active = selectedClientId === client.client_id;
                return (
                  <button
                    key={client.client_id}
                    type="button"
                    onClick={() => setSelectedClientId(client.client_id)}
                    className={`game-card text-left transition ${active ? "border-[color:var(--accent-border)] shadow-[0_10px_24px_rgba(14,110,98,0.12)]" : "hover:-translate-y-0.5 hover:border-[color:var(--accent-border)]"}`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="text-lg font-black text-[color:var(--ink)]">{client.full_name}</div>
                        <div className="mt-1 text-sm text-[color:var(--ink-muted)]">{formatPhoneRu(client.phone)}</div>
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
                <div className="text-xs uppercase text-[color:var(--ink-muted)]">Визитов всего</div>
                <div className="text-lg font-black text-[color:var(--ink)]">{clientStats.visits_count}</div>
              </div>
              <div>
                <div className="text-xs uppercase text-[color:var(--ink-muted)]">Завершённые</div>
                <div className="text-lg font-black text-[color:var(--ink)]">{formatCount(clientStats.sessions_count)}</div>
              </div>
              <div>
                <div className="text-xs uppercase text-[color:var(--ink-muted)]">Выручка</div>
                <div className="text-lg font-black text-[color:var(--ink)]">{formatRub(clientStats.revenue_estimate)}</div>
              </div>
              <div>
                <div className="text-xs uppercase text-[color:var(--ink-muted)]">Последний визит</div>
                <div className="text-lg font-black text-[color:var(--ink)]">{clientStats.last_visit_date ? formatDateRu(clientStats.last_visit_date) : "—"}</div>
              </div>
            </div>
          ) : null}

          <form className="game-card space-y-3" onSubmit={onCreateClient}>
            <div className="text-xs font-black uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">Быстрое создание</div>
            <div className="grid gap-3 md:grid-cols-2">
              <div>
                <label htmlFor="new-client-name" className="mb-2 block text-sm font-bold text-[color:var(--ink-muted)]">Имя и фамилия</label>
                <input
                  id="new-client-name"
                  value={clientName}
                  onChange={(e) => setClientName(e.target.value)}
                  placeholder="Например: Ирина Смирнова"
                  required
                  className="game-input"
                />
              </div>
              <div>
                <label htmlFor="new-client-phone" className="mb-2 block text-sm font-bold text-[color:var(--ink-muted)]">Телефон</label>
                <input
                  id="new-client-phone"
                  value={clientPhone}
                  onChange={(e) => setClientPhone(e.target.value)}
                  placeholder="+7 999 000-00-00"
                  type="tel"
                  inputMode="tel"
                  required
                  className="game-input"
                />
              </div>
            </div>
            <button className="game-button w-full md:w-auto" disabled={loading} type="submit">
              Создать спортсмена
            </button>
          </form>
        </section>

        <section className="game-panel space-y-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="text-xs font-black uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">Шаги 2–4</div>
              <h2 className="mt-1 text-xl font-black text-[color:var(--ink)]">Слот и экипировка</h2>
            </div>
            <span className="game-chip">Сценарий смены</span>
          </div>

          <div className="grid grid-cols-2 gap-2 2xl:grid-cols-4">
            <div
              className="flex min-h-[5.5rem] flex-col justify-between rounded-[22px] border px-3 py-3"
              style={{
                background: selectedClient ? "var(--accent-soft)" : "var(--panel-solid)",
                borderColor: selectedClient ? "var(--accent-border)" : "var(--border)",
              }}
            >
              <div className="text-[11px] font-bold uppercase tracking-[0.04em] leading-snug text-[color:var(--ink-muted)] [overflow-wrap:anywhere]">1. Спортсмен</div>
              <div className="mt-2 text-sm font-black leading-snug break-words text-[color:var(--ink)]">{selectedClient ? selectedClient.full_name : "Не выбран"}</div>
            </div>
            <div
              className="flex min-h-[5.5rem] flex-col justify-between rounded-[22px] border px-3 py-3"
              style={{
                background: selectedSlot ? "var(--accent-soft)" : "var(--panel-solid)",
                borderColor: selectedSlot ? "var(--accent-border)" : "var(--border)",
              }}
            >
              <div className="text-[11px] font-bold uppercase tracking-[0.04em] leading-snug text-[color:var(--ink-muted)] [overflow-wrap:anywhere]">2. Слот</div>
              <div className="mt-2 text-sm font-black leading-snug break-words text-[color:var(--ink)]">{selectedSlot || "Не выбран"}</div>
            </div>
            <div
              className="flex min-h-[5.5rem] flex-col justify-between rounded-[22px] border px-3 py-3"
              style={{ background: "var(--panel-solid)", borderColor: "var(--accent-border)" }}
            >
              <div className="text-[11px] font-bold uppercase tracking-[0.04em] leading-snug text-[color:var(--ink-muted)] [overflow-wrap:anywhere]">3. Дисциплина</div>
              <div className="mt-2 text-sm font-black leading-snug break-words text-[color:var(--ink)]">{getRideTypeLabel(rideType)}</div>
            </div>
            <div
              className="flex min-h-[5.5rem] flex-col justify-between rounded-[22px] border px-3 py-3"
              style={{
                background: selectedClientId && boatId && time ? "var(--accent-soft)" : "var(--panel-solid)",
                borderColor: selectedClientId && boatId && time ? "var(--accent-border)" : "var(--border)",
              }}
            >
              <div className="text-[11px] font-bold uppercase tracking-[0.04em] leading-snug text-[color:var(--ink-muted)] [overflow-wrap:anywhere]">4. Готовность</div>
              <div className="mt-2 text-sm font-black leading-snug break-words text-[color:var(--ink)]">{selectedClientId && boatId && time ? "Можно оформлять" : "Заполните шаги"}</div>
            </div>
          </div>

          <form className="space-y-4" onSubmit={onCreateBooking}>
            <div className="game-card space-y-3">
              <label htmlFor="booking-date" className="block text-xs font-black uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">Дата и слот</label>
              <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
                <input
                  id="booking-date"
                  ref={dateInputRef}
                  type="date"
                  value={date}
                  onChange={(e) => setDate(e.target.value)}
                  required
                  className="game-input"
                />
                <button type="button" onClick={openDatePicker} className="game-button-secondary whitespace-nowrap px-4">
                  Выбрать дату
                </button>
              </div>
              <div className="flex flex-wrap gap-2 text-xs">
                <button type="button" onClick={() => setDate(today)} className="game-chip min-h-11 px-3" disabled={date === today} aria-pressed={date === today} title={date === today ? "Уже выбрана сегодняшняя дата" : undefined}>Сегодня</button>
                <button type="button" onClick={() => setDate(currentSeason.start)} className="game-chip min-h-11 px-3" disabled={date === currentSeason.start} aria-pressed={date === currentSeason.start} title={date === currentSeason.start ? "Уже выбрано начало сезона" : undefined}>Начало сезона</button>
                <button type="button" onClick={() => setDate(currentSeason.end)} className="game-chip min-h-11 px-3" disabled={date === currentSeason.end} aria-pressed={date === currentSeason.end} title={date === currentSeason.end ? "Уже выбран конец сезона" : undefined}>Конец сезона</button>
              </div>
              {seasonHint ? <p className="text-xs font-semibold text-[color:var(--warn)]">{seasonHint}</p> : null}
              <select
                aria-label="Слот"
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
                <option value="">Выберите слот</option>
                {availableSlots.map((slot) => (
                  <option key={`${slot.boat_id}-${slot.time}`} value={`${slot.boat_id}|${slot.time}`}>
                    {slot.time} · {boatLabel(slot.boat_id)} · свободно: {slot.available}
                  </option>
                ))}
              </select>
              {availableSlots.length === 0 ? (
                <p className="text-xs text-[color:var(--ink-muted)]">
                  {seasonHint ? "Вне сезона слоты не открываются: брони на эту дату можно смотреть, но новую не оформить." : "На выбранную дату нет свободных слотов. Проверьте дату, расписание, катера и цены."}
                </p>
              ) : null}
            </div>

            <div className="game-card space-y-4 overflow-visible">
              <div className="text-xs font-black uppercase tracking-[0.08em] text-[color:var(--ink-muted)]">Режим катания</div>
              <div className="grid gap-2 sm:grid-cols-3">
                {RIDE_TYPES.map((item) => (
                  <button
                    key={item.value}
                    type="button"
                    onClick={() => setRideType(item.value)}
                    className={`game-tab h-12 w-full px-2 ${rideType === item.value ? "game-tab-active" : ""}`}
                    aria-pressed={rideType === item.value}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
              <div className="grid items-stretch gap-3 sm:grid-cols-2">
                <div className="flex min-h-[7.5rem] flex-col justify-center">
                  <label htmlFor="sets-count" className="mb-2 block text-sm font-bold leading-snug text-[color:var(--ink-muted)]">Количество сетов</label>
                  <select id="sets-count" value={setsCount} onChange={(e) => setSetsCount(Number(e.target.value) || 1)} className="game-input">
                    {[1, 2, 3, 4].map((count) => (
                      <option key={count} value={count}>
                        {count} {count === 1 ? "сет" : count < 5 ? "сета" : "сетов"} · {count * 25} мин
                      </option>
                    ))}
                  </select>
                </div>
                <div
                  className="flex min-h-[7.5rem] flex-col justify-center rounded-2xl border px-3 py-3"
                  style={{ background: "var(--accent-soft)", borderColor: "var(--accent-border)" }}
                >
                  <div className="text-[11px] font-bold uppercase tracking-[0.08em] text-[color:var(--ink-muted)]">План по времени</div>
                  <div className="mt-1 text-base font-black leading-tight text-[color:var(--ink)]">{setsCount * 25} мин на воде</div>
                  <div className="mt-1 text-xs leading-snug text-[color:var(--ink-muted)]">По этому времени считается таймер смены.</div>
                </div>
              </div>
            </div>

            <div className="game-card space-y-3">
              <div className="text-xs font-black uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">Бонусы и экипировка</div>
              <div className="grid items-end gap-3 sm:grid-cols-2">
                <div>
                  <div className="mb-2 block text-sm font-bold leading-snug text-[color:var(--ink-muted)]">Тренер</div>
                  <label
                    className="flex min-h-12 cursor-pointer items-center gap-3 rounded-2xl border px-3"
                    style={{ background: "var(--panel-solid)", borderColor: "var(--border)" }}
                  >
                    <input type="checkbox" className="h-4 w-4 accent-[color:var(--accent)]" checked={coachRequired} onChange={(e) => setCoachRequired(e.target.checked)} />
                    <span className="text-sm font-black leading-snug text-[color:var(--ink)]">Нужен</span>
                  </label>
                </div>
                <div>
                  <label htmlFor="booking-discount" className="mb-2 block text-sm font-bold leading-snug text-[color:var(--ink-muted)]">Скидка, ₽</label>
                  <input
                    id="booking-discount"
                    type="number"
                    min={0}
                    value={discount}
                    onChange={(e) => setDiscount(Number(e.target.value) || 0)}
                    className="game-input"
                  />
                </div>
              </div>

              <div className="grid items-end gap-3 sm:grid-cols-3">
                <div>
                  <div className="mb-2 block text-sm font-bold leading-snug text-[color:var(--ink-muted)]">Гидрокостюм</div>
                  <label
                    className="flex min-h-12 cursor-pointer items-center gap-3 rounded-2xl border px-3"
                    style={{ background: "var(--panel-solid)", borderColor: "var(--border)" }}
                  >
                    <input
                      type="checkbox"
                      className="h-4 w-4 accent-[color:var(--accent)]"
                      checked={wetsuitRequired}
                      onChange={(e) => {
                        const checked = e.target.checked;
                        setWetsuitRequired(checked);
                        setWetsuitSize(DEFAULT_WETSUIT_SIZE);
                        setWetsuitGender(DEFAULT_WETSUIT_GENDER);
                      }}
                    />
                    <span className="text-sm font-black leading-snug text-[color:var(--ink)]">Нужен</span>
                  </label>
                </div>
                <div>
                  <label htmlFor="wetsuit-gender" className="mb-2 block text-sm font-bold leading-snug text-[color:var(--ink-muted)]">Пол</label>
                  <select
                    id="wetsuit-gender"
                    aria-describedby={!wetsuitRequired ? "wetsuit-disabled-hint" : undefined}
                    title={!wetsuitRequired ? "Сначала отметьте «Гидрокостюм — нужен»" : undefined}
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
                  <label htmlFor="wetsuit-size" className="mb-2 block text-sm font-bold leading-snug text-[color:var(--ink-muted)]">Размер</label>
                  <select
                    id="wetsuit-size"
                    aria-describedby={!wetsuitRequired ? "wetsuit-disabled-hint" : undefined}
                    title={!wetsuitRequired ? "Сначала отметьте «Гидрокостюм — нужен»" : undefined}
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
              {!wetsuitRequired ? (
                <p id="wetsuit-disabled-hint" className="text-xs text-[color:var(--ink-muted)]">
                  Пол и размер выбираются, когда отмечено «Гидрокостюм — нужен».
                </p>
              ) : null}
            </div>

            <div className="game-card space-y-3">
              <label htmlFor="booking-notes" className="block text-xs font-black uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">Комментарий к заезду</label>
              <input
                id="booking-notes"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Например: гидрокостюм нужен к старту, клиент новичок"
                className="game-input"
              />
            </div>

            <button
              type="submit"
              disabled={loading || !selectedClientId || !boatId || !time}
              aria-describedby={!loading && (!selectedClientId || !boatId || !time) ? "create-booking-hint" : undefined}
              className="game-button w-full"
            >
              {loading ? "Оформляем бронь…" : "Оформить бронь"}
            </button>
            {!loading && (!selectedClientId || !boatId || !time) ? (
              <p id="create-booking-hint" className="text-xs text-[color:var(--ink-muted)]">
                {!selectedClientId ? "Чтобы оформить бронь, выберите спортсмена (шаг 1)" : "Чтобы оформить бронь, выберите дату и свободный слот"}
                {!selectedClientId && (!boatId || !time) ? ", дату и свободный слот." : "."}
              </p>
            ) : null}
          </form>
        </section>
        </>
        ) : null}
      </div>

      <section className="game-panel space-y-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="text-xs font-black uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">Список на день</div>
            <h2 className="mt-1 text-xl font-black text-[color:var(--ink)]">Брони на {formatDateRu(date)}</h2>
          </div>
          <div className="game-chip">{loading ? "Обновляем…" : `Показано ${filteredBookings.length} из ${bookings.length}`}</div>
        </div>

        <div className="grid gap-2 sm:grid-cols-4">
          <div className="game-stat p-3">
            <div className="text-xs uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">Всего</div>
            <div className="mt-1 text-lg font-black text-[color:var(--ink)]">{bookingStats.total}</div>
          </div>
          <div className="game-stat p-3">
            <div className="text-xs uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">Ожидают</div>
            <div className="mt-1 text-lg font-black text-[color:var(--ink)]">{bookingStats.waiting}</div>
          </div>
          <div className="game-stat p-3">
            <div className="text-xs uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">На воде</div>
            <div className="mt-1 text-lg font-black text-[color:var(--ink)]">{bookingStats.onWater}</div>
          </div>
          <div className="game-stat p-3">
            <div className="text-xs uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">Завершены</div>
            <div className="mt-1 text-lg font-black text-[color:var(--ink)]">{bookingStats.done}</div>
          </div>
        </div>

        <div className="grid gap-3 xl:grid-cols-[1.4fr_1fr_auto]">
          <div className="game-card space-y-3">
            <div className="text-xs font-black uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">Фильтр статуса</div>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              <button type="button" onClick={() => setStatusFilter("all")} aria-pressed={statusFilter === "all"} className={`game-tab ${statusFilter === "all" ? "game-tab-active" : ""}`}>Все</button>
              {(["confirmed", "arrived", "ready", "in_progress", "done", "late", "cancelled", "no_show"] as BookingStatus[]).map((status) => (
                <button key={status} type="button" onClick={() => setStatusFilter(status)} aria-pressed={statusFilter === status} className={`game-tab ${statusFilter === status ? "game-tab-active" : ""}`}>
                  {getStatusLabel(status)}
                </button>
              ))}
            </div>
          </div>

          <div className="game-card space-y-3">
            <div className="text-xs font-black uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">Фильтр дисциплины</div>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              <button type="button" onClick={() => setRideFilter("all")} aria-pressed={rideFilter === "all"} className={`game-tab ${rideFilter === "all" ? "game-tab-active" : ""}`}>Все дисциплины</button>
              {RIDE_TYPES.map((item) => (
                <button key={item.value} type="button" onClick={() => setRideFilter(item.value)} aria-pressed={rideFilter === item.value} className={`game-tab ${rideFilter === item.value ? "game-tab-active" : ""}`}>
                  {item.label}
                </button>
              ))}
            </div>
          </div>

          <div className="game-card space-y-3">
            <div className="text-xs font-black uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">Вид</div>
            <label className="game-card flex min-h-11 cursor-pointer items-center gap-3 p-3">
              <input type="checkbox" className="h-5 w-5 accent-[color:var(--accent)]" checked={wetsuitOnly} onChange={(e) => setWetsuitOnly(e.target.checked)} />
              <span className="text-sm font-black text-[color:var(--ink)]">Только с гидрокостюмом</span>
            </label>
            <label className="game-card flex min-h-11 cursor-pointer items-center gap-3 p-3">
              <input type="checkbox" className="h-5 w-5 accent-[color:var(--accent)]" checked={compactList} onChange={(e) => setCompactList(e.target.checked)} />
              <span className="text-sm font-black text-[color:var(--ink)]">Компактный список</span>
            </label>
          </div>
        </div>

        <div className={`grid gap-4 ${compactList ? "" : "xl:grid-cols-2"}`}>
          {filteredBookings.map((booking) => (
            <article
              key={booking.booking_id}
              id={`booking-${booking.booking_id}`}
              className={`game-card scroll-mt-24 ${compactList ? "space-y-3" : "space-y-4"} ${highlightId === booking.booking_id ? "ring-2 ring-[color:var(--accent)] ring-offset-2 ring-offset-[color:var(--paper)]" : ""}`}
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="text-xs font-black uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">{booking.time} · {boatLabel(booking.boat_id)}</div>
                  <div className="mt-1 text-xl font-black text-[color:var(--ink)]">{booking.client_name || booking.client_id}</div>
                  <div className="text-sm text-[color:var(--ink-muted)]">{formatPhoneRu(booking.client_phone)}</div>
                </div>
                <span className={`${getStatusBadge(booking.status)} max-w-[11rem] sm:max-w-[14rem]`}>{getStatusLabel(booking.status)}</span>
              </div>

              <div className="flex flex-wrap gap-2">
                <div className="game-stat min-w-fit flex-[1_1_7rem] p-3">
                  <div className="text-[11px] font-bold uppercase leading-tight tracking-[0.04em] whitespace-nowrap text-[color:var(--ink-muted)]">Дисциплина</div>
                  <div className="mt-1 text-sm font-black text-[color:var(--ink)]">{getRideTypeLabel(booking.ride_type)}</div>
                </div>
                <div className="game-stat min-w-fit flex-[1_1_7rem] p-3">
                  <div className="text-[11px] font-bold uppercase leading-tight tracking-[0.04em] whitespace-nowrap text-[color:var(--ink-muted)]">Гидрокостюм</div>
                  <div className="mt-1 text-sm font-black text-[color:var(--ink)]">{booking.wetsuit_required ? "Да" : "Нет"}</div>
                </div>
                <div className="game-stat min-w-fit flex-[1_1_7rem] p-3">
                  <div className="text-[11px] font-bold uppercase leading-tight tracking-[0.04em] whitespace-nowrap text-[color:var(--ink-muted)]">Пол / размер</div>
                  <div className="mt-1 text-sm font-black text-[color:var(--ink)]">{getWetsuitGenderLabel(booking.client_name || "", booking.wetsuit_gender)}{booking.wetsuit_size ? ` ${booking.wetsuit_size}` : ""}</div>
                </div>
                <div className="game-stat min-w-fit flex-[1_1_7rem] p-3">
                  <div className="text-[11px] font-bold uppercase leading-tight tracking-[0.04em] whitespace-nowrap text-[color:var(--ink-muted)]">Цена</div>
                  <div className="mt-1 text-sm font-black text-[color:var(--ink)]">{formatRub(booking.total_price)}</div>
                </div>
                <div className="game-stat min-w-fit flex-[1_1_7rem] p-3">
                  <div className="text-[11px] font-bold uppercase leading-tight tracking-[0.04em] whitespace-nowrap text-[color:var(--ink-muted)]">Сеты / время</div>
                  <div className="mt-1 text-sm font-black text-[color:var(--ink)]">
                    {booking.sets_count === null ? "—" : `${formatCount(booking.sets_count)} · ${formatMinutes(booking.planned_duration_minutes)}`}
                  </div>
                  <div className="mt-1 text-xs text-[color:var(--ink-muted)]">
                    {isPositive(booking.actual_duration_seconds) ? `Факт ${formatMinutes(Math.max(Math.round((booking.actual_duration_seconds ?? 0) / 60), 1))}` : "Факт появится после завершения"}
                  </div>
                </div>
              </div>

              <div className="game-card space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <div className="text-xs font-black uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">Оплата</div>
                    <div className="mt-1 text-sm font-black text-[color:var(--ink)]">{PAYMENT_STATUS_LABELS[booking.payment_status]}</div>
                    <div className="mt-1 text-xs text-[color:var(--ink-muted)]">
                      Оплату фиксирует оператор вручную в журнале; приём карт в приложении не выполняется.
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-xs text-[color:var(--ink-muted)]">Получено / остаток</div>
                    <div className="text-sm font-black text-[color:var(--ink)]">
                      {formatRubMinor(booking.net_paid_minor)} / {formatRubMinor(booking.balance_due_minor)}
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
                      <select value={paymentMethod} onChange={(event) => setPaymentMethod(event.target.value as PaymentMethod)} className="game-input" aria-label="Способ оплаты">
                        {PAYMENT_METHODS.map((method) => <option key={method.value} value={method.value}>{method.label}</option>)}
                      </select>
                      <button type="button" disabled={loading} onClick={() => void onPayment(booking)} className="game-button px-4">Зафиксировать</button>
                    </div>
                  ) : (
                    <button
                      type="button"
                      onClick={() => {
                        setPaymentBookingId(booking.booking_id);
                        setPaymentAmount(String((toFiniteNumber(booking.balance_due_minor) ?? 0) / 100));
                      }}
                      className="game-button-secondary w-full"
                    >
                      Зафиксировать оплату
                    </button>
                  )
                ) : null}
              </div>

              {booking.notes ? <div className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--accent-soft)] px-3 py-3 text-sm text-[color:var(--ink-muted)]">{booking.notes}</div> : null}

              {supportsClientPrefs(booking) && booking.booking_id !== focusBooking?.booking_id ? (
                readOnly ? (
                  booking.coach_user_id === session.staff_user_id && !["cancelled", "no_show"].includes(booking.status) ? (
                    <ClientPrefsPanel session={session} booking={booking} inventory={inventory} onUpdated={replaceBooking} boardOnly dense />
                  ) : null
                ) : PREFS_PANEL_STATUSES.has(booking.status) || (booking.status === "done" && hasIssuedEquipment(booking)) ? (
                  <ClientPrefsPanel session={session} booking={booking} inventory={inventory} onUpdated={replaceBooking} dense />
                ) : booking.last_time && ["confirmed", "late"].includes(booking.status) ? (
                  <div className="rounded-2xl border border-[color:var(--accent-border)] bg-[color:var(--shift-wash)] px-3 py-2 text-sm text-[color:var(--ink)]">
                    <span className="font-black text-[color:var(--accent)]">В прошлый раз: </span>
                    {[
                      booking.last_time.wetsuit ? `гидрокостюм ${wetsuitTitle(booking.last_time.wetsuit)}` : "",
                      booking.last_time.board ? `доска ${boardTitle(booking.last_time.board)}` : "",
                      booking.last_time.drink ? drinkLabel(booking.last_time.drink).toLowerCase() : "",
                    ].filter(Boolean).join(", ")}
                  </div>
                ) : null
              ) : null}

              {!readOnly ? (
                <div className="space-y-3">
                  <PilotRideControls
                    session={session}
                    booking={booking}
                    onUpdated={mergeUpdatedBooking}
                    allowTimerControls={session.role === "admin"}
                    allowCancel
                    compact={compactList}
                  />
                  {booking.status === "arrived" && booking.warmup_state !== "pending" ? (
                    <button
                      type="button"
                      onClick={() => void onStatusChange(booking.booking_id, "ready")}
                      className="game-button w-full"
                    >
                      Передать пилоту
                    </button>
                  ) : null}
                </div>
              ) : null}
            </article>
          ))}

          {filteredBookings.length === 0 ? (
            <div className="game-card text-sm text-[color:var(--ink-muted)]">По текущим фильтрам броней нет.</div>
          ) : null}
        </div>
      </section>
    </section>
  );
}

function availableSlotKey(boatId: string, time: string): string {
  if (!boatId || !time) return "";
  return `${time} · ${boatLabel(boatId)}`;
}


