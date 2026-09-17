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

export function resolvePostLoginRoute(role: StaffRole, nextPath: string | null): string {
  if (nextPath && nextPath.startsWith("/") && !nextPath.startsWith("//")) {
    return nextPath;
  }

  if (isMobilePreferred()) {
    return getMobileRouteForRole(role);
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
