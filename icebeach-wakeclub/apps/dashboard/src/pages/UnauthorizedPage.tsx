import { Link } from "react-router-dom";

import { getDefaultRouteForRole, useAuth } from "../auth/session";

export function UnauthorizedPage(): JSX.Element {
  const { session, signOut, clearIssue } = useAuth();
  const home = session ? getDefaultRouteForRole(session.role) : "/login";

  return (
    <div className="flex min-h-screen items-center justify-center p-6 text-slate-100">
      <div className="game-panel w-full max-w-md space-y-4">
        <h1 className="game-heading">Нет доступа</h1>
        <p className="game-subheading">
          {session
            ? `Роль «${session.role}» не может открыть этот раздел. Войдите под другим сотрудником или вернитесь на доступный экран.`
            : "У этой роли нет прав на страницу. Войдите заново."}
        </p>
        <div className="flex flex-col gap-3 sm:flex-row">
          <Link to={home} className="game-button flex-1" onClick={() => clearIssue()}>
            На доступный экран
          </Link>
          <button
            type="button"
            className="game-button-secondary flex-1"
            onClick={() => {
              void signOut();
            }}
          >
            Сменить сотрудника
          </button>
        </div>
      </div>
    </div>
  );
}
