import { useEffect, useState } from "react";

import { getLeads, getMarketingFunnel } from "../api/client";
import { LeadItem, MarketingFunnel, StaffSession } from "../types";

type MarketingPageProps = {
  session: StaffSession;
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

  useEffect(() => {
    void (async () => {
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
      }
    })();
  }, [session.token, range.from, range.to]);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-slate-50">Маркетинг</h1>
        <p className="text-sm text-slate-400">Воронка лидов и read-only аналитика</p>
      </header>

      {error ? <p className="rounded-lg border border-red-500/40 bg-red-950/40 p-3 text-sm text-red-100">{error}</p> : null}

      {funnel ? (
        <section className="grid gap-4 md:grid-cols-4">
          <MetricCard label="Лиды" value={funnel.leads_count} />
          <MetricCard label="Контакт" value={funnel.contacted_count} />
          <MetricCard label="Записались" value={funnel.booked_count} />
          <MetricCard label="Конверсия %" value={funnel.conversion_to_booked_pct} />
        </section>
      ) : null}

      <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
        <h2 className="mb-3 text-lg font-medium text-slate-100">Лиды</h2>
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-sm text-slate-200">
            <thead className="text-slate-400">
              <tr>
                <th className="px-2 py-2">Имя</th>
                <th className="px-2 py-2">Телефон</th>
                <th className="px-2 py-2">Источник</th>
                <th className="px-2 py-2">Статус</th>
              </tr>
            </thead>
            <tbody>
              {leads.map((lead) => (
                <tr key={lead.lead_id} className="border-t border-slate-800">
                  <td className="px-2 py-2">{lead.full_name}</td>
                  <td className="px-2 py-2">{lead.phone}</td>
                  <td className="px-2 py-2">{lead.source}</td>
                  <td className="px-2 py-2">{lead.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: number }): JSX.Element {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-4">
      <p className="text-xs uppercase tracking-wide text-slate-400">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-cyan-100">{value}</p>
    </div>
  );
}
