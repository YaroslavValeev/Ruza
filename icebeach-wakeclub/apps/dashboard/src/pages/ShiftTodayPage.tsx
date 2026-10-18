import { useEffect, useMemo, useState } from "react";

import { getShiftToday } from "../api/client";
import { ConsentBadges } from "../components/ConsentBadges";
import { BookingItem, CheckinItem, ShiftToday, StaffSession } from "../types";
import { formatDateRu, formatPhoneRu, formatTimeRu, localTodayIso } from "../lib/dates";
import { formatCount } from "../lib/format";
import { boatLabel, rideTypeLabel, statusLabel, useBoatNames } from "../lib/labels";

const CHECKIN_METHOD_LABELS: Record<string, string> = {
  phone: "по телефону",
  face: "по лицу",
  voice: "голосом",
  manual: "вручную",
  system: "автоматически",
};

type ShiftTodayPageProps = {
  session: StaffSession;
};

function getToday(): string {
  return localTodayIso();
}

export function ShiftTodayPage({ session }: ShiftTodayPageProps): JSX.Element {
  useBoatNames(session);
  const [date, setDate] = useState(getToday);
  const [data, setData] = useState<ShiftToday | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const payload = await getShiftToday(date, session.token);
      setData(payload);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [date, session.token]);

  const checkinsByBooking = useMemo(() => {
    const map = new Map<string, CheckinItem>();
    for (const item of data?.checkins ?? []) {
      map.set(item.booking_id, item);
    }
    return map;
  }, [data]);

  return (
    <div className="space-y-5">
      <section className="game-panel flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="game-heading">Смена на {formatDateRu(date)}</h1>
          <p className="game-subheading mt-1">Брони, отметки о прибытии и проблемные статусы в одной ленте.</p>
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <div>
            <label htmlFor="shift-date" className="mb-1 block text-xs font-bold text-[color:var(--ink-muted)]">Дата смены</label>
            <input id="shift-date" type="date" value={date} onChange={(event) => setDate(event.target.value)} className="game-input min-h-[44px]" />
          </div>
          <button type="button" className="game-button-secondary min-h-12 whitespace-nowrap px-4" disabled={loading} onClick={() => void load()}>
            {loading ? "Обновляем…" : "Обновить"}
          </button>
        </div>
      </section>

      {data ? (
        <section className="grid gap-3 sm:grid-cols-4 lg:grid-cols-8">
          <Stat label="Всего" value={formatCount(data.summary.total_bookings)} />
          <Stat label="Отметились" value={formatCount(data.summary.checkins_count)} />
          <Stat label="Готовы" value={formatCount(data.summary.ready)} />
          <Stat label="На воде" value={formatCount(data.summary.in_progress)} />
          <Stat label="Завершены" value={formatCount(data.summary.done)} />
          <Stat label="Опаздывают" value={formatCount(data.summary.late)} />
          <Stat label="Не пришли" value={formatCount(data.summary.no_show)} />
          <Stat label="Отмена" value={formatCount(data.summary.cancelled)} />
        </section>
      ) : null}

      {error ? <div role="alert" className="game-panel border-red-600/25 bg-red-50 text-red-900">{error}</div> : null}

      <section className="space-y-3">
        {(data?.bookings ?? []).map((booking) => (
          <ShiftBookingCard key={booking.booking_id} booking={booking} checkin={checkinsByBooking.get(booking.booking_id)} />
        ))}
        {data && data.bookings.length === 0 ? (
          <div className="game-panel text-sm text-[color:var(--ink-muted)]">На выбранную дату броней нет.</div>
        ) : null}
      </section>
    </div>
  );
}

function ShiftBookingCard({ booking, checkin }: { booking: BookingItem; checkin?: CheckinItem }): JSX.Element {
  const tone =
    booking.status === "done"
      ? "game-badge-success"
      : booking.status === "late" || booking.status === "no_show" || booking.status === "cancelled"
        ? "game-badge-warn"
        : "game-badge-info";

  return (
    <article className="game-card space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-lg font-black text-[color:var(--ink)]">{booking.client_name || booking.client_id}</div>
          <div className="mt-1 text-sm text-[color:var(--ink-muted)]">
            {booking.time} · {boatLabel(booking.boat_id)} · {rideTypeLabel(booking.ride_type)}
          </div>
          <div className="mt-1 text-sm text-[color:var(--ink-muted)]">{formatPhoneRu(booking.client_phone)}</div>
        </div>
        <span className={tone}>{statusLabel(booking.status)}</span>
      </div>
      <ConsentBadges consentFace={checkin?.consent_face} consentVoice={checkin?.consent_voice} compact />
      {checkin ? (
        <div className="text-xs text-[color:var(--ink-muted)]">
          Отметка о прибытии: {statusLabel(checkin.status).toLowerCase()}, {CHECKIN_METHOD_LABELS[checkin.method] ?? "вручную"}, в {formatTimeRu(checkin.ts)}
        </div>
      ) : (
        <div className="text-xs font-semibold text-[color:var(--warn)]">Клиент ещё не отметился</div>
      )}
    </article>
  );
}

function Stat({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="game-stat p-3">
      <div className="text-[11px] uppercase tracking-[0.08em] text-[color:var(--ink-muted)]">{label}</div>
      <div className="mt-1 text-xl font-black text-[color:var(--ink)]">{value}</div>
    </div>
  );
}
