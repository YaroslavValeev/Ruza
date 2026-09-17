import { Link, Outlet, useLocation } from "react-router-dom";

import { useAuth, getMobileRouteForRole } from "../auth/session";
import { ApiHealthBadge } from "../components/ApiHealthBadge";
import { StaffRole, StaffSession } from "../types";
import { canAccessMobilePath } from "../utils/routes";

type MobileShellProps = {
  session: StaffSession;
};

function getMobileTitle(pathname: string): { title: string; subtitle?: string } {
  if (pathname.startsWith("/m/owner")) {
    return { title: "Owner", subtitle: "KPI и быстрый check-in" };
  }
  if (pathname.startsWith("/m/install")) {
    return { title: "Установка", subtitle: "Без App Store / Google Play" };
  }
  return { title: "Пилот", subtitle: "Очередь заездов на смене" };
}

function getMobileNavItems(role: StaffRole): Array<{ to: string; label: string }> {
  const items: Array<{ to: string; label: string }> = [];
  if (role === "admin" || role === "operator" || role === "pilot") {
    items.push({ to: "/m/pilot", label: "Пилот" });
  }
  if (role === "admin" || role === "operator") {
    items.push({ to: "/m/owner", label: "Owner" });
  }
  items.push({ to: "/m/install", label: "Установка" });
  return items;
}

export function MobileShell({ session }: MobileShellProps): JSX.Element {
  const { signOut } = useAuth();
  const location = useLocation();
  const { title, subtitle } = getMobileTitle(location.pathname);
  const navItems = getMobileNavItems(session.role);
  const homeRoute = getMobileRouteForRole(session.role);
  const hasAccess = canAccessMobilePath(session.role, location.pathname);

  return (
    <div className="mobile-shell flex min-h-[100dvh] flex-col bg-slate-950 text-slate-100">
      <header className="mobile-header sticky top-0 z-20 border-b border-slate-800/80 bg-slate-950/95 px-4 pb-3 pt-[max(0.75rem,env(safe-area-inset-top))] backdrop-blur">
        <div className="flex items-start justify-between gap-3">
          <Link to={homeRoute} className="block">
            <div className="text-[11px] font-black uppercase tracking-[0.14em] text-cyan-200/70">Ice Beach</div>
            <h1 className="mt-1 text-xl font-black text-white">{title}</h1>
            {subtitle ? <p className="mt-1 text-sm text-slate-400">{subtitle}</p> : null}
          </Link>
          <div className="flex flex-col items-end gap-2">
            <ApiHealthBadge compact />
            <button
              type="button"
              className="min-h-[44px] rounded-xl border border-slate-700 px-4 py-2 text-sm font-bold text-slate-300"
              onClick={() => void signOut()}
            >
              Выйти
            </button>
          </div>
        </div>
        <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-400">
          <span className="rounded-full bg-slate-900 px-2 py-1">{session.full_name}</span>
          <span className="rounded-full bg-slate-900 px-2 py-1">{session.role}</span>
          {session.boat_id ? <span className="rounded-full bg-slate-900 px-2 py-1">Лодка {session.boat_id}</span> : null}
        </div>
        {!hasAccess ? (
          <div className="mt-3 rounded-xl border border-amber-400/30 bg-amber-950/30 px-3 py-2 text-xs text-amber-100">
            Нет прав на этот раздел — используйте доступные вкладки ниже.
          </div>
        ) : null}
      </header>

      <main className="mobile-main flex-1 overflow-y-auto px-4 py-4 pb-[max(5.5rem,env(safe-area-inset-bottom))]">
        <Outlet />
      </main>

      <nav className="mobile-nav fixed inset-x-0 bottom-0 z-20 border-t border-slate-800/80 bg-slate-950/95 px-4 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-2 backdrop-blur">
        <div className={`grid gap-2 ${navItems.length === 3 ? "grid-cols-3" : navItems.length === 2 ? "grid-cols-2" : "grid-cols-1"}`}>
          {navItems.map((item) => (
            <MobileNavLink key={item.to} to={item.to} label={item.label} active={location.pathname.startsWith(item.to)} />
          ))}
        </div>
      </nav>
    </div>
  );
}

function MobileNavLink({ to, label, active }: { to: string; label: string; active: boolean }): JSX.Element {
  return (
    <Link
      to={to}
      className={`flex min-h-[48px] items-center justify-center rounded-2xl border px-2 text-center text-sm font-bold active:scale-[0.98] ${
        active ? "border-cyan-400/40 bg-cyan-950/40 text-cyan-100" : "border-slate-800 bg-slate-900/80 text-slate-200"
      }`}
    >
      {label}
    </Link>
  );
}
