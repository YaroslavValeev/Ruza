import { useEffect, useMemo, useState } from "react";

import { getKpiSummary, getPreflightSummary, runAnalyticsSnapshot, runSmokeCheck } from "../api/client";
import { formatPercent, formatRub, formatRubMinor, toFiniteNumber } from "../lib/format";
import { formatDateRangeRu, formatDateRu, formatDayMonthNumeric, formatLocalIsoDate } from "../lib/dates";
import { preflightCheckText, rideTypeLabel, smokeCheckText } from "../lib/labels";
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


const RIDE_TYPE_TONES: Record<RideType, string> = {
  wakeboard: "text-teal-800",
  surf: "text-amber-800",
  skim: "text-stone-700",
};

const CHECK_LEVEL_LABELS: Record<PreflightLevel, string> = {
  PASS: "Норма",
  WARN: "Внимание",
  BLOCKER: "Блокер",
};

const CHECK_LEVEL_STYLES: Record<PreflightLevel, string> = {
  PASS: "border-emerald-600/25 bg-emerald-50 text-emerald-900",
  WARN: "border-amber-600/25 bg-amber-50 text-amber-900",
  BLOCKER: "border-red-600/25 bg-red-50 text-red-900",
};

const SMOKE_LEVEL_LABELS: Record<SmokeLevel, string> = {
  PASS: "Норма",
  FAIL: "Ошибка",
};

const SMOKE_LEVEL_STYLES: Record<SmokeLevel, string> = {
  PASS: "border-emerald-600/25 bg-emerald-50 text-emerald-900",
  FAIL: "border-red-600/25 bg-red-50 text-red-900",
};

function getToday(): string {
  return formatLocalIsoDate();
}

function getSeasonBounds(dateText: string): { start: string; end: string } {
  const year = Number(dateText.slice(0, 4)) || new Date().getFullYear();
  return {
    start: `${year}-05-01`,
    end: `${year}-09-25`,
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
      ? "rounded-full border border-red-600/30 bg-red-50 px-3 py-1 text-xs font-black uppercase tracking-[0.08em] text-red-800"
      : preflight.warnings > 0
        ? "game-badge-info"
        : "game-badge-success"
    : "game-chip ";

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
              Показатели клуба за выбранный период: стоимость завершённых заездов, фактические поступления, возвраты и задолженность.
            </p>
          </div>
        </div>
      </header>

      <section className="game-panel space-y-4">
        <div>
          <label className="mb-2 block text-sm font-bold text-[color:var(--ink-muted)]">Период</label>
          <div className="grid grid-cols-3 gap-2 lg:grid-cols-5" role="group" aria-label="Период">
            {PERIOD_OPTIONS.map((option) => (
              <button key={option.value} type="button" onClick={() => setPeriod(option.value)} aria-pressed={period === option.value} className={`game-tab ${period === option.value ? "game-tab-active" : ""}`}>
                {option.label}
              </button>
            ))}
          </div>
        </div>

        {period === "custom" ? (
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <label className="mb-2 block text-sm font-bold text-[color:var(--ink-muted)]">Дата с</label>
              <input type="date" value={customFrom} max={customTo} onChange={(e) => handleCustomFromChange(e.target.value)} className="game-input" />
            </div>
            <div>
              <label className="mb-2 block text-sm font-bold text-[color:var(--ink-muted)]">Дата по</label>
              <input type="date" value={customTo} min={customFrom} onChange={(e) => handleCustomToChange(e.target.value)} className="game-input" />
            </div>
          </div>
        ) : (
          <div>
            <label className="mb-2 block text-sm font-bold text-[color:var(--ink-muted)]">{anchorDateLabel}</label>
            <input type="date" value={anchorDate} onChange={(e) => setAnchorDate(e.target.value)} className="game-input md:max-w-xs" />
            {period === "season" ? <p className="mt-2 text-xs text-[color:var(--ink-muted)]">Сезон: {formatDateRangeRu(seasonBounds.start, seasonBounds.end)}</p> : null}
          </div>
        )}

        <div className="flex justify-end">
          <button type="button" onClick={() => void loadKpi()} className="game-button w-full sm:w-auto">
            {loading ? "Пересчитываем…" : "Обновить показатели"}
          </button>
        </div>
      </section>

      {error ? <div className="game-panel border-red-600/25 bg-red-50 text-red-900">{error}</div> : null}

      {session.role === "admin" ? (
        <section className="game-panel space-y-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="text-xs font-black uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">Оперативная сводка</div>
              <h2 className="mt-1 text-xl font-black text-[color:var(--ink)]">Состояние сменного контура</h2>
            </div>
            <span className={readinessTone}>{preflight && preflight.blockers > 0 ? "Нельзя стартовать" : readinessLabel}</span>
          </div>

          <div className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
            <KpiCard label="Блокеры" value={String(preflight?.blockers ?? 0)} />
            <KpiCard label="Предупреждения" value={String(preflight?.warnings ?? 0)} />
            <KpiCard label="Проверка сценария" value={smoke ? (smoke.ok ? "Пройдена" : "Ошибка") : "Не запускалась"} />
            <KpiCard label="Лидирующая дисциплина" value={leadRide ? rideTypeLabel(leadRide.ride_type, { capitalize: true }) : "—"} />
          </div>
        </section>
      ) : null}

      <div className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
        <KpiCard label="Период" value={kpi ? formatDateRangeRu(kpi.date_from, kpi.date_to) : "—"} />
        <KpiCard label="Сессий" value={String(toFiniteNumber(kpi?.sessions_count) ?? 0)} />
        <KpiCard label="Загрузка" value={formatPercent(kpi?.utilization_pct ?? 0, 0)} />
        <KpiCard label="Стоимость завершённых заездов" value={formatRub(kpi?.revenue_estimate ?? 0)} />
        <KpiCard label="Поступления" value={formatRubMinor(kpi?.payments_gross_minor)} />
        <KpiCard label="Возвраты" value={formatRubMinor(kpi?.refunds_total_minor)} />
        <KpiCard label="Чистое поступление" value={formatRubMinor(kpi?.net_revenue_minor)} />
        <KpiCard label="К оплате" value={formatRubMinor(kpi?.outstanding_minor)} />
        <KpiCard label="Период расчёта" value={PERIOD_OPTIONS.find((item) => item.value === (kpi?.period ?? period))?.label ?? "—"} />
      </div>

      {kpi?.plan_fact ? (
        <section className="game-panel grid gap-3 sm:grid-cols-3 items-stretch">
          <PlanBar label="Сессии" actual={kpi.sessions_count} target={kpi.plan_fact.sessions_target} pct={kpi.plan_fact.sessions_pct} />
          <PlanBar label="Загрузка, %" actual={kpi.utilization_pct} target={kpi.plan_fact.utilization_target_pct} pct={kpi.plan_fact.utilization_pct_of_target} />
          <PlanBar label="Стоимость завершённых заездов" actual={kpi.revenue_estimate} target={kpi.plan_fact.revenue_target} pct={kpi.plan_fact.revenue_pct} />
        </section>
      ) : null}

      {session.role === "admin" ? (
        <button
          type="button"
          className="game-button"
          onClick={() => void runAnalyticsSnapshot(session.token, anchorDate).then(() => setError(null)).catch((err) => setError((err as Error).message))}
          title={`Дата снимка: ${formatDateRu(anchorDate)}`}
        >
          Сохранить дневной снимок аналитики
        </button>
      ) : null}

      <section className="game-panel space-y-4">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="text-xs font-black uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">График показателей</div>
            <h2 className="mt-1 text-xl font-black text-[color:var(--ink)]">Прогресс по дням</h2>
          </div>
          <div className="flex flex-wrap gap-2 text-xs">
            <span className="game-chip">Бирюзовые столбцы — стоимость завершённых заездов</span>
            <span className="game-chip">Янтарная линия — сессии</span>
          </div>
        </div>
        <TimelineChart points={kpi?.timeline ?? []} />
      </section>

      <section className="game-panel space-y-4">
        <div>
          <div className="text-xs font-black uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">Дисциплины</div>
          <h2 className="mt-1 text-xl font-black text-[color:var(--ink)]">Разрез по дисциплинам</h2>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {(kpi?.ride_breakdown ?? []).map((item) => (
            <article key={item.ride_type} className="game-card space-y-3">
              <div className={`text-sm font-black uppercase tracking-[0.12em] ${RIDE_TYPE_TONES[item.ride_type]}`}>{rideTypeLabel(item.ride_type)}</div>
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="game-stat p-3">
                  <div className="text-xs uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">Сессий</div>
                  <div className="mt-1 text-2xl font-black text-[color:var(--ink)]">{item.sessions_count}</div>
                </div>
                <div className="game-stat p-3">
                  <div className="text-xs uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">Стоимость заездов</div>
                  <div className="mt-1 text-2xl font-black text-[color:var(--ink)]">{formatRub(item.revenue_estimate)}</div>
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
              <div className="text-xs font-black uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">Проверка перед сменой</div>
              <h2 className="mt-1 text-xl font-black text-[color:var(--ink)]">Предстартовая проверка</h2>
            </div>
            <div className="flex gap-2">
              <button type="button" onClick={() => setPreflightExpanded((value) => !value)} className="game-button-secondary px-4">
                {preflightExpanded ? "Свернуть" : "Развернуть"}
              </button>
            </div>
          </div>

          {preflight ? (
            <div className="flex flex-wrap gap-2 text-xs">
              <span className="game-chip">Дата: {formatDateRu(preflight.target_date)}</span>
              <span className="game-badge-warn">Блокеры: {preflight.blockers}</span>
              <span className="game-badge-info">Предупреждения: {preflight.warnings}</span>
            </div>
          ) : null}

          {preflightExpanded ? (
            <>
              <div className="grid gap-3 md:grid-cols-[220px_200px]">
                <div>
                  <label className="mb-2 block text-sm font-bold text-[color:var(--ink-muted)]">Дата смены</label>
                  <input type="date" value={preflightDate} onChange={(e) => setPreflightDate(e.target.value)} className="game-input" />
                </div>
                <div className="flex items-end">
                  <button type="button" onClick={() => void loadPreflight()} className="game-button w-full">
                    {preflightLoading ? "Проверяем…" : "Проверить готовность"}
                  </button>
                </div>
              </div>

              {preflightError ? <div className="game-panel border-red-600/25 bg-red-50 text-red-900">{preflightError}</div> : null}

              <div className="space-y-2">
                {preflight?.checks.map((item) => {
                  const view = preflightCheckText(item.level, item.code, item.message);
                  return (
                    <div key={`${item.level}-${item.code}`} className={`game-card ${CHECK_LEVEL_STYLES[item.level]}`} title={item.message}>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="game-chip text-[color:var(--ink)]">{CHECK_LEVEL_LABELS[item.level]}</span>
                        <span className="font-black">{view.title}</span>
                      </div>
                      <div className="mt-2 text-sm">{view.text}</div>
                    </div>
                  );
                })}
              </div>
            </>
          ) : null}
        </section>
      ) : null}

      {session.role === "admin" ? (
        <section className="game-panel space-y-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="text-xs font-black uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">Быстрая проверка контура</div>
              <h2 className="mt-1 text-xl font-black text-[color:var(--ink)]">Проверка рабочего сценария</h2>
            </div>
            <button type="button" onClick={() => setSmokeExpanded((value) => !value)} className="game-button-secondary px-4">
              {smokeExpanded ? "Свернуть" : "Развернуть"}
            </button>
          </div>

          {smoke ? (
            <div className="flex flex-wrap gap-2 text-xs">
              <span className={smoke.ok ? "game-badge-success" : "game-badge-warn"}>{smoke.ok ? "Сценарий пройден" : "Есть ошибки"}</span>
              <span className="game-chip">Дата: {formatDateRu(smoke.target_date)}</span>
              <span className="game-chip">{smoke.created_booking_id ? "Тестовая бронь создана" : "Тестовая бронь не создавалась"}</span>
            </div>
          ) : null}

          {smokeExpanded ? (
            <>
              <div className="grid gap-3 md:grid-cols-[220px_200px]">
                <div>
                  <label className="mb-2 block text-sm font-bold text-[color:var(--ink-muted)]">Дата проверки</label>
                  <input type="date" value={smokeDate} onChange={(e) => setSmokeDate(e.target.value)} className="game-input" />
                </div>
                <div className="flex items-end">
                  <button type="button" onClick={() => void loadSmoke()} className="game-button w-full">
                    {smokeLoading ? "Запускаем…" : "Запустить проверку"}
                  </button>
                </div>
              </div>

              {smokeError ? <div className="game-panel border-red-600/25 bg-red-50 text-red-900">{smokeError}</div> : null}

              <div className="space-y-2">
                {smoke?.checks.map((item) => {
                  const view = smokeCheckText(item.level, item.code);
                  return (
                    <div key={`${item.level}-${item.code}`} className={`game-card ${SMOKE_LEVEL_STYLES[item.level]}`} title={item.message}>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="game-chip text-[color:var(--ink)]">{SMOKE_LEVEL_LABELS[item.level]}</span>
                        <span className="font-black">{view.title}</span>
                      </div>
                      <div className="mt-2 text-sm">{view.text}</div>
                    </div>
                  );
                })}
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
    <article className="game-stat min-w-0">
      <p className="text-[11px] font-black uppercase tracking-[0.08em] text-[color:var(--ink-muted)] sm:text-xs sm:tracking-[0.12em]">{label}</p>
      <p className="mt-2 break-words text-lg font-black leading-tight text-[color:var(--ink)] sm:text-2xl">{value}</p>
    </article>
  );
}

function TimelineChart({ points }: { points: KpiTimelinePoint[] }): JSX.Element {
  if (points.length < 2) {
    return (
      <div className="game-card text-sm text-[color:var(--ink-muted)]">
        {points.length === 0 ? "За этот период данных для графика пока нет." : "Для графика нужно минимум два дня с данными — выберите неделю, месяц или сезон."}
      </div>
    );
  }

  const width = 720;
  const height = 260;
  const padX = 40;
  const padTop = 20;
  const padBottom = 42;
  const chartHeight = height - padTop - padBottom;
  const chartWidth = width - padX * 2;
  const safePoints = points.map((point) => ({
    ...point,
    revenue_estimate: toFiniteNumber(point.revenue_estimate) ?? 0,
    sessions_count: toFiniteNumber(point.sessions_count) ?? 0,
  }));
  const peakRevenue = Math.max(...safePoints.map((point) => point.revenue_estimate), 0);
  const peakSessions = Math.max(...safePoints.map((point) => point.sessions_count), 0);
  const maxRevenue = Math.max(peakRevenue, 1);
  const maxSessions = Math.max(peakSessions, 1);
  const step = points.length === 1 ? chartWidth : chartWidth / (points.length - 1);
  const barWidth = Math.max(12, Math.min(34, chartWidth / Math.max(points.length * 1.8, 1)));

  const sessionPath = safePoints
    .map((point, index) => {
      const x = padX + step * index;
      const y = padTop + chartHeight - (point.sessions_count / maxSessions) * chartHeight;
      return `${index === 0 ? "M" : "L"}${x} ${y}`;
    })
    .join(" ");

  return (
    <div className="game-card overflow-x-auto">
      <svg viewBox={`0 0 ${width} ${height}`} className="min-w-[680px] text-[color:var(--ink)]">
        {[0, 0.25, 0.5, 0.75, 1].map((ratio, index) => {
          const y = padTop + chartHeight * ratio;
          return <line key={index} x1={padX} y1={y} x2={width - padX} y2={y} stroke="rgba(26,36,33,0.1)" strokeDasharray="4 8" />;
        })}

        {safePoints.map((point, index) => {
          const x = padX + step * index;
          const barHeight = (point.revenue_estimate / maxRevenue) * chartHeight;
          const y = padTop + chartHeight - barHeight;
          const pointY = padTop + chartHeight - (point.sessions_count / maxSessions) * chartHeight;
          return (
            <g key={point.date}>
              <rect x={x - barWidth / 2} y={y} width={barWidth} height={Math.max(barHeight, 4)} rx={8} fill="url(#revenueGradient)" />
              <circle cx={x} cy={pointY} r={5} fill="#C9782A" stroke="#F7F4ED" strokeWidth={2} />
              <text x={x} y={height - 16} textAnchor="middle" fontSize="11" fill="#5C6B66">{formatDayMonthNumeric(point.date)}</text>
            </g>
          );
        })}

        <path d={sessionPath} fill="none" stroke="#C9782A" strokeWidth={4} strokeLinecap="round" strokeLinejoin="round" />

        <defs>
          <linearGradient id="revenueGradient" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="#128577" />
            <stop offset="100%" stopColor="#0E6E62" />
          </linearGradient>
        </defs>
      </svg>

      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        <LegendCard label="Максимум выручки за день" value={formatRub(peakRevenue)} tone="text-[color:var(--ink)]" />
        <LegendCard label="Максимум сессий за день" value={String(peakSessions)} tone="text-[color:var(--ink)]" />
        <LegendCard label="Дней на графике" value={String(points.length)} tone="text-[color:var(--ink)]" />
      </div>
    </div>
  );
}

function LegendCard({ label, value, tone }: { label: string; value: string; tone: string }): JSX.Element {
  return (
    <div className="game-stat p-3">
      <div className="text-xs uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">{label}</div>
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
  const pctValue = toFiniteNumber(pct);
  const width = Math.max(Math.min(pctValue ?? 0, 100), 0);
  const actualText = toFiniteNumber(actual) === null ? "—" : String(actual);
  const targetText = toFiniteNumber(target) === null ? "—" : String(target);
  return (
    <div className="game-card space-y-3 p-4">
      <div className="text-sm font-black text-[color:var(--ink)]">{label}</div>
      <div className="text-xs text-[color:var(--ink-muted)]">
        Факт: {actualText} / План: {targetText} ({pctValue === null ? "—" : `${pctValue} %`})
      </div>
      <div className="h-2.5 overflow-hidden rounded-full" style={{ background: "rgba(26,36,33,0.12)" }}>
        <div
          className="h-full rounded-full"
          style={{ width: `${width}%`, background: "linear-gradient(90deg, #128577 0%, #0E6E62 100%)" }}
        />
      </div>
    </div>
  );
}



