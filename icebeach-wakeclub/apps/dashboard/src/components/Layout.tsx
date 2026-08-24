import { Link, NavLink, useNavigate } from "react-router-dom";

import { ApiHealthBadge } from "./ApiHealthBadge";
import { BUILD_STAMP } from "../constants/build";
import { getDefaultRouteForRole, useAuth } from "../auth/session";
import { StaffRole } from "../types";

const ROLE_LABELS: Record<string, string> = {
  admin: "Админ",
  operator: "Оператор",
  pilot: "Пилот",
  coach: "Тренер",
  marketing_read: "Маркетинг",
};

export function Layout({ children }: { children: React.ReactNode }): JSX.Element {
  const navigate = useNavigate();
  const { session, signOut } = useAuth();

  if (!session) {
    return <>{children}</>;
  }

  const homeRoute = getDefaultRouteForRole(session.role);
  const navItems = [
    { label: "Смена", to: "/shift", roles: ["admin", "operator", "coach"] as StaffRole[] },
    { label: "Аналитика", to: "/kpi", roles: ["admin", "operator", "pilot", "coach", "marketing_read"] as StaffRole[] },
    { label: "Брони", to: "/bookings", roles: ["admin", "operator", "coach"] as StaffRole[] },
    { label: "Маркетинг", to: "/marketing", roles: ["admin", "operator", "marketing_read"] as StaffRole[] },
    { label: "Пилот", to: "/pilot", roles: ["admin", "operator", "pilot"] as StaffRole[] },
  ].filter((item) => item.roles.includes(session.role));

  const logout = async () => {
    await signOut();
    navigate("/login", { replace: true });
  };

  return (
    <div className="relative min-h-screen overflow-hidden text-slate-100">
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -left-24 top-0 h-64 w-64 rounded-full bg-cyan-400/10 blur-3xl" />
        <div className="absolute right-0 top-24 h-72 w-72 rounded-full bg-orange-400/10 blur-3xl" />
        <div className="absolute bottom-0 left-1/4 h-80 w-80 rounded-full bg-blue-500/10 blur-3xl" />
      </div>

      <header className="relative z-10 border-b border-cyan-200/10 bg-slate-950/35 backdrop-blur-xl">
        <div className="mx-auto max-w-6xl px-4 py-4 sm:px-6">
          <div className="game-panel flex flex-col gap-4 sm:gap-5">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <Link to={homeRoute} className="inline-block text-2xl font-black uppercase tracking-[0.12em] text-white sm:text-3xl">
                  Ice Beach Club
                </Link>
                <div className="mt-2 flex flex-wrap gap-2 text-xs sm:text-sm">
                  <span className="game-chip text-cyan-100">Режим: Управление сменой</span>
                  <span className="game-chip text-orange-100">Сезон 01.06 - 01.10</span>
                  <span className="game-chip text-cyan-100">07:00 - 22:00</span>
                </div>
              </div>

              <div className="lg:min-w-[320px]">
                <ApiHealthBadge />
              </div>
            </div>

            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <nav className="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap sm:gap-3">
                {navItems.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    className={({ isActive }) => `game-tab ${isActive ? "game-tab-active" : ""}`}
                  >
                    {item.label}
                  </NavLink>
                ))}
              </nav>

              <div className="grid gap-3 sm:grid-cols-[1fr_auto_auto] sm:items-center">
                <div className="text-left sm:text-right">
                  <div className="text-sm font-black uppercase tracking-[0.08em] text-white">{session.full_name}</div>
                  <div className="text-xs text-cyan-100/70">Клуб: {session.club_id}</div>
                </div>
                <span className="game-chip justify-center text-cyan-100">{ROLE_LABELS[session.role] || session.role}</span>
                <button className="game-button-secondary px-4" onClick={logout}>
                  Выйти
                </button>
              </div>
            </div>
          </div>
        </div>
      </header>

      <main className="relative z-10 mx-auto max-w-6xl px-4 py-5 sm:px-6 sm:py-6">{children}</main>
    </div>
  );
}
