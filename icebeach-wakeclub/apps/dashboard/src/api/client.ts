import {
  AvailabilityItem,
  BookingCreateRequest,
  BookingCreateResponse,
  BookingItem,
  BookingStatus,
  ClientCreateRequest,
  ClientItem,
  CheckinCreateRequest,
  CheckinItem,
  ClientStats,
  HealthStatus,
  KpiPeriod,
  KpiSummary,
  LeadItem,
  LoginCodeResponse,
  MarketingFunnel,
  BoatItem,
  PilotQueueItem,
  PreflightSummary,
  PublicBookingRequest,
  PublicBookingRequestResponse,
  RideTimerAction,
  ShiftToday,
  ShiftLive,
  SmokeSummary,
  StaffSession,
  BookingPrepUpdateRequest,
  BoardInput,
  BoardRef,
  EquipmentUpdateRequest,
  EquipmentUpdateResponse,
  WetsuitInput,
  WetsuitRef,
} from "../types";
import { emitAuthFailure } from "../auth/auth-events";
import { toFiniteNumber } from "../lib/format";

/** Длительность одного сета, как в API (ride_runtime.SET_DURATION_MINUTES). */
const SET_MINUTES = 25;
const NOT_STARTED_STATUSES = new Set(["confirmed", "arrived", "ready", "late"]);

type RideRuntimeFields = {
  status: string;
  sets_count: number | null;
  planned_duration_minutes: number | null;
  warmup_state: import("../types").WarmupState;
  timer_state: import("../types").RideTimerState;
  elapsed_seconds: number | null;
  remaining_seconds: number | null;
  actual_duration_seconds: number | null;
};

/**
 * Приводит поля заезда к числам. Старая версия API (например, демо из Ruza-demo)
 * не присылает sets_count / planned_duration_minutes / remaining_seconds — тогда
 * выводим то, что можно вычислить, а остальное оставляем null (на экране «—»).
 */
export function normalizeRide<T extends RideRuntimeFields>(raw: T): T {
  const item = raw as T & Record<string, unknown>;
  const sets = toFiniteNumber(item.sets_count);
  const planned = toFiniteNumber(item.planned_duration_minutes) ?? (sets !== null ? sets * SET_MINUTES : null);
  const elapsed = toFiniteNumber(item.elapsed_seconds);
  let remaining = toFiniteNumber(item.remaining_seconds);
  if (remaining === null && planned !== null) {
    if (elapsed !== null) remaining = Math.max(planned * 60 - elapsed, 0);
    else if (NOT_STARTED_STATUSES.has(String(item.status))) remaining = planned * 60;
  }
  return {
    ...raw,
    sets_count: sets,
    planned_duration_minutes: planned,
    elapsed_seconds: elapsed,
    remaining_seconds: remaining,
    actual_duration_seconds: toFiniteNumber(item.actual_duration_seconds),
    warmup_state: item.warmup_state || "pending",
    timer_state: item.timer_state || "idle",
  };
}

const RAW_API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

function isLoopbackHost(hostname: string): boolean {
  return hostname === "127.0.0.1" || hostname === "localhost" || hostname === "::1";
}

function resolveApiBaseUrl(): string {
  const raw = RAW_API_BASE_URL.trim();

  if (raw.startsWith("/")) {
    return `${window.location.origin}${raw}`.replace(/\/$/, "");
  }

  try {
    const configured = new URL(RAW_API_BASE_URL, window.location.origin);
    const browserHost = window.location.hostname;

    if (browserHost && !isLoopbackHost(browserHost) && isLoopbackHost(configured.hostname)) {
      configured.hostname = browserHost;
    }

    return configured.toString().replace(/\/$/, "");
  } catch {
    return RAW_API_BASE_URL.replace(/\/$/, "");
  }
}

const API_BASE_URL = resolveApiBaseUrl();

export function getApiBaseUrl(): string {
  return API_BASE_URL;
}

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export function isApiError(error: unknown, status?: number): error is ApiError {
  if (!(error instanceof ApiError)) {
    return false;
  }

  return status === undefined ? true : error.status === status;
}

/** Известные ответы сервера → русский текст для сотрудника. */
const API_DETAIL_RU: Array<[RegExp, string]> = [
  [/^Arrival can only be confirmed before the ride starts/i, "Прибытие можно отметить только до начала заезда."],
  [/^Booking missing in pilot queue/i, "Бронь не найдена в очереди пилота."],
  [/^Booking not found for check-in/i, "Не найдена бронь для отметки о прибытии."],
  [/^Booking not found/i, "Бронь не найдена."],
  [/^Client not found by phone/i, "Клиент с таким телефоном не найден."],
  [/^Client not found/i, "Клиент не найден."],
  [/^No active booking found for client/i, "У клиента нет активной брони на эту дату."],
  [/^Code must be 6 digits/i, "Код должен состоять из 6 цифр."],
  [/^Invalid or expired code/i, "Код неверный или устарел. Запросите новый."],
  [/^User not found or inactive/i, "Сотрудник не найден или отключён."],
  [/^Several staff records match this phone/i, "На этот телефон оформлено несколько сотрудников. Укажите код сотрудника."],
  [/^staff_user_id or phone is required/i, "Укажите телефон или код сотрудника."],
  [/^Too many login attempts/i, "Слишком много попыток входа. Подождите несколько минут."],
  [/^Too many login code requests/i, "Слишком много запросов кода. Подождите несколько минут."],
  [/^Too many requests for this phone/i, "Слишком много запросов для этого телефона. Подождите."],
  [/^Face check-in requires consent_face/i, "Нет согласия клиента на распознавание лица."],
  [/^Forbidden for this role/i, "Для вашей роли это действие недоступно."],
  [/^Pilot can only (update|view) assigned boat/i, "Пилоту доступен только закреплённый за ним катер."],
  [/^Pilot can only start and finish rides/i, "Пилот может только запускать и завершать заезды."],
  [/^Operator can only hand off bookings to pilot/i, "Оператор может только передать заезд пилоту."],
  [/^Ride start and finish are only available through the timer/i, "Старт и финиш заезда — только через таймер."],
  [/^Another ride is already active on this boat/i, "На этом катере уже идёт другой заезд — сначала завершите его."],
  [/^Ride can only start from ready/i, "Запустить сет можно только после статуса «Готово к старту»."],
  [/^Ride can only pause while running on water/i, "Пауза доступна только во время заезда."],
  [/^Ride can only stop after it has started/i, "Завершить можно только начатый заезд."],
  [/^Extra set can only be added while on water/i, "Дополнительный сет можно добавить только во время заезда."],
  [/^Next slot is not free for an extra set/i, "Следующий слот занят — дополнительный сет добавить нельзя."],
  [/^No earlier start notice can be sent/i, "Следующему клиенту нельзя предложить ранний старт."],
  [/^Late can only be marked before arrival/i, "Опоздание можно отметить только до прибытия."],
  [/^Warmup can only be set after arrival/i, "Разминку можно отметить только после прибытия."],
  [/^Invalid status transition/i, "Такой переход статуса недоступен."],
  [/^No capacity for selected slot duration/i, "На выбранное время не хватает свободных слотов."],
  [/^No pricing configured for selected date/i, "На выбранную дату не настроены цены."],
  [/^Booking ID already used/i, "Такая бронь уже создана — обновите список."],
  [/^Idempotency key already used/i, "Эта операция уже выполнена."],
  [/^Payment not found/i, "Оплата не найдена."],
  [/^Refund exceeds charge amount/i, "Сумма возврата больше суммы оплаты."],
  [/^Only succeeded charges can be refunded/i, "Вернуть можно только проведённую оплату."],
  [/^Reconciliation discrepancy requires explicit override/i, "Расхождение в сверке — нужно явное подтверждение."],
  [/^Lead not found/i, "Лид не найден."],
  [/^Smoke check requires at least one client/i, "Для проверки сценария нужен хотя бы один клиент."],
  [/^Smoke check requires one free slot/i, "Для проверки сценария нужен свободный слот."],
  [/^boat_id is required for this user/i, "Выберите катер."],
  [/^phone is required for phone check-in/i, "Введите телефон клиента."],
  [/^client_id or booking_id required/i, "Выберите клиента или бронь."],
  [/^date_from and date_to must be provided together/i, "Укажите обе даты периода."],
  [/^(Missing session token|Invalid token|Invalid token payload|Token expired)/i, "Сессия истекла. Войдите снова."],
  [/^Legacy login is disabled/i, "Этот способ входа отключён. Войдите по одноразовому коду."],
];

const API_STATUS_RU: Record<number, string> = {
  400: "Запрос не выполнен: проверьте введённые данные.",
  401: "Сессия истекла. Войдите снова.",
  403: "Для вашей роли это действие недоступно.",
  404: "Данные не найдены.",
  409: "Данные изменились. Обновите экран и повторите.",
  422: "Проверьте заполнение полей.",
  429: "Слишком много запросов. Подождите немного.",
};

function toFriendlyApiMessage(status: number, text: string): string {
  let detail = "";
  try {
    const parsed = JSON.parse(text) as { detail?: unknown; message?: unknown };
    if (typeof parsed.detail === "string") detail = parsed.detail;
    else if (typeof parsed.message === "string") detail = parsed.message;
  } catch {
    detail = text.length < 200 ? text : "";
  }
  if (detail && /[А-Яа-яЁё]/.test(detail)) {
    return detail;
  }
  const known = API_DETAIL_RU.find(([pattern]) => pattern.test(detail.trim()));
  if (known) {
    return known[1];
  }
  if (status >= 500) {
    return "Ошибка на сервере. Повторите попытку позже.";
  }
  return API_STATUS_RU[status] ?? `Не удалось выполнить действие (код ${status}).`;
}

type FetchApiOptions = RequestInit & {
  token?: string;
  notifyAuthFailure?: boolean;
  timeoutMs?: number;
};

function toFriendlyNetworkError(error: unknown, timeoutMs: number): Error {
  if (error instanceof DOMException && error.name === "AbortError") {
    return new ApiError(0, `Сервер не ответил за ${Math.round(timeoutMs / 1000)} сек. Повторите попытку.`);
  }

  if (error instanceof TypeError || (error instanceof Error && /Failed to fetch/i.test(error.message))) {
    return new ApiError(0, "Нет связи с сервером. Проверьте подключение и повторите попытку.");
  }

  if (error instanceof Error) {
    return error;
  }

  return new ApiError(0, "Сетевой сбой. Повторите попытку.");
}

function withTimeout(timeoutMs: number): { signal: AbortSignal; cancel: () => void } {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);
  return {
    signal: controller.signal,
    cancel: () => window.clearTimeout(timeoutId),
  };
}

async function fetchApi<T>(path: string, options: FetchApiOptions = {}): Promise<T> {
  const { token, notifyAuthFailure = true, headers, timeoutMs = 15000, ...requestInit } = options;
  const mergedHeaders = new Headers(headers);
  if (!mergedHeaders.has("Content-Type") && requestInit.body) {
    mergedHeaders.set("Content-Type", "application/json");
  }

  if (token) {
    mergedHeaders.set("Authorization", `Bearer ${token}`);
  }

  const method = (requestInit.method || "GET").toUpperCase();
  const maxAttempts = method === "GET" ? 3 : 1;

  let lastErr: unknown = null;
  let response: Response | null = null;

  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    const t = withTimeout(timeoutMs);
    try {
      response = await fetch(`${API_BASE_URL}${path}`, {
        ...requestInit,
        credentials: "include",
        headers: mergedHeaders,
        signal: t.signal,
      });
      break;
    } catch (err) {
      lastErr = err;
      if (attempt === maxAttempts) {
        throw toFriendlyNetworkError(err, timeoutMs);
      }
      await new Promise((r) => setTimeout(r, 250 * attempt));
    } finally {
      t.cancel();
    }
  }

  if (!response) {
    throw toFriendlyNetworkError(lastErr, timeoutMs);
  }

  if (!response.ok) {
    const text = await response.text();
    if (notifyAuthFailure && (response.status === 401 || response.status === 403)) {
      emitAuthFailure(response.status as 401 | 403);
    }
    throw new ApiError(response.status, toFriendlyApiMessage(response.status, text));
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export function requestLoginCode(staff_user_id: string, phone: string): Promise<LoginCodeResponse> {
  return fetchApi<LoginCodeResponse>("/auth/request-code", {
    method: "POST",
    notifyAuthFailure: false,
    body: JSON.stringify({ staff_user_id: staff_user_id || undefined, phone }),
    headers: { "Content-Type": "application/json" },
  });
}

export function verifyLoginCode(staff_user_id: string, code: string, phone?: string): Promise<StaffSession> {
  return fetchApi<StaffSession>("/auth/verify-code", {
    method: "POST",
    notifyAuthFailure: false,
    body: JSON.stringify({ staff_user_id: staff_user_id || undefined, phone: phone || undefined, code }),
    headers: { "Content-Type": "application/json" },
  });
}

export function getCurrentSession(): Promise<StaffSession> {
  return fetchApi<StaffSession>("/auth/me");
}

export async function logout(): Promise<void> {
  try {
    await fetch(`${API_BASE_URL}/auth/logout`, {
      method: "POST",
      credentials: "include",
    });
  } catch {
    return;
  }
}

export function getHealthStatus(): Promise<HealthStatus> {
  return fetchApi<HealthStatus>("/health", { notifyAuthFailure: false, timeoutMs: 5000 });
}

export function getKpiSummary(token: string | undefined, period: KpiPeriod, dateFrom?: string, dateTo?: string): Promise<KpiSummary> {
  const search = new URLSearchParams();
  search.set("period", period);
  if (dateFrom) {
    search.set("date_from", dateFrom);
  }
  if (dateTo) {
    search.set("date_to", dateTo);
  }
  return fetchApi<KpiSummary>(`/kpi/summary?${search.toString()}`, { token });
}

export function getPreflightSummary(token: string | undefined, date: string): Promise<PreflightSummary> {
  const search = new URLSearchParams();
  search.set("date", date);
  return fetchApi<PreflightSummary>(`/preflight/summary?${search.toString()}`, { token });
}

export function runSmokeCheck(token: string | undefined, date: string): Promise<SmokeSummary> {
  const search = new URLSearchParams();
  search.set("date", date);
  return fetchApi<SmokeSummary>(`/smoke/run?${search.toString()}`, {
    method: "POST",
    token,
  });
}

export function getClients(query: string, token?: string): Promise<ClientItem[]> {
  return fetchApi<ClientItem[]>(`/clients?query=${encodeURIComponent(query)}`, { token });
}

export function createClient(payload: ClientCreateRequest, token?: string): Promise<ClientItem> {
  return fetchApi<ClientItem>("/clients", {
    method: "POST",
    token,
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json" },
  });
}

export function getBookings(date: string, token?: string): Promise<BookingItem[]> {
  return fetchApi<BookingItem[]>(`/bookings?date=${encodeURIComponent(date)}`, { token }).then((rows) => rows.map(normalizeRide));
}

export function getShiftToday(date: string, token?: string): Promise<ShiftToday> {
  return fetchApi<ShiftToday>(`/shift/today?date=${encodeURIComponent(date)}`, { token }).then((data) => ({
    ...data,
    bookings: (data.bookings ?? []).map(normalizeRide),
  }));
}

export function getShiftLive(token?: string, date?: string): Promise<ShiftLive> {
  const search = new URLSearchParams();
  if (date) {
    search.set("date", date);
  }
  const suffix = search.toString();
  return fetchApi<ShiftLive>(`/shift/live${suffix ? `?${suffix}` : ""}`, { token }).then((data) => ({
    ...data,
    focus_booking: data.focus_booking ? normalizeRide(data.focus_booking) : data.focus_booking,
  }));
}

export function getClientStats(clientId: string, token?: string): Promise<ClientStats> {
  return fetchApi<ClientStats>(`/clients/${encodeURIComponent(clientId)}/stats`, { token });
}

export function getPublicAvailability(date: string): Promise<AvailabilityItem[]> {
  return fetchApi<AvailabilityItem[]>(`/public/availability?date=${encodeURIComponent(date)}`, { notifyAuthFailure: false });
}

export function submitPublicBookingRequest(payload: PublicBookingRequest): Promise<PublicBookingRequestResponse> {
  return fetchApi<PublicBookingRequestResponse>("/public/booking-request", {
    method: "POST",
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json" },
    notifyAuthFailure: false,
  });
}

export function getPilotToday(
  token?: string,
  boatId?: string,
  date?: string,
  dateFrom?: string,
  dateTo?: string,
): Promise<PilotQueueItem[]> {
  const search = new URLSearchParams();
  if (boatId) {
    search.set("boat_id", boatId);
  }
  if (date) {
    search.set("date", date);
  }
  if (dateFrom) {
    search.set("date_from", dateFrom);
  }
  if (dateTo) {
    search.set("date_to", dateTo);
  }
  const suffix = search.toString();
  return fetchApi<PilotQueueItem[]>(`/pilot/today${suffix ? `?${suffix}` : ""}`, { token }).then((rows) => rows.map(normalizeRide));
}

export function getAvailability(token: string | undefined, date: string): Promise<AvailabilityItem[]> {
  return fetchApi<AvailabilityItem[]>(`/availability?date=${encodeURIComponent(date)}`, { token });
}

export function createBooking(token: string | undefined, payload: BookingCreateRequest): Promise<BookingCreateResponse> {
  return fetchApi<BookingCreateResponse>("/bookings", {
    method: "POST",
    token,
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json" },
  });
}

export function createPayment(
  token: string | undefined,
  payload: { booking_id: string; amount_minor: number; method: import("../types").PaymentMethod; idempotency_key: string },
): Promise<import("../types").PaymentMutationResponse> {
  return fetchApi<import("../types").PaymentMutationResponse>("/payments", {
    method: "POST",
    token,
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json" },
  });
}

export function updateBookingStatus(bookingId: string, status: BookingStatus, token?: string): Promise<BookingItem> {
  return fetchApi<BookingItem>(`/bookings/${encodeURIComponent(bookingId)}/status`, {
    method: "PATCH",
    token,
    body: JSON.stringify({ status }),
    headers: { "Content-Type": "application/json" },
  }).then(normalizeRide);
}

export function updateBookingPrep(bookingId: string, payload: BookingPrepUpdateRequest, token?: string): Promise<BookingItem> {
  return fetchApi<BookingItem>(`/bookings/${encodeURIComponent(bookingId)}/prep`, {
    method: "PATCH",
    token,
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json" },
  }).then(normalizeRide);
}

export function runBookingTimerAction(bookingId: string, action: RideTimerAction, token?: string): Promise<BookingItem> {
  return fetchApi<BookingItem>(`/bookings/${encodeURIComponent(bookingId)}/timer-action`, {
    method: "POST",
    token,
    body: JSON.stringify({ action }),
    headers: { "Content-Type": "application/json" },
  }).then(normalizeRide);
}

export function createCheckin(payload: CheckinCreateRequest, token?: string): Promise<CheckinItem> {
  return fetchApi<CheckinItem>("/checkins", {
    method: "POST",
    token,
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json" },
  });
}

export function runAnalyticsSnapshot(token: string | undefined, date: string): Promise<{ written: boolean }> {
  return fetchApi<{ written: boolean }>(`/analytics/snapshot?date=${encodeURIComponent(date)}`, {
    method: "POST",
    token,
  });
}

export function getBoats(token?: string): Promise<BoatItem[]> {
  return fetchApi<BoatItem[]>("/boats", { token });
}

export function getLeads(token?: string): Promise<LeadItem[]> {
  return fetchApi<LeadItem[]>("/leads", { token });
}

export function updateLeadStatus(leadId: string, status: LeadItem["status"], token?: string): Promise<LeadItem> {
  return fetchApi<LeadItem>(`/leads/${encodeURIComponent(leadId)}/status`, {
    method: "PATCH",
    token,
    body: JSON.stringify({ status }),
    headers: { "Content-Type": "application/json" },
  });
}

export function createLead(
  payload: { full_name: string; phone: string; source?: string; notes?: string },
  token?: string,
): Promise<LeadItem> {
  return fetchApi<LeadItem>("/leads", {
    method: "POST",
    token,
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json" },
  });
}

export function getMarketingFunnel(token: string | undefined, dateFrom: string, dateTo: string): Promise<MarketingFunnel> {
  const search = new URLSearchParams({ date_from: dateFrom, date_to: dateTo });
  return fetchApi<MarketingFunnel>(`/marketing/funnel?${search.toString()}`, { token });
}

/* ---------- «Как в прошлый раз»: инвентарь и выдача снаряжения ---------- */

export function getInventoryBoards(token?: string, includeInactive = false): Promise<BoardRef[]> {
  return fetchApi<BoardRef[]>(`/inventory/boards${includeInactive ? "?include_inactive=true" : ""}`, { token });
}

export function getInventoryWetsuits(token?: string, includeInactive = false): Promise<WetsuitRef[]> {
  return fetchApi<WetsuitRef[]>(`/inventory/wetsuits${includeInactive ? "?include_inactive=true" : ""}`, { token });
}

export function createBoard(payload: BoardInput, token?: string): Promise<BoardRef> {
  return fetchApi<BoardRef>("/inventory/boards", {
    method: "POST",
    token,
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json" },
  });
}

export function updateBoard(boardId: string, payload: Partial<BoardInput>, token?: string): Promise<BoardRef> {
  return fetchApi<BoardRef>(`/inventory/boards/${encodeURIComponent(boardId)}`, {
    method: "PATCH",
    token,
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json" },
  });
}

export function createWetsuit(payload: WetsuitInput, token?: string): Promise<WetsuitRef> {
  return fetchApi<WetsuitRef>("/inventory/wetsuits", {
    method: "POST",
    token,
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json" },
  });
}

export function updateWetsuit(wetsuitId: string, payload: Partial<WetsuitInput>, token?: string): Promise<WetsuitRef> {
  return fetchApi<WetsuitRef>(`/inventory/wetsuits/${encodeURIComponent(wetsuitId)}`, {
    method: "PATCH",
    token,
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json" },
  });
}

export function updateBookingEquipment(bookingId: string, payload: EquipmentUpdateRequest, token?: string): Promise<EquipmentUpdateResponse> {
  return fetchApi<EquipmentUpdateResponse>(`/bookings/${encodeURIComponent(bookingId)}/equipment`, {
    method: "PATCH",
    token,
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json" },
  }).then((data) => ({ ...data, booking: normalizeRide(data.booking), warnings: data.warnings ?? [] }));
}

export function repeatLastEquipment(bookingId: string, token?: string): Promise<EquipmentUpdateResponse> {
  return fetchApi<EquipmentUpdateResponse>(`/bookings/${encodeURIComponent(bookingId)}/equipment/repeat-last`, {
    method: "POST",
    token,
  }).then((data) => ({ ...data, booking: normalizeRide(data.booking), warnings: data.warnings ?? [] }));
}

export function resetClientPrefs(clientId: string, token?: string): Promise<{ client_id: string; prefs_reset_at: string }> {
  return fetchApi<{ client_id: string; prefs_reset_at: string }>(`/clients/${encodeURIComponent(clientId)}/prefs/reset`, {
    method: "POST",
    token,
  });
}
