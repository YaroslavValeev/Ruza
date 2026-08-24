import { FormEvent, useEffect, useState } from "react";

import { getPublicAvailability, submitPublicBookingRequest } from "../api/client";
import { AvailabilityItem, RideType } from "../types";

const RIDE_TYPES: RideType[] = ["wakeboard", "surf", "skim"];

function getDefaultDate(): string {
  return new Date().toISOString().slice(0, 10);
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
      setError("Выберите слот");
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
    <div className="mx-auto min-h-screen max-w-lg bg-slate-950 px-4 py-8 text-slate-100">
      <h1 className="text-2xl font-black text-white">Запись в Ice Beach</h1>
      <p className="mt-2 text-sm text-slate-400">Оставьте заявку — оператор подтвердит бронь.</p>

      <form className="mt-6 space-y-4" onSubmit={(event) => void onSubmit(event)}>
        <input type="date" value={date} onChange={(event) => setDate(event.target.value)} className="game-input w-full min-h-[48px]" />
        <select value={time} onChange={(event) => setTime(event.target.value)} className="game-input w-full min-h-[48px]">
          <option value="">Выберите время</option>
          {slots.map((slot) => (
            <option key={`${slot.time}-${slot.boat_id}`} value={slot.time}>
              {slot.time} (свободно {slot.available})
            </option>
          ))}
        </select>
        <select value={rideType} onChange={(event) => setRideType(event.target.value as RideType)} className="game-input w-full min-h-[48px]">
          {RIDE_TYPES.map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </select>
        <input value={fullName} onChange={(event) => setFullName(event.target.value)} className="game-input w-full min-h-[48px]" placeholder="Имя" required />
        <input value={phone} onChange={(event) => setPhone(event.target.value)} className="game-input w-full min-h-[48px]" placeholder="Телефон" required inputMode="tel" />
        <textarea value={notes} onChange={(event) => setNotes(event.target.value)} className="game-input w-full min-h-[80px]" placeholder="Комментарий" />
        <button type="submit" className="game-button min-h-[52px] w-full" disabled={loading}>
          {loading ? "Отправляем..." : "Отправить заявку"}
        </button>
      </form>

      {message ? <div className="mt-4 rounded-xl border border-emerald-400/30 bg-emerald-950/30 p-4 text-emerald-50">{message}</div> : null}
      {error ? <div className="mt-4 rounded-xl border border-red-400/30 bg-red-950/30 p-4 text-red-50">{error}</div> : null}
    </div>
  );
}
