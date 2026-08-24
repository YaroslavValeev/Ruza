import { FormEvent, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { getApiBaseUrl } from "../api/client";
import { useAuth } from "../auth/session";
import { ApiHealthBadge } from "../components/ApiHealthBadge";
import { resolvePostLoginRoute } from "../utils/routes";

export function LoginPage(): JSX.Element {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { requestCode, verifyCode } = useAuth();
  const [step, setStep] = useState<"request" | "verify">("request");
  const [staffUserId, setStaffUserId] = useState("");
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [debugCode, setDebugCode] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const [codeExpiresSec, setCodeExpiresSec] = useState<number | null>(null);

  const onRequestCode = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const response = await requestCode(staffUserId.trim(), phone.trim());
      const dev = response.debug_code ?? null;
      setDebugCode(dev);
      setCode(dev ?? "");
      setCodeExpiresSec(response.expires_in_seconds ?? 300);
      setMessage(`Код готов. Действует ${Math.round((response.expires_in_seconds ?? 300) / 60)} мин.`);
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
      const session = await verifyCode(staffUserId.trim(), code.replace(/\D/g, ""));
      navigate(resolvePostLoginRoute(session.role, searchParams.get("next")), { replace: true });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-[100dvh] items-center justify-center px-4 py-8">
      <form className="game-panel w-full max-w-md space-y-4" onSubmit={step === "request" ? onRequestCode : onVerifyCode}>
        <div>
          <div className="text-xs font-black uppercase tracking-[0.14em] text-cyan-200/70">Ice Beach Wake Club</div>
          <h1 className="game-heading mt-2">Вход</h1>
          <p className="game-subheading mt-2">staff_user_id + телефон + одноразовый код.</p>
        </div>

        <ApiHealthBadge />

        <label className="block text-sm font-bold text-cyan-100/70">staff_user_id</label>
        <input
          value={staffUserId}
          onChange={(e) => setStaffUserId(e.target.value)}
          className="game-input min-h-[48px]"
          placeholder="staff_001"
          required
          disabled={step === "verify"}
        />

        <label className="block text-sm font-bold text-cyan-100/70">Телефон</label>
        <input
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          className="game-input min-h-[48px]"
          placeholder="+79990000001"
          inputMode="tel"
          required
          disabled={step === "verify"}
        />

        {step === "verify" ? (
          <>
            <label className="block text-sm font-bold text-cyan-100/70">Код</label>
            <input
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
              className="game-input min-h-[52px] text-center text-2xl tracking-[0.35em]"
              placeholder="000000"
              inputMode="numeric"
              autoComplete="one-time-code"
              required
            />
            {codeExpiresSec ? (
              <p className="text-xs text-slate-400">Код действует ~{Math.max(1, Math.round(codeExpiresSec / 60))} мин. Если ошибка — нажмите «Новый код».</p>
            ) : null}
            {debugCode ? (
              <button
                type="button"
                className="game-button-secondary min-h-[48px] w-full"
                onClick={() => setCode(debugCode)}
              >
                Подставить DEV-код: {debugCode}
              </button>
            ) : null}
          </>
        ) : null}

        {message ? <div className="game-panel border-emerald-400/30 bg-emerald-950/30 text-sm text-emerald-50">{message}</div> : null}
        {debugCode ? <div className="game-panel border-amber-400/30 bg-amber-950/30 text-sm text-amber-50">DEV code: {debugCode}</div> : null}
        {error ? <div className="game-panel border-red-400/30 bg-red-950/30 text-sm text-red-50">{error}</div> : null}

        <button type="submit" disabled={loading} className="game-button min-h-[52px] w-full text-base">
          {loading ? "Ждём..." : step === "request" ? "Получить код" : "Войти"}
        </button>

        {step === "verify" ? (
          <>
            <button
              type="button"
              className="game-button-secondary min-h-[48px] w-full"
              disabled={loading}
              onClick={() => void onRequestCode({ preventDefault: () => undefined } as FormEvent)}
            >
              Новый код
            </button>
            <button
              type="button"
              className="game-button-secondary min-h-[48px] w-full"
              onClick={() => {
                setStep("request");
                setCode("");
                setDebugCode(null);
                setCodeExpiresSec(null);
                setMessage(null);
                setError(null);
              }}
            >
              Изменить staff_user_id / телефон
            </button>
          </>
        ) : null}

        <p className="text-xs text-slate-500">
          API: {getApiBaseUrl()} · <Link to="/m/install" className="text-cyan-300 underline">Установка на телефон</Link>
        </p>
      </form>
    </div>
  );
}
