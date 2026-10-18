import { localTodayIso } from "../lib/dates";
import { FormEvent, useEffect, useState } from "react";

import { getPublicAvailability, submitPublicBookingRequest } from "../api/client";
import { rideTypeLabel } from "../lib/labels";
import { AvailabilityItem, RideType } from "../types";

const RIDE_TYPES: Array<{ value: RideType; label: string }> = [
  { value: "wakeboard", label: rideTypeLabel("wakeboard", { capitalize: true }) },
  { value: "surf", label: rideTypeLabel("surf", { capitalize: true }) },
  { value: "skim", label: rideTypeLabel("skim", { capitalize: true }) },
];

const FIELD_LABEL = "mb-2 block text-sm font-bold text-[color:var(--ink-muted)]";

function getDefaultDate(): string {
  return localTodayIso();
}

export function PublicBookPage(): JSX.Element {
  const [date, setDate] = useState(getDefaultDate);
  const [slots, setSlots] = useState<AvailabilityItem[]>([]);
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [time, setTime] = useState("");
  const [rideType, setRideType] = useState<RideType>("wakeboard");
  const [notes, setNotes] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const load = async () => {
      setError(null);
      try {
        const data = await getPublicAvailability(date);
        setSlots(data.filter((slot) => slot.available > 0 && slot.status === "active"));
        if (!time && data.length > 0) {
          const first = data.find((slot) => slot.available > 0);
          if (first) {
            setTime(first.time);
          }
        }
      } catch (err) {
        setError((err as Error).message);
      }
    };
    void load();
  }, [date]);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!time) {
      setError("Выберите время заезда");
      return;
    }
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const result = await submitPublicBookingRequest({
        full_name: fullName,
        phone,
        date,
        time,
        ride_type: rideType,
        notes,
      });
      setMessage(result.message);
      setFullName("");
      setPhone("");
      setNotes("");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-[100dvh] bg-[var(--paper)] px-4 py-8 text-[var(--ink)]">
      <div className="mx-auto max-w-lg">
        <div className="text-xs font-black uppercase tracking-[0.14em] text-[color:var(--accent)]">MyWave Club · Ice Beach</div>
        <h1 className="game-heading mt-2">Запись на заезд</h1>
        <p className="mt-2 text-sm text-[var(--ink-muted)]">Оставьте заявку — оператор перезвонит и подтвердит бронь.</p>

        <form className="game-panel mt-6 space-y-4" onSubmit={(event) => void onSubmit(event)}>
          <div>
            <label htmlFor="book-date" className={FIELD_LABEL}>Дата</label>
            <input id="book-date" type="date" value={date} onChange={(event) => setDate(event.target.value)} className="game-input w-full min-h-[48px]" />
          </div>
          <div>
            <label htmlFor="book-time" className={FIELD_LABEL}>Время</label>
            <select id="book-time" value={time} onChange={(event) => setTime(event.target.value)} className="game-input w-full min-h-[48px]">
              <option value="">Выберите время</option>
              {slots.map((slot) => (
                <option key={`${slot.time}-${slot.boat_id}`} value={slot.time}>
                  {slot.time} · свободно мест: {slot.available}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="book-ride" className={FIELD_LABEL}>Дисциплина</label>
            <select id="book-ride" value={rideType} onChange={(event) => setRideType(event.target.value as RideType)} className="game-input w-full min-h-[48px]">
              {RIDE_TYPES.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="book-name" className={FIELD_LABEL}>Имя</label>
            <input id="book-name" value={fullName} onChange={(event) => setFullName(event.target.value)} className="game-input w-full min-h-[48px]" autoComplete="name" required />
          </div>
          <div>
            <label htmlFor="book-phone" className={FIELD_LABEL}>Телефон</label>
            <input id="book-phone" type="tel" value={phone} onChange={(event) => setPhone(event.target.value)} className="game-input w-full min-h-[48px]" placeholder="+7 999 000-00-00" autoComplete="tel" required inputMode="tel" />
          </div>
          <div>
            <label htmlFor="book-notes" className={FIELD_LABEL}>Комментарий</label>
            <textarea id="book-notes" value={notes} onChange={(event) => setNotes(event.target.value)} className="game-input w-full min-h-[80px]" placeholder="Например: первый раз, нужен тренер" />
          </div>
          <button type="submit" className="game-button min-h-[52px] w-full" disabled={loading}>
            {loading ? "Отправляем…" : "Отправить заявку"}
          </button>
        </form>

        {message ? <div role="status" className="mt-4 rounded-xl border border-emerald-600/25 bg-emerald-50 p-4 text-emerald-900">{message}</div> : null}
        {error ? <div role="alert" className="mt-4 rounded-xl border border-red-600/25 bg-red-50 p-4 text-red-900">{error}</div> : null}
      </div>
    </div>
  );
}
