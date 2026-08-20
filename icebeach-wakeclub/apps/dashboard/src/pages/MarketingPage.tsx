import { useEffect, useState } from "react";

import { getLeads, getMarketingFunnel } from "../api/client";
import { LeadItem, MarketingFunnel, StaffSession } from "../types";

type MarketingPageProps = {
  session: StaffSession;
};

const STATUS_LABELS: Record<LeadItem["status"], string> = {
  new: "Новый",
  contacted: "Контакт",
  booked: "Записался",
  lost: "Потерян",
};

function getSeasonRange(): { from: string; to: string } {
  const year = new Date().getFullYear();
  return { from: `${year}-06-01`, to: `${year}-10-01` };
}

export function MarketingPage({ session }: MarketingPageProps): JSX.Element {
  const [range] = useState(getSeasonRange);
  const [funnel, setFunnel] = useState<MarketingFunnel | null>(null);
  const [leads, setLeads] = useState<LeadItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void (async () => {
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
    })();
  }, [session.token, range.from, range.to]);

  return (
    <section className="space-y-5 sm:space-y-6">
      <header className="game-panel">
        <h1 className="game-heading">Маркетинг</h1>
        <p className="game-subheading mt-2">
          Воронка лидов сезона {range.from} — {range.to}. Телефоны видны staff; внешние выгрузки не делаем.
        </p>
      </header>

      {error ? <p className="game-panel border-red-400/30 bg-red-950/40 text-sm text-red-100">{error}</p> : null}
      {loading ? <p className="game-card text-sm text-slate-300">Загружаем воронку...</p> : null}

      {funnel ? (
        <section className="grid gap-4 md:grid-cols-4">
          <MetricCard label="Лиды" value={funnel.leads_count} />
          <MetricCard label="Контакт+" value={funnel.contacted_count} />
          <MetricCard label="Записались" value={funnel.booked_count} />
          <MetricCard label="Конверсия %" value={funnel.conversion_to_booked_pct} />
        </section>
      ) : null}

      <section className="game-panel space-y-3">
        <h2 className="text-lg font-black text-white">Лиды</h2>
        {leads.length === 0 && !loading ? (
          <p className="game-card text-sm text-slate-300">Лидов за выбранный контур пока нет.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm text-slate-200">
              <caption className="sr-only">Список лидов клуба</caption>
              <thead className="text-cyan-100/70">
                <tr>
                  <th className="px-2 py-2">Имя</th>
                  <th className="px-2 py-2">Телефон</th>
                  <th className="px-2 py-2">Источник</th>
                  <th className="px-2 py-2">Статус</th>
                </tr>
              </thead>
              <tbody>
                {leads.map((lead) => (
                  <tr key={lead.lead_id} className="border-t border-cyan-200/10">
                    <td className="px-2 py-2">{lead.full_name}</td>
                    <td className="px-2 py-2">{lead.phone}</td>
                    <td className="px-2 py-2">{lead.source}</td>
                    <td className="px-2 py-2">{STATUS_LABELS[lead.status] || lead.status}</td>
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

function MetricCard({ label, value }: { label: string; value: number }): JSX.Element {
  return (
    <article className="game-stat">
      <p className="text-xs font-black uppercase tracking-[0.12em] text-cyan-100/60">{label}</p>
      <p className="mt-2 text-2xl font-black text-white">{value}</p>
    </article>
  );
}
