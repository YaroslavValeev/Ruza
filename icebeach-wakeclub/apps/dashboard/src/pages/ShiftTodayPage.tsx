import { useEffect, useMemo, useState } from "react";

import { getShiftToday } from "../api/client";
import { ConsentBadges } from "../components/ConsentBadges";
import { BookingItem, CheckinItem, ShiftToday, StaffSession } from "../types";
import { STATUS_LABELS } from "../mobile/pilot-utils";

type ShiftTodayPageProps = {
  session: StaffSession;
};

function getToday(): string {
  return new Date().toISOString().slice(0, 10);
}

export function ShiftTodayPage({ session }: ShiftTodayPageProps): JSX.Element {
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
      <section className="game-panel flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="text-xs font-black uppercase tracking-[0.12em] text-cyan-100/70">Смена сегодня</div>
          <p className="mt-1 text-sm text-slate-400">Брони, check-in и проблемные статусы в одной ленте.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <input type="date" value={date} onChange={(event) => setDate(event.target.value)} className="game-input min-h-[44px]" />
          <button type="button" className="game-button-secondary min-h-[44px] px-4" disabled={loading} onClick={() => void load()}>
            {loading ? "..." : "Обновить"}
          </button>
        </div>
      </section>

      {data ? (
        <section className="grid gap-3 sm:grid-cols-4 lg:grid-cols-8">
          <Stat label="Всего" value={String(data.summary.total_bookings)} />
          <Stat label="Check-in" value={String(data.summary.checkins_count)} />
          <Stat label="Готовы" value={String(data.summary.ready)} />
          <Stat label="На воде" value={String(data.summary.in_progress)} />
          <Stat label="Done" value={String(data.summary.done)} />
          <Stat label="Late" value={String(data.summary.late)} />
          <Stat label="No-show" value={String(data.summary.no_show)} />
          <Stat label="Отмена" value={String(data.summary.cancelled)} />
        </section>
      ) : null}

      {error ? <div className="game-panel border-red-400/30 bg-red-950/30 text-red-50">{error}</div> : null}

      <section className="space-y-3">
        {(data?.bookings ?? []).map((booking) => (
          <ShiftBookingCard key={booking.booking_id} booking={booking} checkin={checkinsByBooking.get(booking.booking_id)} />
        ))}
        {data && data.bookings.length === 0 ? (
          <div className="game-panel text-sm text-slate-400">На выбранную дату броней нет.</div>
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
          <div className="text-lg font-black text-white">{booking.client_name || booking.client_id}</div>
          <div className="mt-1 text-sm text-slate-400">
            {booking.time} • {booking.boat_id} • {booking.ride_type}
          </div>
          <div className="mt-1 text-sm text-cyan-100/70">{booking.client_phone}</div>
        </div>
        <span className={tone}>{STATUS_LABELS[booking.status] || booking.status}</span>
      </div>
      <ConsentBadges consentFace={checkin?.consent_face} consentVoice={checkin?.consent_voice} compact />
      {checkin ? (
        <div className="text-xs text-slate-400">
          Check-in: {checkin.status} ({checkin.method}) в {new Date(checkin.ts).toLocaleTimeString("ru-RU")}
        </div>
      ) : (
        <div className="text-xs text-amber-200/80">Check-in ещё не выполнен</div>
      )}
    </article>
  );
}

function Stat({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="game-stat p-3">
      <div className="text-[10px] uppercase tracking-[0.12em] text-cyan-100/60">{label}</div>
      <div className="mt-1 text-xl font-black text-white">{value}</div>
    </div>
  );
}
