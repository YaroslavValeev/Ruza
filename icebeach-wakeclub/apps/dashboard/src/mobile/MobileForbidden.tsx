import { Link } from "react-router-dom";

import { getMobileRouteForRole } from "../auth/session";
import { StaffRole } from "../types";

type MobileForbiddenProps = {
  role: StaffRole;
  pageLabel: string;
};

export function MobileForbidden({ role, pageLabel }: MobileForbiddenProps): JSX.Element {
  const home = getMobileRouteForRole(role);

  return (
    <div className="game-panel space-y-4 text-center">
      <div className="text-xs font-black uppercase tracking-[0.12em] text-amber-200/80">Нет доступа</div>
      <h2 className="text-lg font-black text-white">Раздел «{pageLabel}» недоступен</h2>
      <p className="text-sm text-slate-400">У вашей роли ({role}) нет прав на этот экран.</p>
      <Link to={home} className="game-button inline-flex min-h-[48px] items-center justify-center px-6">
        На главный экран
      </Link>
    </div>
  );
}
