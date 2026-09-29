import { Link } from "react-router-dom";

import { getDefaultRouteForRole, getMobileRouteForRole, useAuth } from "../auth/session";
import { isMobilePreferred } from "../utils/routes";

export function UnauthorizedPage(): JSX.Element {
  const { session, signOut, clearIssue } = useAuth();
  const mobile = isMobilePreferred();
  const home = session
    ? mobile
      ? getMobileRouteForRole(session.role)
      : getDefaultRouteForRole(session.role)
    : "/login";

  return (
    <div className="flex min-h-[100dvh] items-center justify-center px-4 py-8">
      <div className="game-panel w-full max-w-md space-y-4 text-center">
        <div className="text-xs font-black uppercase tracking-[0.14em] text-red-200/80">403</div>
        <h1 className="text-xl font-black text-white">Доступ запрещён</h1>
        <p className="text-sm text-slate-400">У вашей роли нет прав на эту страницу.</p>
        <div className="flex flex-col gap-2">
          <Link to={home} onClick={clearIssue} className="game-button min-h-[48px]">
            На доступный экран
          </Link>
          {mobile ? (
            <Link to="/m/install" className="game-button-secondary min-h-[48px]">
              Установка на телефон
            </Link>
          ) : null}
          <button type="button" className="game-button-secondary min-h-[48px]" onClick={() => void signOut()}>
            Войти другим сотрудником
          </button>
        </div>
      </div>
    </div>
  );
}
