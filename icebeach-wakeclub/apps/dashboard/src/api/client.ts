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
  HealthStatus,
  KpiPeriod,
  KpiSummary,
  LeadItem,
  LoginCodeResponse,
  MarketingFunnel,
  PilotQueueItem,
  PreflightSummary,
  SmokeSummary,
  StaffSession,
} from "../types";
import { emitAuthFailure } from "../auth/auth-events";

const RAW_API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

function isLoopbackHost(hostname: string): boolean {
  return hostname === "127.0.0.1" || hostname === "localhost" || hostname === "::1";
}

function resolveApiBaseUrl(): string {
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

type FetchApiOptions = RequestInit & {
  token?: string;
  notifyAuthFailure?: boolean;
  timeoutMs?: number;
};

function toFriendlyNetworkError(error: unknown, timeoutMs: number): Error {
  if (error instanceof DOMException && error.name === "AbortError") {
    return new ApiError(
      0,
      `API не ответило за ${Math.round(timeoutMs / 1000)} сек. Проверь status-local.ps1 и ${API_BASE_URL}/health.`,
    );
  }

  if (error instanceof TypeError || (error instanceof Error && /Failed to fetch/i.test(error.message))) {
    return new ApiError(
      0,
      `API недоступно. Проверь start-local.ps1, status-local.ps1 и адрес ${API_BASE_URL}.`,
    );
  }

  if (error instanceof Error) {
    return error;
  }

  return new ApiError(0, "Сетевой сбой при обращении к API.");
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
    throw new ApiError(
      response.status,
      text ? `API ${response.status}: ${text}` : `API ${response.status}`,
    );
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
    body: JSON.stringify({ staff_user_id, phone }),
    headers: { "Content-Type": "application/json" },
  });
}

export function verifyLoginCode(staff_user_id: string, code: string): Promise<StaffSession> {
  return fetchApi<StaffSession>("/auth/verify-code", {
    method: "POST",
    notifyAuthFailure: false,
    body: JSON.stringify({ staff_user_id, code }),
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
  return fetchApi<BookingItem[]>(`/bookings?date=${encodeURIComponent(date)}`, { token });
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
  return fetchApi<PilotQueueItem[]>(`/pilot/today${suffix ? `?${suffix}` : ""}`, { token });
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

export function updateBookingStatus(bookingId: string, status: BookingStatus, token?: string): Promise<BookingItem> {
  return fetchApi<BookingItem>(`/bookings/${encodeURIComponent(bookingId)}/status`, {
    method: "PATCH",
    token,
    body: JSON.stringify({ status }),
    headers: { "Content-Type": "application/json" },
  });
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

export function getLeads(token?: string): Promise<LeadItem[]> {
  return fetchApi<LeadItem[]>("/leads", { token });
}

export function getMarketingFunnel(token: string | undefined, dateFrom: string, dateTo: string): Promise<MarketingFunnel> {
  const search = new URLSearchParams({ date_from: dateFrom, date_to: dateTo });
  return fetchApi<MarketingFunnel>(`/marketing/funnel?${search.toString()}`, { token });
}
