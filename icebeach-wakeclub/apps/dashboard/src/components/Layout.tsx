import { Link, NavLink, useLocation, useNavigate } from "react-router-dom";

import { ApiHealthBadge } from "./ApiHealthBadge";
import { LiveShiftStrip } from "./shift-timer/LiveShiftStrip";
import { BUILD_STAMP } from "../constants/build";
import { getDefaultRouteForRole, useAuth } from "../auth/session";
import { roleLabel } from "../lib/labels";
import { StaffRole } from "../types";

/** Живая смена нужна там, где идёт работа с заездами; на аналитике и маркетинге она лишняя. */
const LIVE_STRIP_PATHS = ["/shift", "/bookings", "/pilot"];
const LIVE_STRIP_ROLES: StaffRole[] = ["admin", "operator", "pilot", "coach"];

export function Layout({ children }: { children: React.ReactNode }): JSX.Element {
  const navigate = useNavigate();
  const location = useLocation();
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
    { label: "Инвентарь", to: "/inventory", roles: ["admin"] as StaffRole[] },
  ].filter((item) => item.roles.includes(session.role));

  const logout = async () => {
    await signOut();
    navigate("/login", { replace: true });
  };

  return (
    <div className="relative min-h-full" style={{ color: "var(--ink)" }}>
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -left-24 top-0 h-64 w-64 rounded-full bg-teal-700/10 blur-3xl" />
        <div className="absolute right-0 top-24 h-72 w-72 rounded-full bg-amber-700/8 blur-3xl" />
      </div>

      <header className="relative z-10 border-b border-stone-400/35 bg-[rgba(230,225,214,0.78)] backdrop-blur-xl">
        <div className="mx-auto max-w-6xl px-4 py-4 sm:px-6">
          <div className="game-panel flex flex-col gap-4 sm:gap-5">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <Link
                  to={homeRoute}
                  className="inline-block text-2xl font-black uppercase tracking-[0.12em] sm:text-3xl"
                  style={{ color: "var(--ink)" }}
                >
                  MyWave Club
                </Link>
                <div className="mt-2 flex flex-wrap gap-2 text-xs sm:text-sm">
                  <span className="game-chip">Управление сменой</span>
                  <span className="game-chip">Сезон: 01.06–01.10</span>
                  <span className="game-chip">Часы работы: 07:00–22:00</span>
                  <span className="sm:hidden">
                    <ApiHealthBadge compact />
                  </span>
                </div>
              </div>

              <div className="hidden sm:block lg:min-w-[320px]">
                <ApiHealthBadge />
              </div>
            </div>

            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <nav aria-label="Разделы" className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1 sm:mx-0 sm:flex-wrap sm:gap-3 sm:overflow-visible sm:px-0 sm:pb-0">
                {navItems.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    className={({ isActive }) => `game-tab shrink-0 whitespace-nowrap ${isActive ? "game-tab-active" : ""}`}
                  >
                    {item.label}
                  </NavLink>
                ))}
              </nav>

              <div className="flex items-center gap-3">
                <div className="min-w-0 flex-1 text-left sm:text-right">
                  <div className="truncate text-sm font-black" style={{ color: "var(--ink)" }}>
                    {session.full_name}
                  </div>
                  <span className="game-chip mt-1 max-w-full truncate">{roleLabel(session.role)}</span>
                </div>
                <button className="game-button-secondary shrink-0 px-4" onClick={logout}>
                  Выйти
                </button>
              </div>
            </div>
          </div>
        </div>
      </header>

      {LIVE_STRIP_ROLES.includes(session.role) && LIVE_STRIP_PATHS.some((path) => location.pathname.startsWith(path)) ? (
        <div className="relative z-10 mx-auto max-w-6xl px-4 sm:px-6">
          <LiveShiftStrip session={session} />
        </div>
      ) : null}

      <main className="relative z-10 mx-auto max-w-6xl px-4 py-5 pb-16 sm:px-6 sm:py-6 sm:pb-20">{children}</main>
    </div>
  );
}
