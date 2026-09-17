import { FormEvent, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { getDefaultRouteForRole, useAuth } from "../auth/session";
import { getApiBaseUrl } from "../api/client";
import { ApiHealthBadge } from "../components/ApiHealthBadge";

export function LoginPage(): JSX.Element {
  const navigate = useNavigate();
  const { requestCode, verifyCode } = useAuth();
  const [step, setStep] = useState<"request" | "verify">("request");
  const [staffUserId, setStaffUserId] = useState("");
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [resolvedStaffId, setResolvedStaffId] = useState("");
  const [resolvedName, setResolvedName] = useState<string | null>(null);
  const [debugCode, setDebugCode] = useState<string | null>(null);
  const [expiresIn, setExpiresIn] = useState<number | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const codeInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (step === "verify") {
      codeInputRef.current?.focus();
    }
  }, [step]);

  const onRequestCode = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const response = await requestCode(staffUserId.trim(), phone.trim());
      setDebugCode(response.debug_code ?? null);
      setExpiresIn(response.expires_in_seconds);
      setResolvedStaffId(response.staff_user_id || staffUserId.trim());
      setResolvedName(response.full_name ?? null);
      setMessage(
        response.full_name
          ? `Код для ${response.full_name}. Действует ${response.expires_in_seconds} сек.`
          : `Код подготовлен. Действует ${response.expires_in_seconds} сек.`,
      );
      setStep("verify");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const onVerifyCode = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const session = await verifyCode(resolvedStaffId || staffUserId.trim(), code.trim(), phone.trim());
      navigate(getDefaultRouteForRole(session.role), { replace: true });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center p-6 text-slate-100">
      <form
        className="game-panel w-full max-w-md space-y-4"
        onSubmit={step === "request" ? onRequestCode : onVerifyCode}
      >
        <div>
          <p className="text-xs font-black uppercase tracking-[0.12em] text-cyan-100/70">Ice Beach Club</p>
          <h1 className="game-heading mt-1">Вход в смену</h1>
          <p className="game-subheading mt-2">
            Введите телефон сотрудника. Код подтверждения действует несколько минут.
          </p>
        </div>

        <ApiHealthBadge />

        {import.meta.env.DEV ? (
          <div className="game-card space-y-2 text-sm text-cyan-100/80">
            <p className="text-xs font-black uppercase tracking-[0.12em] text-cyan-100/60">Локальный demo</p>
            <div className="flex flex-wrap gap-2">
              {[
                { phone: "+79990000000", label: "Админ" },
                { phone: "+79990000001", label: "Оператор" },
                { phone: "+79990000002", label: "Пилот" },
              ].map((account) => (
                <button
                  key={account.phone}
                  type="button"
                  className="game-button-secondary px-3 text-xs"
                  onClick={() => {
                    setPhone(account.phone);
                    setStaffUserId("");
                    setStep("request");
                    setCode("");
                    setDebugCode(null);
                    setError(null);
                    setMessage(null);
                  }}
                >
                  {account.label}
                </button>
              ))}
            </div>
            <p className="text-xs text-slate-400">Нажмите роль, затем «Получить код». DEV-код появится на этой форме.</p>
          </div>
        ) : null}

        <div>
          <label htmlFor="login-phone" className="mb-2 block text-sm font-bold text-cyan-100/70">
            Телефон
          </label>
          <input
            id="login-phone"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            className="game-input"
            placeholder="+7 999 000 00 01"
            type="tel"
            inputMode="tel"
            autoComplete="tel"
            required
            disabled={step === "verify"}
          />
        </div>

        <details className="game-card">
          <summary className="cursor-pointer text-sm font-bold text-cyan-100/80">Если телефоны совпадают — укажите ID</summary>
          <label htmlFor="login-staff-id" className="mb-2 mt-3 block text-sm font-bold text-cyan-100/70">
            ID сотрудника
          </label>
          <input
            id="login-staff-id"
            value={staffUserId}
            onChange={(e) => setStaffUserId(e.target.value)}
            className="game-input"
            placeholder="staff_001"
            autoComplete="username"
            disabled={step === "verify"}
          />
        </details>

        {step === "verify" ? (
          <>
            {resolvedName ? <p className="text-sm text-cyan-100/80">Сотрудник: {resolvedName}</p> : null}
            <label htmlFor="login-code" className="mb-2 block text-sm font-bold text-cyan-100/70">
              Одноразовый код
            </label>
            <input
              id="login-code"
              ref={codeInputRef}
              value={code}
              onChange={(e) => setCode(e.target.value)}
              className="game-input"
              placeholder="123456"
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={8}
              required
            />
            {expiresIn ? <p className="text-xs text-slate-400">Код действует {expiresIn} секунд.</p> : null}
          </>
        ) : null}

        {message ? (
          <p role="status" className="rounded-2xl bg-emerald-900/40 p-3 text-sm text-emerald-200">
            {message}
          </p>
        ) : null}
        {debugCode ? (
          <p role="status" className="rounded-2xl bg-amber-900/40 p-3 text-sm text-amber-200">
            DEV-код: {debugCode}
          </p>
        ) : null}
        {error ? (
          <p role="alert" className="rounded-2xl bg-red-900/50 p-3 text-sm text-red-200">
            {error}
          </p>
        ) : null}

        <button type="submit" disabled={loading} className="game-button w-full">
          {loading ? "Ждём..." : step === "request" ? "Получить код" : "Войти"}
        </button>

        {step === "verify" ? (
          <button
            type="button"
            className="game-button-secondary w-full"
            onClick={() => {
              setStep("request");
              setCode("");
              setDebugCode(null);
              setMessage(null);
              setError(null);
              setResolvedName(null);
            }}
          >
            Изменить телефон
          </button>
        ) : null}
        <p className="text-xs text-slate-500">
          Сервер: {getApiBaseUrl()} ·{" "}
          <Link to="/m/install" className="text-cyan-300 underline">
            Установка на телефон
          </Link>
        </p>
      </form>
    </div>
  );
}
