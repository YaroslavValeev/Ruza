import { Navigate, Route, Routes } from "react-router-dom";

import { useAuth, getDefaultRouteForRole } from "../auth/session";
import { Layout } from "../components/Layout";
import { BookingsPage } from "../pages/BookingsPage";
import { KpiPage } from "../pages/KpiPage";
import { LoginPage } from "../pages/LoginPage";
import { MarketingPage } from "../pages/MarketingPage";
import { PilotPage } from "../pages/PilotPage";
import { UnauthorizedPage } from "../pages/UnauthorizedPage";
import { StaffRole } from "../types";

export function AppRouter(): JSX.Element {
  const { session, status, issue } = useAuth();

  if (status === "loading") {
    return <AppLoadingScreen />;
  }

  if (status === "anonymous") {
    return (
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/unauthorized" element={<UnauthorizedPage />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );
  }

  if (!session) {
    return <AppLoadingScreen />;
  }

  if (issue === "forbidden") {
    return (
      <Routes>
        <Route path="/unauthorized" element={<UnauthorizedPage />} />
        <Route path="*" element={<Navigate to="/unauthorized" replace />} />
      </Routes>
    );
  }

  const defaultRoute = getDefaultRouteForRole(session.role);

  return (
    <Layout>
      <Routes>
        <Route path="/login" element={<Navigate to={defaultRoute} replace />} />
        <Route
          path="/kpi"
          element={
            <RoleGuard allowed={["admin", "operator", "pilot", "coach", "marketing_read"]} role={session.role}>
              <KpiPage session={session} />
            </RoleGuard>
          }
        />
        <Route
          path="/bookings"
          element={
            <RoleGuard allowed={["admin", "operator", "coach"]} role={session.role}>
              <BookingsPage session={session} />
            </RoleGuard>
          }
        />
        <Route
          path="/marketing"
          element={
            <RoleGuard allowed={["admin", "operator", "marketing_read"]} role={session.role}>
              <MarketingPage session={session} />
            </RoleGuard>
          }
        />
        <Route
          path="/pilot"
          element={
            <RoleGuard allowed={["admin", "operator", "pilot"]} role={session.role}>
              <PilotPage session={session} />
            </RoleGuard>
          }
        />
        <Route path="/unauthorized" element={<UnauthorizedPage />} />
        <Route path="*" element={<Navigate to={defaultRoute} replace />} />
      </Routes>
    </Layout>
  );
}

type RoleGuardProps = {
  allowed: StaffRole[];
  role: StaffRole;
  children: JSX.Element;
};

function RoleGuard({ allowed, role, children }: RoleGuardProps): JSX.Element {
  if (!allowed.includes(role)) {
    return <Navigate to="/unauthorized" replace />;
  }

  return children;
}

function AppLoadingScreen(): JSX.Element {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-950 px-6 text-slate-100">
      <div className="rounded-xl border border-slate-800 bg-slate-900 px-6 py-4 text-sm text-slate-300 shadow-xl">
        Проверяем сессию...
      </div>
    </div>
  );
}
