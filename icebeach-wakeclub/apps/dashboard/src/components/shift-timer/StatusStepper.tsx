import { useId, useState } from "react";

import { updateBookingPrep } from "../../api/client";
import { BookingItem, StaffSession, WarmupState } from "../../types";
import { currentFlowIndex, emitBookingUpdated, FLOW_STEPS, flowActionTitle, getNextStep, runFlowAction } from "../../lib/status-flow";
import { emitShiftLiveRefresh } from "./LiveShiftStrip";

type StatusStepperProps = {
  session: StaffSession;
  booking: Pick<BookingItem, "booking_id" | "status" | "warmup_state" | "timer_state" | "boat_id">;
  onUpdated?: (booking: BookingItem) => void;
  /** full — полные подписи с lg, short — всегда короткие (узкие карточки). */
  labels?: "auto" | "short";
};

/**
 * Этапы заезда. Пройденные и будущие этапы — обычный текст (не кнопки).
 * Следующий этап — настоящая кнопка: переводит бронь одним нажатием, если роли это разрешено,
 * иначе неактивна и под этапами написано, кто и где это делает.
 */
export function StatusStepper({ session, booking, onUpdated, labels = "auto" }: StatusStepperProps): JSX.Element {
  const reasonId = useId();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const current = currentFlowIndex(booking.status);
  const next = getNextStep(session, booking);
  const closed = current === null;

  const apply = async (task: () => Promise<BookingItem>) => {
    setBusy(true);
    setError(null);
    try {
      const updated = await task();
      onUpdated?.(updated);
      emitBookingUpdated(updated);
      emitShiftLiveRefresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const setWarmup = (state: WarmupState) => apply(() => updateBookingPrep(booking.booking_id, { warmup_state: state }, session.token));

  const stepLabel = (index: number) => {
    const step = FLOW_STEPS[index];
    const full = index === 0 && booking.status === "late" ? "Опоздание" : step.full;
    const short = index === 0 && booking.status === "late" ? "Опозд." : step.short;
    if (labels === "short") return <span>{short}</span>;
    return (
      <>
        <span className="lg:hidden">{short}</span>
        <span className="hidden lg:inline">{full}</span>
      </>
    );
  };

  const nextButton = (className: string, fullLabel: boolean) =>
    next ? (
      <button
        type="button"
        className={className}
        disabled={!next.allowed || busy}
        aria-describedby={!next.allowed && next.reason ? reasonId : undefined}
        aria-label={next.allowed ? flowActionTitle(next.action) : `${FLOW_STEPS[next.index].full}: недоступно`}
        title={next.allowed ? flowActionTitle(next.action) : next.reason ?? undefined}
        onClick={() => void apply(() => runFlowAction(next.action, booking.booking_id, session.token))}
      >
        {next.allowed ? <span aria-hidden="true">→</span> : null}
        {busy ? <span>…</span> : fullLabel ? <span>{next.allowed ? flowActionTitle(next.action) : FLOW_STEPS[next.index].full}</span> : stepLabel(next.index)}
      </button>
    ) : null;

  return (
    <div className="space-y-2">
      {/* Телефон: пять колонок не помещаются — текущий этап строкой и кнопка следующего шага во всю ширину. */}
      <div className="space-y-2 sm:hidden">
        <div className="flex items-baseline justify-between gap-3 text-sm">
          <span className="font-black text-[color:var(--ink)]">
            {closed ? (booking.status === "no_show" ? "Неявка" : "Отменено") : current !== null ? (current === 0 && booking.status === "late" ? "Опоздание" : FLOW_STEPS[current].full) : ""}
          </span>
          <span className="text-xs text-[color:var(--ink-muted)]">{current !== null ? `Шаг ${current + 1} из ${FLOW_STEPS.length}` : ""}</span>
        </div>
        <div className="shift-progress" aria-hidden="true">
          <div className="shift-progress-fill" style={{ width: `${current !== null ? (current / (FLOW_STEPS.length - 1)) * 100 : 0}%` }} />
        </div>
        {nextButton("status-step-next min-h-12 text-sm", true)}
      </div>

      <ol className="status-steps hidden sm:grid" aria-label="Этапы заезда">
        {FLOW_STEPS.map((step, index) => {
          if (!closed && current !== null && index < current) {
            return (
              <li key={step.status} className="status-step status-step-done" title={`${step.full} — пройдено`}>
                <span aria-hidden="true">✓</span>
                {stepLabel(index)}
                <span className="sr-only"> — пройдено</span>
              </li>
            );
          }
          if (!closed && index === current) {
            return (
              <li key={step.status} className="status-step status-step-current" aria-current="step" title={`${step.full} — текущий этап`}>
                {stepLabel(index)}
              </li>
            );
          }
          if (next && index === next.index) {
            return (
              <li key={step.status} className="min-w-0">
                {nextButton("status-step-next", false)}
              </li>
            );
          }
          return (
            <li key={step.status} className="status-step status-step-future">
              {stepLabel(index)}
            </li>
          );
        })}
      </ol>

      {closed ? (
        <p className="status-step-reason">
          {booking.status === "no_show" ? "Клиент не пришёл — этапы заезда не продолжаются." : "Бронь отменена — этапы заезда не продолжаются."}
        </p>
      ) : null}
      {next && !next.allowed && next.reason ? (
        <p id={reasonId} className="status-step-reason">
          {next.reason}
        </p>
      ) : null}
      {next?.needsWarmup && next.canWarmup ? (
        <div className="grid grid-cols-2 gap-2">
          <button type="button" className="game-button-secondary px-3 text-xs" disabled={busy} onClick={() => void setWarmup("warmed_up")}>
            Размялся
          </button>
          <button type="button" className="game-button-secondary px-3 text-xs" disabled={busy} onClick={() => void setWarmup("no_warmup")}>
            Без разминки
          </button>
        </div>
      ) : null}
      {error ? (
        <div role="alert" className="rounded-2xl border border-red-600/25 bg-red-50 px-3 py-2 text-sm text-red-900">
          {error}
        </div>
      ) : null}
    </div>
  );
}
