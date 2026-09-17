import { useEffect, useState } from "react";

import { getHealthStatus } from "../api/client";

type ApiHealthBadgeProps = {
  compact?: boolean;
};

export function ApiHealthBadge({ compact = false }: ApiHealthBadgeProps): JSX.Element {
  const [healthy, setHealthy] = useState<boolean | null>(null);
  const [checkedAt, setCheckedAt] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const check = async () => {
    setLoading(true);
    try {
      await getHealthStatus();
      setHealthy(true);
      setCheckedAt(new Date().toLocaleTimeString("ru-RU"));
    } catch {
      setHealthy(false);
      setCheckedAt(new Date().toLocaleTimeString("ru-RU"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void check();
    const id = window.setInterval(() => void check(), 15000);
    return () => window.clearInterval(id);
  }, []);

  const dotClass =
    healthy === true
      ? "bg-emerald-400 shadow-[0_0_12px_rgba(52,211,153,0.7)]"
      : healthy === false
        ? "bg-red-400 shadow-[0_0_12px_rgba(248,113,113,0.7)]"
        : "bg-slate-400";

  const label =
    healthy === true ? "API на связи" : healthy === false ? "API недоступно" : "Проверка API";

  if (compact) {
    return (
      <button
        type="button"
        onClick={() => void check()}
        className="flex min-h-[44px] items-center gap-2 rounded-xl border border-slate-800 bg-slate-900/80 px-3 py-2 text-xs font-bold text-slate-200"
      >
        <span className={`inline-block h-2.5 w-2.5 rounded-full ${dotClass}`} />
        {loading ? "..." : label}
      </button>
    );
  }

  return (
    <div className="game-panel-soft">
      <div className="flex items-center gap-2">
        <span className={`inline-block h-3 w-3 rounded-full ${dotClass}`} />
        <span className="text-xs font-black uppercase tracking-[0.12em] text-slate-200">{label}</span>
      </div>
      <div className="mt-1 text-xs text-slate-400">{checkedAt ? `Проверка: ${checkedAt}` : "Ещё не проверяли"}</div>
      <button type="button" onClick={() => void check()} className="game-button-secondary mt-2 px-3 py-2 text-xs">
        {loading ? "..." : "Проверить"}
      </button>
    </div>
  );
}
