import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { createCheckin, getBookings, getClients, getKpiSummary } from "../api/client";
import { ConsentBadges } from "../components/ConsentBadges";
import { ClientPrefsPanel } from "../components/equipment/ClientPrefsPanel";
import { VoiceCheckinWizard } from "../components/VoiceCheckinWizard";
import { formatDateRu } from "../lib/dates";
import { supportsClientPrefs, useInventory, visitOrdinal } from "../lib/equipment";
import { formatCount, formatPercent, formatRubMinor } from "../lib/format";
import { boatLabel, rideTypeLabel, roleLabel, useBoatNames } from "../lib/labels";
import { BookingItem, ClientItem, KpiSummary, StaffSession } from "../types";
import { getToday } from "./pilot-utils";

type MobileOwnerPageProps = {
  session: StaffSession;
};

export function MobileOwnerPage({ session }: MobileOwnerPageProps): JSX.Element {
  const [date, setDate] = useState(getToday);
  const [kpi, setKpi] = useState<KpiSummary | null>(null);
  const [phone, setPhone] = useState("");
  const [checkinClient, setCheckinClient] = useState<ClientItem | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  /** Бронь после отметки о прибытии — «Как в прошлый раз». */
  const [arrivedBooking, setArrivedBooking] = useState<BookingItem | null>(null);
  const inventory = useInventory(session.token);
  useBoatNames(session);

  const loadKpi = async () => {
    setError(null);
    setLoading(true);
    try {
      const data = await getKpiSummary(session.token, "day", date, date);
      setKpi(data);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadKpi();
  }, [date, session.token]);

  useEffect(() => {
    if (!phone.trim()) {
      setCheckinClient(null);
      return;
    }
    const timer = window.setTimeout(() => {
      getClients(phone.trim(), session.token)
        .then((rows) => setCheckinClient(rows[0] ?? null))
        .catch(() => setCheckinClient(null));
    }, 300);
    return () => window.clearTimeout(timer);
  }, [phone, session.token]);

  const submitCheckin = async (status: "arrived" | "ready") => {
    if (!phone.trim()) {
      setError("Введите телефон клиента.");
      return;
    }
    setError(null);
    setMessage(null);
    setLoading(true);
    try {
      const checkin = await createCheckin({ method: "phone", phone: phone.trim(), date, status }, session.token);
      setMessage(status === "arrived" ? "Прибытие отмечено." : "Клиент отмечен как готовый к старту.");
      setArrivedBooking(null);
      if (checkin.booking_id) {
        getBookings(date, session.token)
          .then((rows) => setArrivedBooking(rows.find((row) => row.booking_id === checkin.booking_id) ?? null))
          .catch(() => setArrivedBooking(null));
      }
      setPhone("");
      setCheckinClient(null);
      await loadKpi();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const onCheckin = async (event: FormEvent) => {
    event.preventDefault();
    await submitCheckin("arrived");
  };

  return (
    <div className="space-y-4">
      <section className="game-panel space-y-3">
        <label htmlFor="owner-date" className="block text-xs font-black uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">Дата смены</label>
        <input id="owner-date" type="date" value={date} onChange={(event) => setDate(event.target.value)} className="game-input min-h-[48px]" />
      </section>

      <section className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <StatCard label="Заезды" value={kpi ? formatCount(kpi.sessions_count) : "—"} />
        <StatCard label="Загрузка" value={kpi ? formatPercent(kpi.utilization_pct, 0) : "—"} />
        <StatCard wide label="Чистая выручка" value={kpi ? formatRubMinor(kpi.net_revenue_minor) : "—"} />
      </section>

      <div className="flex gap-2">
        <button type="button" className="game-button-secondary min-h-[48px] flex-1" disabled={loading} onClick={() => void loadKpi()}>
          {loading ? "Обновляем…" : "Обновить показатели"}
        </button>
      </div>

      <section className="game-panel space-y-4">
        <div>
          <h2 className="text-xs font-black uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">Отметка о прибытии</h2>
          <p className="mt-1 text-sm text-[color:var(--ink-muted)]">По телефону клиента, без поиска в списке.</p>
        </div>
        <form className="space-y-3" onSubmit={(event) => void onCheckin(event)}>
          <label htmlFor="owner-phone" className="block text-sm font-bold text-[color:var(--ink-muted)]">Телефон клиента</label>
          <input
            id="owner-phone"
            type="tel"
            value={phone}
            onChange={(event) => setPhone(event.target.value)}
            className="game-input min-h-[52px] text-lg"
            placeholder="+7 999 000-00-01"
            inputMode="tel"
            autoComplete="tel"
          />
          {checkinClient ? (
            <div className="flex flex-wrap items-center gap-2 text-sm text-[color:var(--ink-muted)]">
              <span>{checkinClient.full_name}</span>
              <ConsentBadges consentFace={checkinClient.consent_face} consentVoice={checkinClient.consent_voice} compact />
            </div>
          ) : null}
          <div className="grid gap-2 sm:grid-cols-[2fr_1fr]">
            <button type="submit" className="game-button min-h-[56px] text-base font-black" disabled={loading}>
              Отметить прибытие
            </button>
            <button
              type="button"
              className="game-button-secondary min-h-[56px] text-base"
              disabled={loading}
              onClick={() => void submitCheckin("ready")}
            >
              Готов к старту
            </button>
          </div>
        </form>
        <VoiceCheckinWizard
          date={date}
          token={session.token}
          onSuccess={(text) => setMessage(text)}
          onError={(text) => setError(text)}
        />
      </section>

      {message ? <div role="status" className="game-panel border-emerald-600/25 bg-emerald-50 text-emerald-900">{message}</div> : null}

      {arrivedBooking && supportsClientPrefs(arrivedBooking) ? (
        <section className="game-panel space-y-3" aria-labelledby="owner-arrived-name">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="text-xs font-black uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">
                {arrivedBooking.time} · {boatLabel(arrivedBooking.boat_id)} · {rideTypeLabel(arrivedBooking.ride_type)}
              </div>
              <h2 id="owner-arrived-name" className="mt-1 text-xl font-black text-[color:var(--ink)]">{arrivedBooking.client_name || arrivedBooking.client_id}</h2>
              <div className="text-sm text-[color:var(--ink-muted)]">{visitOrdinal(arrivedBooking.visits_before)}</div>
            </div>
            <button
              type="button"
              className="game-button-secondary min-h-11 min-w-11 px-3"
              onClick={() => setArrivedBooking(null)}
              aria-label="Скрыть карточку клиента"
            >
              ✕
            </button>
          </div>
          <ClientPrefsPanel
            session={session}
            booking={arrivedBooking}
            inventory={inventory}
            onUpdated={(updated) => setArrivedBooking((current) => (current ? { ...current, ...updated } : updated))}
          />
        </section>
      ) : null}
      {error ? <div role="alert" className="game-panel border-red-600/25 bg-red-50 text-red-900">{error}</div> : null}

      <section className="game-panel space-y-3 text-sm text-[color:var(--ink-muted)]">
        <div className="font-bold text-[color:var(--ink)]">
          {session.full_name} · {roleLabel(session.role)}
        </div>
        <p>Смена на {formatDateRu(date)}. Полная версия панели:</p>
        <div className="flex flex-wrap gap-2">
          <Link to="/shift" className="game-button-secondary min-h-11 px-4">Смена</Link>
          <Link to="/bookings" className="game-button-secondary min-h-11 px-4">Брони</Link>
          <Link to="/kpi" className="game-button-secondary min-h-11 px-4">Аналитика</Link>
        </div>
      </section>
    </div>
  );
}

function StatCard({ label, value, wide = false }: { label: string; value: string; wide?: boolean }): JSX.Element {
  return (
    <div className={`game-stat p-4 ${wide ? "col-span-2 sm:col-span-1" : ""}`}>
      <div className="text-xs uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">{label}</div>
      <div className="mt-2 text-2xl font-black text-[color:var(--ink)]">{value}</div>
    </div>
  );
}
