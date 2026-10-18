import { FormEvent, useCallback, useEffect, useState } from "react";

import { createLead, getLeads, getMarketingFunnel, updateLeadStatus } from "../api/client";
import { LeadItem, MarketingFunnel, StaffSession } from "../types";
import { formatDateRangeRu, formatPhoneRu } from "../lib/dates";
import { formatCount, formatPercent } from "../lib/format";
import { LEAD_SOURCE_OPTIONS, leadSourceLabel } from "../lib/labels";

type MarketingPageProps = {
  session: StaffSession;
};

const STATUS_LABELS: Record<LeadItem["status"], string> = {
  new: "Новый",
  contacted: "Связались",
  booked: "Записан",
  lost: "Потерян",
};

const LEAD_STATUSES: Array<LeadItem["status"]> = ["new", "contacted", "booked", "lost"];

function getSeasonRange(): { from: string; to: string } {
  const year = new Date().getFullYear();
  return { from: `${year}-06-01`, to: `${year}-10-01` };
}

export function MarketingPage({ session }: MarketingPageProps): JSX.Element {
  const canWrite = session.role === "admin" || session.role === "operator";
  const [range] = useState(getSeasonRange);
  const [funnel, setFunnel] = useState<MarketingFunnel | null>(null);
  const [leads, setLeads] = useState<LeadItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [source, setSource] = useState("offline");
  const [notes, setNotes] = useState("");

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const [funnelData, leadsData] = await Promise.all([
        getMarketingFunnel(session.token, range.from, range.to),
        getLeads(session.token),
      ]);
      setFunnel(funnelData);
      setLeads(leadsData);
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }, [session.token, range.from, range.to]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const onCreateLead = async (event: FormEvent) => {
    event.preventDefault();
    setSavingId("new");
    try {
      await createLead(
        {
          full_name: fullName.trim(),
          phone: phone.trim(),
          source: source.trim() || "offline",
          notes: notes.trim() || undefined,
        },
        session.token,
      );
      setFullName("");
      setPhone("");
      setSource("offline");
      setNotes("");
      await reload();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSavingId(null);
    }
  };

  const onStatusChange = async (leadId: string, status: LeadItem["status"]) => {
    setSavingId(leadId);
    try {
      const updated = await updateLeadStatus(leadId, status, session.token);
      setLeads((current) => current.map((item) => (item.lead_id === leadId ? updated : item)));
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSavingId(null);
    }
  };

  return (
    <section className="space-y-5 sm:space-y-6">
      <header className="game-panel">
        <h1 className="game-heading">Маркетинг</h1>
        <p className="game-subheading mt-2">
          Воронка лидов за сезон {formatDateRangeRu(range.from, range.to)}. Телефоны видны только сотрудникам клуба, выгрузок наружу нет.
        </p>
      </header>

      {error ? <p role="alert" className="game-panel border-red-600/25 bg-red-50 text-sm text-red-900">{error}</p> : null}
      {loading ? <p className="game-card text-sm text-[color:var(--ink-muted)]">Загружаем воронку…</p> : null}

      {funnel ? (
        <section className="space-y-2">
          <p className="text-xs font-bold uppercase tracking-[0.08em] text-[color:var(--ink-muted)]">
            Воронка за сезон {formatDateRangeRu(range.from, range.to)}
          </p>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <MetricCard label="Лиды" value={formatCount(funnel.leads_count)} />
            <MetricCard label="Связались" value={formatCount(funnel.contacted_count)} />
            <MetricCard label="Записались" value={formatCount(funnel.booked_count)} />
            <MetricCard label="Конверсия" value={formatPercent(funnel.conversion_to_booked_pct, 0)} />
          </div>
        </section>
      ) : null}

      {canWrite ? (
        <section className="game-panel space-y-3">
          <h2 className="text-lg font-black text-[color:var(--ink)]">Новый лид</h2>
          <p className="text-sm text-[color:var(--ink-muted)]">Оператор и администратор заносят обращение прямо здесь, без сторонних систем.</p>
          <form className="grid gap-3 md:grid-cols-2" onSubmit={(event) => void onCreateLead(event)}>
            <div>
              <label htmlFor="lead-name" className="mb-2 block text-sm font-bold text-[color:var(--ink-muted)]">Имя</label>
              <input
                id="lead-name"
                className="game-input"
                value={fullName}
                onChange={(event) => setFullName(event.target.value)}
                required
              />
            </div>
            <div>
              <label htmlFor="lead-phone" className="mb-2 block text-sm font-bold text-[color:var(--ink-muted)]">Телефон</label>
              <input
                id="lead-phone"
                className="game-input"
                placeholder="+7 999 000-00-00"
                type="tel"
                inputMode="tel"
                value={phone}
                onChange={(event) => setPhone(event.target.value)}
                required
              />
            </div>
            <div>
              <label htmlFor="lead-source" className="mb-2 block text-sm font-bold text-[color:var(--ink-muted)]">Источник</label>
              <select id="lead-source" className="game-input" value={source} onChange={(event) => setSource(event.target.value)}>
                {LEAD_SOURCE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="lead-notes" className="mb-2 block text-sm font-bold text-[color:var(--ink-muted)]">Комментарий</label>
              <input
                id="lead-notes"
                className="game-input"
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
              />
            </div>
            <button className="game-button md:col-span-2 md:justify-self-start md:px-8" disabled={savingId === "new"} type="submit">
              {savingId === "new" ? "Сохраняем…" : "Создать лид"}
            </button>
          </form>
        </section>
      ) : (
        <p className="game-card text-sm text-[color:var(--ink-muted)]">Роль «Маркетинг» видит воронку и лиды, но не меняет статусы.</p>
      )}

      <section className="game-panel space-y-3">
        <h2 className="text-lg font-black text-[color:var(--ink)]">Все лиды</h2>
        {leads.length === 0 && !loading ? (
          <p className="game-card text-sm text-[color:var(--ink-muted)]">Лидов пока нет.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm text-[color:var(--ink)]">
              <caption className="sr-only">Список лидов клуба</caption>
              <thead className="text-[color:var(--ink-muted)]">
                <tr>
                  <th className="px-2 py-2">Имя</th>
                  <th className="px-2 py-2">Телефон</th>
                  <th className="px-2 py-2">Источник</th>
                  <th className="px-2 py-2">Статус</th>
                  {canWrite ? <th className="px-2 py-2">Действия</th> : null}
                </tr>
              </thead>
              <tbody>
                {leads.map((lead) => (
                  <tr key={lead.lead_id} className="border-t border-[color:var(--border)]">
                    <td className="px-2 py-2">{lead.full_name}</td>
                    <td className="whitespace-nowrap px-2 py-2">{formatPhoneRu(lead.phone)}</td>
                    <td className="px-2 py-2">{leadSourceLabel(lead.source)}</td>
                    <td className="px-2 py-2">{STATUS_LABELS[lead.status] || lead.status}</td>
                    {canWrite ? (
                      <td className="px-2 py-2">
                        <div className="flex flex-wrap gap-2">
                          {LEAD_STATUSES.filter((status) => status !== lead.status).map((status) => (
                            <button
                              key={status}
                              type="button"
                              className="game-button-secondary px-3 text-xs"
                              disabled={savingId === lead.lead_id}
                              onClick={() => void onStatusChange(lead.lead_id, status)}
                            >
                              {STATUS_LABELS[status]}
                            </button>
                          ))}
                        </div>
                      </td>
                    ) : null}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </section>
  );
}

function MetricCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <article className="game-stat">
      <p className="text-xs font-black uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">{label}</p>
      <p className="mt-2 text-2xl font-black text-[color:var(--ink)]">{value}</p>
    </article>
  );
}
