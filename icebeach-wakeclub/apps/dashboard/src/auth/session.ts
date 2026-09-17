import { createContext, createElement, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { getCurrentSession, isApiError, logout, requestLoginCode, verifyLoginCode } from "../api/client";
import { LoginCodeResponse, StaffRole, StaffSession } from "../types";
import { subscribeAuthFailure } from "./auth-events";

export type AuthStatus = "loading" | "anonymous" | "authenticated";
export type AuthIssue = "forbidden" | null;

type AuthContextValue = {
  session: StaffSession | null;
  status: AuthStatus;
  issue: AuthIssue;
  requestCode: (staffUserId: string, phone: string) => Promise<LoginCodeResponse>;
  verifyCode: (staffUserId: string, code: string, phone?: string) => Promise<StaffSession>;
  signOut: () => Promise<void>;
  refreshSession: () => Promise<void>;
  clearIssue: () => void;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

function normalizeSession(session: StaffSession): StaffSession {
  return {
    ...session,
    token: session.token?.trim() || undefined,
  };
}

export function getDefaultRouteForRole(role: StaffRole): string {
  switch (role) {
    case "pilot":
      return "/pilot";
    case "admin":
    case "operator":
    case "coach":
      return "/bookings";
    default:
      return "/kpi";
  }
}

export function getMobileRouteForRole(role: StaffRole): string {
  switch (role) {
    case "pilot":
      return "/m/pilot";
    case "admin":
    case "operator":
      return "/m/owner";
    default:
      return "/m/install";
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }): JSX.Element {
  const [session, setSession] = useState<StaffSession | null>(null);
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [issue, setIssue] = useState<AuthIssue>(null);

  const applySession = useCallback((nextSession: StaffSession | null) => {
    setSession(nextSession ? normalizeSession(nextSession) : null);
    setStatus(nextSession ? "authenticated" : "anonymous");
    if (nextSession) {
      setIssue(null);
    }
  }, []);

  const refreshSession = useCallback(async () => {
    setStatus("loading");
    try {
      const current = normalizeSession(await getCurrentSession());
      applySession(current);
    } catch (error) {
      if (isApiError(error, 403)) {
        setSession(null);
        setStatus("anonymous");
        setIssue("forbidden");
        return;
      }

      setSession(null);
      setStatus("anonymous");
      if (isApiError(error, 401)) {
        setIssue(null);
      }
    }
  }, [applySession]);

  const requestCode = useCallback(async (staffUserId: string, phone: string) => {
    return requestLoginCode(staffUserId, phone);
  }, []);

  const verifyCode = useCallback(
    async (staffUserId: string, code: string, phone?: string) => {
      const response = normalizeSession(await verifyLoginCode(staffUserId, code, phone));
      let nextSession = response;

      try {
        nextSession = normalizeSession(await getCurrentSession());
      } catch {
        nextSession = response;
      }

      applySession(nextSession);
      return nextSession;
    },
    [applySession],
  );

  const signOut = useCallback(async () => {
    setSession(null);
    setStatus("anonymous");
    setIssue(null);
    void logout();
  }, []);

  const clearIssue = useCallback(() => {
    setIssue(null);
  }, []);

  useEffect(() => {
    void refreshSession();
  }, [refreshSession]);

  useEffect(() => {
    return subscribeAuthFailure((statusCode) => {
      if (statusCode === 401) {
        setSession(null);
        setStatus("anonymous");
        setIssue(null);
        return;
      }

      setIssue("forbidden");
    });
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ session, status, issue, requestCode, verifyCode, signOut, refreshSession, clearIssue }),
    [session, status, issue, requestCode, verifyCode, signOut, refreshSession, clearIssue],
  );

  return createElement(AuthContext.Provider, { value }, children);
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) {
    throw new Error("useAuth must be used within AuthProvider");
  }

  return value;
}
