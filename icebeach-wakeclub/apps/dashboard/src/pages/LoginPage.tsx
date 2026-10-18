import { FormEvent, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "../auth/session";
import { ApiHealthBadge } from "../components/ApiHealthBadge";
import { resolvePostLoginRoute } from "../utils/routes";

function formatSeconds(total: number): string {
  if (total >= 60 && total % 60 === 0) {
    const minutes = total / 60;
    const mod10 = minutes % 10;
    const mod100 = minutes % 100;
    const word = mod10 === 1 && mod100 !== 11 ? "минуту" : mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14) ? "минуты" : "минут";
    return `${minutes} ${word}`;
  }
  return `${total} сек.`;
}

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
      setMessage("Код отправлен.");
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
      const next = new URLSearchParams(window.location.search).get("next");
      navigate(resolvePostLoginRoute(session.role, next), { replace: true });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center p-6 text-[color:var(--ink)]">
      <form
        className="game-panel w-full max-w-md space-y-4"
        onSubmit={step === "request" ? onRequestCode : onVerifyCode}
      >
        <div>
          <p className="text-xs font-black uppercase tracking-[0.12em] text-[color:var(--accent)]">MyWave Club</p>
          <h1 className="game-heading mt-1">Вход в смену</h1>
          <p className="game-subheading mt-2">
            Введите телефон сотрудника. Код подтверждения действует несколько минут.
          </p>
        </div>

        <ApiHealthBadge />

        {import.meta.env.DEV ? (
          <div className="game-card space-y-2 text-sm">
            <p className="text-xs font-black uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">Локальная демоверсия</p>
            <div className="flex flex-wrap gap-2">
              {[
                { phone: "+79990000000", label: "Администратор" },
                { phone: "+79990000001", label: "Оператор" },
                { phone: "+79990000002", label: "Пилот" },
                { phone: "+79990000003", label: "Тренер" },
                { phone: "+79990000004", label: "Маркетинг" },
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
            <p className="text-xs text-[color:var(--ink-muted)]">Выберите роль и нажмите «Получить код» — тестовый код появится на этой форме.</p>
          </div>
        ) : null}

        <div>
          <label htmlFor="login-phone" className="mb-2 block text-sm font-bold text-[color:var(--accent)]">
            Телефон
          </label>
          <input
            id="login-phone"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            className="game-input"
            placeholder="+7 999 000-00-01"
            type="tel"
            inputMode="tel"
            autoComplete="tel"
            required
            disabled={step === "verify"}
          />
        </div>

        <details className="game-card">
          <summary className="flex min-h-11 cursor-pointer items-center text-sm font-bold text-[color:var(--ink)]">На один телефон несколько сотрудников?</summary>
          <label htmlFor="login-staff-id" className="mb-2 mt-3 block text-sm font-bold text-[color:var(--accent)]">
            Код сотрудника
          </label>
          <input
            id="login-staff-id"
            value={staffUserId}
            onChange={(e) => setStaffUserId(e.target.value)}
            className="game-input"
            placeholder="Выдаёт администратор"
            autoComplete="username"
            disabled={step === "verify"}
          />
        </details>

        {step === "verify" ? (
          <>
            {resolvedName ? (
              <p className="text-sm text-[color:var(--ink-muted)]">
                Сотрудник: <span className="font-bold text-[color:var(--ink)]">{resolvedName}</span>
              </p>
            ) : null}
            <label htmlFor="login-code" className="mb-2 block text-sm font-bold text-[color:var(--accent)]">
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
            {expiresIn ? <p className="text-xs text-[color:var(--ink-muted)]">Код действует {formatSeconds(expiresIn)}.</p> : null}
          </>
        ) : null}

        {message ? (
          <p role="status" className="rounded-2xl border border-emerald-600/25 bg-emerald-50 p-3 text-sm text-emerald-900">
            {message}
          </p>
        ) : null}
        {debugCode ? (
          <p role="status" className="rounded-2xl border border-amber-600/25 bg-amber-50 p-3 text-sm text-amber-900">
            Тестовый код: <span className="font-black tracking-[0.12em]">{debugCode}</span>
          </p>
        ) : null}
        {error ? (
          <p role="alert" className="rounded-2xl border border-red-600/25 bg-red-50 p-3 text-sm text-red-900">
            {error}
          </p>
        ) : null}

        <button type="submit" disabled={loading} className="game-button w-full">
          {loading ? "Подождите…" : step === "request" ? "Получить код" : "Войти"}
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
        <p className="text-xs text-[color:var(--ink-muted)]">
          <Link to="/m/install" className="inline-flex min-h-11 items-center font-semibold text-[color:var(--accent)] underline">
            Как установить на телефон
          </Link>
        </p>
      </form>
    </div>
  );
}
