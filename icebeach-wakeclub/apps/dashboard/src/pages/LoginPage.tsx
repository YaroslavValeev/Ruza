import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";

import { getDefaultRouteForRole, useAuth } from "../auth/session";
import { getApiBaseUrl } from "../api/client";

export function LoginPage(): JSX.Element {
  const navigate = useNavigate();
  const { requestCode, verifyCode } = useAuth();
  const [step, setStep] = useState<"request" | "verify">("request");
  const [staffUserId, setStaffUserId] = useState("");
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [debugCode, setDebugCode] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const onRequestCode = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const response = await requestCode(staffUserId.trim(), phone.trim());
      setDebugCode(response.debug_code ?? null);
      setMessage(`Код подготовлен. Канал доставки: ${response.delivery_channel}.`);
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
      const session = await verifyCode(staffUserId.trim(), code.trim());
      navigate(getDefaultRouteForRole(session.role), { replace: true });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-950 p-6 text-slate-100">
      <form className="w-full max-w-sm rounded-xl border border-slate-800 bg-slate-900 p-6 shadow-xl" onSubmit={step === "request" ? onRequestCode : onVerifyCode}>
        <h1 className="mb-1 text-xl font-semibold">Вход в Dashboard</h1>
        <p className="mb-4 text-sm text-slate-400">
          Сначала подтвердите `staff_user_id` и телефон, затем введите одноразовый код.
        </p>

        <label className="mb-2 block text-sm">staff_user_id</label>
        <input
          value={staffUserId}
          onChange={(e) => setStaffUserId(e.target.value)}
          className="mb-4 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 outline-none focus:border-blue-500"
          placeholder="staff_001"
          required
          disabled={step === "verify"}
        />

        <label className="mb-2 block text-sm">Телефон</label>
        <input
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          className="mb-4 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 outline-none focus:border-blue-500"
          placeholder="+79990000001"
          required
          disabled={step === "verify"}
        />

        {step === "verify" ? (
          <>
            <label className="mb-2 block text-sm">Одноразовый код</label>
            <input
              value={code}
              onChange={(e) => setCode(e.target.value)}
              className="mb-4 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 outline-none focus:border-blue-500"
              placeholder="123456"
              required
            />
          </>
        ) : null}

        {message ? <p className="mb-4 rounded bg-emerald-900/40 p-2 text-sm text-emerald-200">{message}</p> : null}
        {debugCode ? <p className="mb-4 rounded bg-amber-900/40 p-2 text-sm text-amber-200">DEV code: {debugCode}</p> : null}
        {error ? <p className="mb-4 rounded bg-red-900/50 p-2 text-sm text-red-200">{error}</p> : null}

        <button
          type="submit"
          disabled={loading}
          className="w-full rounded bg-blue-600 px-3 py-2 font-medium hover:bg-blue-500 disabled:opacity-70"
        >
          {loading ? "Ждём..." : step === "request" ? "Получить код" : "Войти"}
        </button>

        {step === "verify" ? (
          <button
            type="button"
            className="mt-3 w-full rounded border border-slate-700 px-3 py-2 text-sm text-slate-300 hover:bg-slate-800"
            onClick={() => {
              setStep("request");
              setCode("");
              setDebugCode(null);
              setMessage(null);
              setError(null);
            }}
          >
            Изменить staff_user_id / телефон
          </button>
        ) : null}
        <p className="mt-4 text-xs text-slate-500">API: {getApiBaseUrl()}</p>
      </form>
    </div>
  );
}