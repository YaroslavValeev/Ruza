import { Link } from "react-router-dom";

import { getMobileRouteForRole } from "../auth/session";
import { roleLabel } from "../lib/labels";
import { StaffRole } from "../types";

type MobileForbiddenProps = {
  role: StaffRole;
  pageLabel: string;
};

export function MobileForbidden({ role, pageLabel }: MobileForbiddenProps): JSX.Element {
  const home = getMobileRouteForRole(role);

  return (
    <div className="game-panel space-y-4 text-center">
      <div className="text-xs font-black uppercase tracking-[0.12em] text-[color:var(--warn)]">Нет доступа</div>
      <h2 className="text-lg font-black text-[color:var(--ink)]">Раздел «{pageLabel}» недоступен</h2>
      <p className="text-sm text-[color:var(--ink-muted)]">У роли «{roleLabel(role)}» нет прав на этот экран.</p>
      <Link to={home} className="game-button inline-flex min-h-[48px] items-center justify-center px-6">
        На главный экран
      </Link>
    </div>
  );
}
