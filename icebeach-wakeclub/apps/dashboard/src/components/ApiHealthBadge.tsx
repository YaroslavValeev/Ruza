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
      setCheckedAt(new Date().toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" }));
    } catch {
      setHealthy(false);
      setCheckedAt(new Date().toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" }));
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
      ? "bg-emerald-500"
      : healthy === false
        ? "bg-red-500"
        : "bg-stone-400";

  const label =
    healthy === true ? "Сервер на связи" : healthy === false ? "Нет связи" : "Проверяем связь";

  if (compact) {
    return (
      <button
        type="button"
        onClick={() => void check()}
        className="flex min-h-[44px] items-center gap-2 rounded-xl border px-3 py-2 text-xs font-bold"
        style={{ borderColor: "var(--border)", color: "var(--ink)", background: "var(--panel-solid)" }}
      >
        <span className={`inline-block h-2.5 w-2.5 rounded-full ${dotClass}`} />
        <span className="whitespace-nowrap">{loading ? "Проверяем…" : label}</span>
      </button>
    );
  }

  return (
    <div className="game-panel-soft">
      <div className="flex items-center gap-2">
        <span className={`inline-block h-3 w-3 rounded-full ${dotClass}`} />
        <span className="text-xs font-black uppercase tracking-[0.12em] text-[color:var(--ink)]">{label}</span>
      </div>
      <div className="mt-1 text-xs text-[color:var(--ink-muted)]">{checkedAt ? `Проверено в ${checkedAt}` : "Ещё не проверяли"}</div>
      <button type="button" onClick={() => void check()} className="game-button-secondary mt-2 whitespace-nowrap px-3 py-2 text-xs">
        {loading ? "Проверяем…" : "Проверить связь"}
      </button>
    </div>
  );
}
