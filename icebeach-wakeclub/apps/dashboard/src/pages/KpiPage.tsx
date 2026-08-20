import { useEffect, useMemo, useState } from "react";

import { getKpiSummary, getPreflightSummary, runAnalyticsSnapshot, runSmokeCheck } from "../api/client";
import {
  KpiPeriod,
  KpiSummary,
  KpiTimelinePoint,
  PreflightLevel,
  PreflightSummary,
  RideType,
  SmokeLevel,
  SmokeSummary,
  StaffSession,
} from "../types";

type KpiPageProps = {
  session: StaffSession;
};

const PERIOD_OPTIONS: Array<{ value: KpiPeriod; label: string }> = [
  { value: "day", label: "День" },
  { value: "week", label: "Неделя" },
  { value: "month", label: "Месяц" },
  { value: "season", label: "Сезон" },
  { value: "custom", label: "Свои даты" },
];

const RIDE_TYPE_LABELS: Record<RideType, string> = {
  wakeboard: "Вейкборд",
  surf: "Серф",
  skim: "Ским",
};

const RIDE_TYPE_TONES: Record<RideType, string> = {
  wakeboard: "text-cyan-200",
  surf: "text-orange-200",
  skim: "text-fuchsia-200",
};

const CHECK_LEVEL_LABELS: Record<PreflightLevel, string> = {
  PASS: "ОК",
  WARN: "Внимание",
  BLOCKER: "Блокер",
};

const CHECK_LEVEL_STYLES: Record<PreflightLevel, string> = {
  PASS: "border-emerald-400/30 bg-emerald-950/30 text-emerald-50",
  WARN: "border-amber-400/30 bg-amber-950/30 text-amber-50",
  BLOCKER: "border-red-400/30 bg-red-950/30 text-red-50",
};

const SMOKE_LEVEL_LABELS: Record<SmokeLevel, string> = {
  PASS: "ОК",
  FAIL: "Ошибка",
};

const SMOKE_LEVEL_STYLES: Record<SmokeLevel, string> = {
  PASS: "border-emerald-400/30 bg-emerald-950/30 text-emerald-50",
  FAIL: "border-red-400/30 bg-red-950/30 text-red-50",
};

function getToday(): string {
  return new Date().toISOString().slice(0, 10);
}

function getSeasonBounds(dateText: string): { start: string; end: string } {
  const year = Number(dateText.slice(0, 4)) || new Date().getFullYear();
  return {
    start: `${year}-06-01`,
    end: `${year}-10-01`,
  };
}

export function KpiPage({ session }: KpiPageProps): JSX.Element {
  const [period, setPeriod] = useState<KpiPeriod>("day");
  const [anchorDate, setAnchorDate] = useState(getToday());
  const [customFrom, setCustomFrom] = useState(getSeasonBounds(getToday()).start);
  const [customTo, setCustomTo] = useState(getToday());
  const [kpi, setKpi] = useState<KpiSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [preflightDate, setPreflightDate] = useState(getToday());
  const [preflight, setPreflight] = useState<PreflightSummary | null>(null);
  const [preflightError, setPreflightError] = useState<string | null>(null);
  const [preflightLoading, setPreflightLoading] = useState(false);
  const [preflightExpanded, setPreflightExpanded] = useState(false);
  const [smokeDate, setSmokeDate] = useState(getToday());
  const [smoke, setSmoke] = useState<SmokeSummary | null>(null);
  const [smokeError, setSmokeError] = useState<string | null>(null);
  const [smokeLoading, setSmokeLoading] = useState(false);
  const [smokeExpanded, setSmokeExpanded] = useState(false);

  const requestDates = useMemo(() => {
    if (period === "custom") {
      return { dateFrom: customFrom, dateTo: customTo };
    }
    return { dateFrom: anchorDate, dateTo: undefined };
  }, [anchorDate, customFrom, customTo, period]);

  const handleCustomFromChange = (value: string) => {
    setCustomFrom(value);
    if (customTo < value) {
      setCustomTo(value);
    }
  };

  const handleCustomToChange = (value: string) => {
    setCustomTo(value < customFrom ? customFrom : value);
  };

  const anchorDateLabel = period === "week" ? "Опорная дата недели" : period === "month" ? "Опорная дата месяца" : period === "season" ? "Опорная дата сезона" : "Опорная дата";
  const seasonBounds = getSeasonBounds(anchorDate);
  const leadRide = useMemo(() => {
    if (!kpi?.ride_breakdown?.some((item) => item.sessions_count > 0)) return null;
    return [...kpi.ride_breakdown].sort((a, b) => b.revenue_estimate - a.revenue_estimate)[0] ?? null;
  }, [kpi]);
  const readinessLabel = preflight ? (preflight.blockers > 0 ? "Есть блокеры" : preflight.warnings > 0 ? "Есть предупреждения" : "Готово к смене") : "Проверка не запускалась";
  const readinessTone = preflight
    ? preflight.blockers > 0
      ? "rounded-full border border-red-400/40 bg-red-950/50 px-3 py-1 text-xs font-black uppercase tracking-[0.08em] text-red-100"
      : preflight.warnings > 0
        ? "game-badge-info"
        : "game-badge-success"
    : "game-chip text-cyan-100";

  const loadKpi = async () => {
    setError(null);
    setLoading(true);
    try {
      const data = await getKpiSummary(session.token, period, requestDates.dateFrom, requestDates.dateTo);
      setKpi(data);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const loadPreflight = async () => {
    if (session.role !== "admin") return;
    setPreflightError(null);
    setPreflightLoading(true);
    try {
      const data = await getPreflightSummary(session.token, preflightDate);
      setPreflight(data);
    } catch (err) {
      setPreflightError((err as Error).message);
    } finally {
      setPreflightLoading(false);
    }
  };

  const loadSmoke = async () => {
    if (session.role !== "admin") return;
    setSmokeError(null);
    setSmokeLoading(true);
    try {
      const data = await runSmokeCheck(session.token, smokeDate);
      setSmoke(data);
    } catch (err) {
      setSmokeError((err as Error).message);
    } finally {
      setSmokeLoading(false);
    }
  };

  useEffect(() => {
    void loadKpi();
  }, [session.token, period, requestDates.dateFrom, requestDates.dateTo]);

  useEffect(() => {
    if (session.role === "admin") {
      void loadPreflight();
    }
  }, [session.role, preflightDate]);

  useEffect(() => {
    if (period === "custom" && customTo < customFrom) {
      setCustomTo(customFrom);
    }
  }, [customFrom, customTo, period]);

  return (
    <section className="space-y-5 sm:space-y-6">
      <header className="game-panel">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <h1 className="game-heading">Аналитика клуба</h1>
            <p className="game-subheading mt-2 max-w-2xl">
              Показатели клуба за выбранный период: смотри динамику по дням и сравнивай выручку и загрузку по дисциплинам.
            </p>
          </div>
          <div className="grid gap-2 sm:grid-cols-3">
            <div className="game-stat p-3">
              <div className="text-xs uppercase tracking-[0.12em] text-cyan-100/60">Период</div>
              <div className="mt-1 text-sm font-black text-white">{kpi ? `${kpi.date_from} - ${kpi.date_to}` : "—"}</div>
            </div>
            <div className="game-stat p-3">
              <div className="text-xs uppercase tracking-[0.12em] text-cyan-100/60">Сессии</div>
              <div className="mt-1 text-sm font-black text-white">{kpi?.sessions_count ?? 0}</div>
            </div>
            <div className="game-stat p-3">
              <div className="text-xs uppercase tracking-[0.12em] text-cyan-100/60">Выручка</div>
              <div className="mt-1 text-sm font-black text-white">{kpi?.revenue_estimate ?? 0} ₽</div>
            </div>
          </div>
        </div>
      </header>

      <section className="game-panel space-y-4">
        <div>
          <label className="mb-2 block text-sm font-bold text-cyan-100/70">Период</label>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
            {PERIOD_OPTIONS.map((option) => (
              <button key={option.value} type="button" onClick={() => setPeriod(option.value)} className={`game-tab ${period === option.value ? "game-tab-active" : ""}`}>
                {option.label}
              </button>
            ))}
          </div>
        </div>

        {period === "custom" ? (
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <label className="mb-2 block text-sm font-bold text-cyan-100/70">Дата с</label>
              <input type="date" value={customFrom} max={customTo} onChange={(e) => handleCustomFromChange(e.target.value)} className="game-input" />
            </div>
            <div>
              <label className="mb-2 block text-sm font-bold text-cyan-100/70">Дата по</label>
              <input type="date" value={customTo} min={customFrom} onChange={(e) => handleCustomToChange(e.target.value)} className="game-input" />
            </div>
          </div>
        ) : (
          <div>
            <label className="mb-2 block text-sm font-bold text-cyan-100/70">{anchorDateLabel}</label>
            <input type="date" value={anchorDate} onChange={(e) => setAnchorDate(e.target.value)} className="game-input md:max-w-xs" />
            {period === "season" ? <p className="mt-2 text-xs text-slate-400">Сезон: {seasonBounds.start} - {seasonBounds.end}</p> : null}
          </div>
        )}

        <div className="flex justify-end">
          <button type="button" onClick={() => void loadKpi()} className="game-button w-full sm:w-auto">
            {loading ? "Пересчитываем..." : "Обновить KPI"}
          </button>
        </div>
      </section>

      {error ? <div className="game-panel border-red-400/30 bg-red-950/30 text-red-50">{error}</div> : null}

      {session.role === "admin" ? (
        <section className="game-panel space-y-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="text-xs font-black uppercase tracking-[0.12em] text-cyan-100/70">Оперативная сводка</div>
              <h2 className="mt-1 text-xl font-black text-white">Состояние сменного контура</h2>
            </div>
            <span className={readinessTone}>{preflight && preflight.blockers > 0 ? "NO-GO" : readinessLabel}</span>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <KpiCard label="Блокеры" value={String(preflight?.blockers ?? 0)} />
            <KpiCard label="Warnings" value={String(preflight?.warnings ?? 0)} />
            <KpiCard label="Smoke" value={smoke ? (smoke.ok ? "ОК" : "Ошибка") : "Не запускался"} />
            <KpiCard label="Лидер дисциплины" value={leadRide ? RIDE_TYPE_LABELS[leadRide.ride_type] : "—"} />
          </div>
        </section>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <KpiCard label="Период" value={kpi ? `${kpi.date_from} — ${kpi.date_to}` : "—"} />
        <KpiCard label="Сессий" value={String(kpi?.sessions_count ?? 0)} />
        <KpiCard label="Загрузка" value={`${String(kpi?.utilization_pct ?? 0)} %`} />
        <KpiCard label="Выручка" value={`${String(kpi?.revenue_estimate ?? 0)} ₽`} />
        <KpiCard label="Режим" value={PERIOD_OPTIONS.find((item) => item.value === (kpi?.period ?? period))?.label ?? "—"} />
      </div>

      {kpi?.plan_fact ? (
        <section className="game-panel grid gap-3 sm:grid-cols-3">
          <PlanBar label="Сессии" actual={kpi.sessions_count} target={kpi.plan_fact.sessions_target} pct={kpi.plan_fact.sessions_pct} />
          <PlanBar label="Загрузка %" actual={kpi.utilization_pct} target={kpi.plan_fact.utilization_target_pct} pct={kpi.plan_fact.utilization_pct_of_target} />
          <PlanBar label="Выручка" actual={kpi.revenue_estimate} target={kpi.plan_fact.revenue_target} pct={kpi.plan_fact.revenue_pct} />
        </section>
      ) : null}

      {session.role === "admin" ? (
        <button
          type="button"
          className="game-button"
          onClick={() => void runAnalyticsSnapshot(session.token, anchorDate).then(() => setError(null)).catch((err) => setError((err as Error).message))}
        >
          Записать analytics_daily snapshot
        </button>
      ) : null}

      <section className="game-panel space-y-4">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="text-xs font-black uppercase tracking-[0.12em] text-cyan-100/70">График KPI</div>
            <h2 className="mt-1 text-xl font-black text-white">Прогресс по дням</h2>
          </div>
          <div className="flex flex-wrap gap-2 text-xs">
            <span className="game-chip text-cyan-100">Бирюзовые столбцы — выручка</span>
            <span className="game-chip text-orange-100">Оранжевая линия — сессии</span>
          </div>
        </div>
        <TimelineChart points={kpi?.timeline ?? []} />
      </section>

      <section className="game-panel space-y-4">
        <div>
          <div className="text-xs font-black uppercase tracking-[0.12em] text-cyan-100/70">Разрез по дисциплинам</div>
          <h2 className="mt-1 text-xl font-black text-white">Разрез по дисциплинам</h2>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {(kpi?.ride_breakdown ?? []).map((item) => (
            <article key={item.ride_type} className="game-card space-y-3">
              <div className={`text-sm font-black uppercase tracking-[0.12em] ${RIDE_TYPE_TONES[item.ride_type]}`}>{RIDE_TYPE_LABELS[item.ride_type]}</div>
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="game-stat p-3">
                  <div className="text-xs uppercase tracking-[0.12em] text-cyan-100/60">Сессий</div>
                  <div className="mt-1 text-2xl font-black text-white">{item.sessions_count}</div>
                </div>
                <div className="game-stat p-3">
                  <div className="text-xs uppercase tracking-[0.12em] text-cyan-100/60">Выручка</div>
                  <div className="mt-1 text-2xl font-black text-white">{item.revenue_estimate} ₽</div>
                </div>
              </div>
            </article>
          ))}
        </div>
      </section>

      {session.role === "admin" ? (
        <section className="game-panel space-y-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="text-xs font-black uppercase tracking-[0.12em] text-cyan-100/70">Проверка перед сменой</div>
              <h2 className="mt-1 text-xl font-black text-white">Предстартовая проверка</h2>
            </div>
            <div className="flex gap-2">
              <button type="button" onClick={() => setPreflightExpanded((value) => !value)} className="game-button-secondary px-4">
                {preflightExpanded ? "Свернуть" : "Развернуть"}
              </button>
            </div>
          </div>

          {preflight ? (
            <div className="flex flex-wrap gap-2 text-xs">
              <span className="game-chip text-cyan-100">Дата: {preflight.target_date}</span>
              <span className="game-badge-warn">Блокеры: {preflight.blockers}</span>
              <span className="game-badge-info">Warnings: {preflight.warnings}</span>
            </div>
          ) : null}

          {preflightExpanded ? (
            <>
              <div className="grid gap-3 md:grid-cols-[220px_200px]">
                <div>
                  <label className="mb-2 block text-sm font-bold text-cyan-100/70">Дата смены</label>
                  <input type="date" value={preflightDate} onChange={(e) => setPreflightDate(e.target.value)} className="game-input" />
                </div>
                <div className="flex items-end">
                  <button type="button" onClick={() => void loadPreflight()} className="game-button w-full">
                    {preflightLoading ? "Проверяем..." : "Проверить готовность"}
                  </button>
                </div>
              </div>

              {preflightError ? <div className="game-panel border-red-400/30 bg-red-950/30 text-red-50">{preflightError}</div> : null}

              <div className="space-y-2">
                {preflight?.checks.map((item) => (
                  <div key={`${item.level}-${item.code}`} className={`game-card ${CHECK_LEVEL_STYLES[item.level]}`}>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="game-chip text-white">{CHECK_LEVEL_LABELS[item.level]}</span>
                      <span className="font-black uppercase tracking-[0.08em]">{item.code}</span>
                    </div>
                    <div className="mt-2 text-sm">{item.message}</div>
                  </div>
                ))}
              </div>
            </>
          ) : null}
        </section>
      ) : null}

      {session.role === "admin" ? (
        <section className="game-panel space-y-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="text-xs font-black uppercase tracking-[0.12em] text-cyan-100/70">Быстрая проверка контура</div>
              <h2 className="mt-1 text-xl font-black text-white">Проверка рабочего сценария</h2>
            </div>
            <button type="button" onClick={() => setSmokeExpanded((value) => !value)} className="game-button-secondary px-4">
              {smokeExpanded ? "Свернуть" : "Развернуть"}
            </button>
          </div>

          {smoke ? (
            <div className="flex flex-wrap gap-2 text-xs">
              <span className={smoke.ok ? "game-badge-success" : "game-badge-warn"}>Статус: {smoke.ok ? "ОК" : "Ошибка"}</span>
              <span className="game-chip text-cyan-100">Дата: {smoke.target_date}</span>
              <span className="game-chip text-cyan-100">Бронь: {smoke.created_booking_id || "—"}</span>
            </div>
          ) : null}

          {smokeExpanded ? (
            <>
              <div className="grid gap-3 md:grid-cols-[220px_200px]">
                <div>
                  <label className="mb-2 block text-sm font-bold text-cyan-100/70">Дата smoke</label>
                  <input type="date" value={smokeDate} onChange={(e) => setSmokeDate(e.target.value)} className="game-input" />
                </div>
                <div className="flex items-end">
                  <button type="button" onClick={() => void loadSmoke()} className="game-button w-full">
                    {smokeLoading ? "Запускаем..." : "Запустить smoke"}
                  </button>
                </div>
              </div>

              {smokeError ? <div className="game-panel border-red-400/30 bg-red-950/30 text-red-50">{smokeError}</div> : null}

              <div className="space-y-2">
                {smoke?.checks.map((item) => (
                  <div key={`${item.level}-${item.code}`} className={`game-card ${SMOKE_LEVEL_STYLES[item.level]}`}>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="game-chip text-white">{SMOKE_LEVEL_LABELS[item.level]}</span>
                      <span className="font-black uppercase tracking-[0.08em]">{item.code}</span>
                    </div>
                    <div className="mt-2 text-sm">{item.message}</div>
                  </div>
                ))}
              </div>
            </>
          ) : null}
        </section>
      ) : null}
    </section>
  );
}

function KpiCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <article className="game-stat">
      <p className="text-xs font-black uppercase tracking-[0.12em] text-cyan-100/60">{label}</p>
      <p className="mt-2 break-words text-2xl font-black text-white">{value}</p>
    </article>
  );
}

function TimelineChart({ points }: { points: KpiTimelinePoint[] }): JSX.Element {
  if (!points.length) {
    return <div className="game-card text-sm text-slate-300">Для этого периода пока нет данных для графика.</div>;
  }

  const width = 720;
  const height = 260;
  const padX = 40;
  const padTop = 20;
  const padBottom = 42;
  const chartHeight = height - padTop - padBottom;
  const chartWidth = width - padX * 2;
  const maxRevenue = Math.max(...points.map((point) => point.revenue_estimate), 1);
  const maxSessions = Math.max(...points.map((point) => point.sessions_count), 1);
  const step = points.length === 1 ? chartWidth : chartWidth / (points.length - 1);
  const barWidth = Math.max(12, Math.min(34, chartWidth / Math.max(points.length * 1.8, 1)));

  const sessionPath = points
    .map((point, index) => {
      const x = padX + step * index;
      const y = padTop + chartHeight - (point.sessions_count / maxSessions) * chartHeight;
      return `${index === 0 ? "M" : "L"}${x} ${y}`;
    })
    .join(" ");

  return (
    <div className="game-card overflow-x-auto">
      <svg viewBox={`0 0 ${width} ${height}`} className="min-w-[680px] text-white">
        {[0, 0.25, 0.5, 0.75, 1].map((ratio, index) => {
          const y = padTop + chartHeight * ratio;
          return <line key={index} x1={padX} y1={y} x2={width - padX} y2={y} stroke="rgba(255,255,255,0.08)" strokeDasharray="4 8" />;
        })}

        {points.map((point, index) => {
          const x = padX + step * index;
          const barHeight = (point.revenue_estimate / maxRevenue) * chartHeight;
          const y = padTop + chartHeight - barHeight;
          const pointY = padTop + chartHeight - (point.sessions_count / maxSessions) * chartHeight;
          return (
            <g key={point.date}>
              <rect x={x - barWidth / 2} y={y} width={barWidth} height={Math.max(barHeight, 4)} rx={8} fill="url(#revenueGradient)" />
              <circle cx={x} cy={pointY} r={5} fill="#ffb44d" stroke="#fff5d9" strokeWidth={2} />
              <text x={x} y={height - 16} textAnchor="middle" fontSize="11" fill="rgba(230,246,255,0.72)">{formatShortDate(point.date)}</text>
            </g>
          );
        })}

        <path d={sessionPath} fill="none" stroke="#ffb44d" strokeWidth={4} strokeLinecap="round" strokeLinejoin="round" />

        <defs>
          <linearGradient id="revenueGradient" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="#59e3ff" />
            <stop offset="100%" stopColor="#1768ff" />
          </linearGradient>
        </defs>
      </svg>

      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        <LegendCard label="Макс. выручка" value={`${maxRevenue} ₽`} tone="text-cyan-200" />
        <LegendCard label="Макс. сессий" value={String(maxSessions)} tone="text-orange-200" />
        <LegendCard label="Точек на графике" value={String(points.length)} tone="text-fuchsia-200" />
      </div>
    </div>
  );
}

function LegendCard({ label, value, tone }: { label: string; value: string; tone: string }): JSX.Element {
  return (
    <div className="game-stat p-3">
      <div className="text-xs uppercase tracking-[0.12em] text-cyan-100/60">{label}</div>
      <div className={`mt-1 text-lg font-black ${tone}`}>{value}</div>
    </div>
  );
}

function PlanBar({
  label,
  actual,
  target,
  pct,
}: {
  label: string;
  actual: number;
  target?: number | null;
  pct?: number | null;
}): JSX.Element {
  const width = Math.min(pct ?? 0, 100);
  return (
    <div className="game-card space-y-2">
      <div className="text-sm font-black text-white">{label}</div>
      <div className="text-xs text-slate-300">
        Факт: {actual} / План: {target ?? "—"} ({pct ?? "—"}%)
      </div>
      <div className="h-2 rounded-full bg-slate-800">
        <div className="h-2 rounded-full bg-cyan-400" style={{ width: `${width}%` }} />
      </div>
    </div>
  );
}

function formatShortDate(value: string): string {
  const [, month, day] = value.split("-");
  return `${day}.${month}`;
}


