import { getDefaultRouteForRole, getMobileRouteForRole } from "../auth/session";
import { StaffRole } from "../types";

export function isMobilePreferred(): boolean {
  if (typeof window === "undefined") {
    return false;
  }

  if (window.location.pathname.startsWith("/m")) {
    return true;
  }

  if (window.matchMedia("(max-width: 768px)").matches) {
    return true;
  }

  const ua = navigator.userAgent.toLowerCase();
  return /iphone|ipad|ipod|android/.test(ua);
}

function isNativeShell(): boolean {
  if (typeof window === "undefined") return false;
  try {
    const cap = (window as unknown as { Capacitor?: { isNativePlatform?: () => boolean } }).Capacitor;
    return Boolean(cap?.isNativePlatform?.());
  } catch {
    return false;
  }
}

/** Роли, у которых есть отдельный мобильный экран (/m/pilot, /m/owner). */
function hasMobileWorkspace(role: StaffRole): boolean {
  return role === "admin" || role === "operator" || role === "pilot";
}

/**
 * Куда вести после входа. Единая точка для LoginPage и AppRouter (маршрут /login у авторизованного),
 * чтобы редирект роутера не перебивал мобильный маршрут.
 */
export function resolvePostLoginRoute(role: StaffRole, nextPath: string | null): string {
  const safeNext = nextPath && nextPath.startsWith("/") && !nextPath.startsWith("//") && !nextPath.startsWith("/login") ? nextPath : null;
  const mobile = Boolean(safeNext?.startsWith("/m/")) || isMobilePreferred() || isNativeShell();

  if (mobile && hasMobileWorkspace(role)) {
    return safeNext?.startsWith("/m/") ? safeNext : getMobileRouteForRole(role);
  }

  if (safeNext && !safeNext.startsWith("/m/")) {
    return safeNext;
  }

  return getDefaultRouteForRole(role);
}

export function canAccessMobilePath(role: StaffRole, pathname: string): boolean {
  if (pathname.startsWith("/m/install")) {
    return true;
  }
  if (pathname.startsWith("/m/pilot")) {
    return role === "admin" || role === "operator" || role === "pilot";
  }
  if (pathname.startsWith("/m/owner")) {
    return role === "admin" || role === "operator";
  }
  return true;
}
