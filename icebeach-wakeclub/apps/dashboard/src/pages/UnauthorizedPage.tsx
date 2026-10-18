import { Link } from "react-router-dom";

import { useAuth } from "../auth/session";
import { isMobilePreferred, resolvePostLoginRoute } from "../utils/routes";

export function UnauthorizedPage(): JSX.Element {
  const { session, signOut, clearIssue } = useAuth();
  const mobile = isMobilePreferred();
  const home = session ? resolvePostLoginRoute(session.role, null) : "/login";

  return (
    <div className="flex min-h-[100dvh] items-center justify-center px-4 py-8">
      <div className="game-panel w-full max-w-md space-y-4 text-center">
        <div className="text-xs font-black uppercase tracking-[0.14em] text-[color:var(--danger)]">Ошибка 403</div>
        <h1 className="text-xl font-black text-[color:var(--ink)]">Доступ запрещён</h1>
        <p className="text-sm text-[color:var(--ink-muted)]">У вашей роли нет прав на эту страницу.</p>
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
