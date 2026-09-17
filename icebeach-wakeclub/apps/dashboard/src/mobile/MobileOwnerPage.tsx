import { FormEvent, useEffect, useState } from "react";

import { createCheckin, getClients, getKpiSummary } from "../api/client";
import { ConsentBadges } from "../components/ConsentBadges";
import { VoiceCheckinWizard } from "../components/VoiceCheckinWizard";
import { ClientItem, KpiSummary, StaffSession } from "../types";
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
      setError("Введите телефон клиента");
      return;
    }
    setError(null);
    setMessage(null);
    setLoading(true);
    try {
      await createCheckin({ method: "phone", phone: phone.trim(), date, status }, session.token);
      setMessage(status === "arrived" ? "Приезд отмечен" : "Клиент готов к старту");
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
        <div className="text-xs font-black uppercase tracking-[0.12em] text-cyan-100/70">Дата смены</div>
        <input type="date" value={date} onChange={(event) => setDate(event.target.value)} className="game-input min-h-[48px]" />
      </section>

      <section className="grid gap-3 sm:grid-cols-3">
        <StatCard label="Заезды" value={kpi ? String(kpi.sessions_count) : "—"} />
        <StatCard label="Загрузка" value={kpi ? `${kpi.utilization_pct.toFixed(0)}%` : "—"} />
        <StatCard label="Чистое поступление" value={kpi ? `${Math.round(kpi.net_revenue_minor / 100).toLocaleString("ru-RU")} ₽` : "—"} />
      </section>

      <div className="flex gap-2">
        <button type="button" className="game-button-secondary min-h-[48px] flex-1" disabled={loading} onClick={() => void loadKpi()}>
          {loading ? "Обновляем..." : "Обновить KPI"}
        </button>
      </div>

      <section className="game-panel space-y-4">
        <div>
          <div className="text-xs font-black uppercase tracking-[0.12em] text-cyan-100/70">Быстрый check-in</div>
          <p className="mt-1 text-sm text-slate-400">По телефону клиента, без поиска в списке.</p>
        </div>
        <form className="space-y-3" onSubmit={(event) => void onCheckin(event)}>
          <input
            value={phone}
            onChange={(event) => setPhone(event.target.value)}
            className="game-input min-h-[52px] text-lg"
            placeholder="+79990000001"
            inputMode="tel"
            autoComplete="tel"
          />
          {checkinClient ? (
            <div className="flex flex-wrap items-center gap-2 text-sm text-slate-300">
              <span>{checkinClient.full_name}</span>
              <ConsentBadges consentFace={checkinClient.consent_face} consentVoice={checkinClient.consent_voice} compact />
            </div>
          ) : null}
          <div className="grid gap-2 sm:grid-cols-2">
            <button type="submit" className="game-button min-h-[56px] text-base" disabled={loading}>
              Приехал
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

      {message ? <div className="game-panel border-emerald-400/30 bg-emerald-950/30 text-emerald-50">{message}</div> : null}
      {error ? <div className="game-panel border-red-400/30 bg-red-950/30 text-red-50">{error}</div> : null}

      <section className="game-panel space-y-2 text-sm text-slate-300">
        <div className="font-bold text-white">Owner: {session.full_name}</div>
        <p>Дата: {date}. Полный dashboard: `/shift`, `/bookings`, `/kpi`.</p>
      </section>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="game-stat p-4">
      <div className="text-xs uppercase tracking-[0.12em] text-cyan-100/60">{label}</div>
      <div className="mt-2 text-2xl font-black text-white">{value}</div>
    </div>
  );
}
