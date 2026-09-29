import { useMemo } from "react";

import { getApiBaseUrl } from "../api/client";

function detectPlatform(): "ios" | "android" | "desktop" {
  const ua = navigator.userAgent.toLowerCase();
  if (/iphone|ipad|ipod/.test(ua)) return "ios";
  if (/android/.test(ua)) return "android";
  return "desktop";
}

export function MobileInstallPage(): JSX.Element {
  const platform = useMemo(() => detectPlatform(), []);
  const origin = typeof window !== "undefined" ? window.location.origin : "";
  const pilotUrl = `${origin}/m/pilot`;
  const ownerUrl = `${origin}/m/owner`;

  return (
    <div className="space-y-4">
      <section className="game-panel space-y-3">
        <div className="text-xs font-black uppercase tracking-[0.12em] text-cyan-100/70">Установка без App Store</div>
        <h2 className="text-xl font-black text-white">2 телефона: пилот и owner</h2>
        <p className="text-sm text-slate-300">
          Откройте ссылки ниже в той же Wi‑Fi сети, где запущен Docker на вашем ПК. После входа добавьте ярлык на домашний экран.
        </p>
      </section>

      <section className="game-panel space-y-3">
        <div className="text-sm font-bold text-white">Ссылки для закладок</div>
        <InstallLink label="Пилот" url={pilotUrl} />
        <InstallLink label="Owner" url={ownerUrl} />
        <p className="text-xs text-slate-500">API: {getApiBaseUrl()}</p>
      </section>

      {platform === "ios" ? (
        <section className="game-panel space-y-2 text-sm text-slate-300">
          <div className="font-bold text-white">iPhone / iPad</div>
          <ol className="list-decimal space-y-2 pl-5">
            <li>Откройте ссылку в Safari (не во встроенном браузере Telegram).</li>
            <li>Войдите по коду как обычно.</li>
            <li>Нажмите «Поделиться» → «На экран Домой».</li>
            <li>Запускайте как отдельное приложение Ice Beach.</li>
          </ol>
        </section>
      ) : null}

      {platform === "android" ? (
        <section className="game-panel space-y-2 text-sm text-slate-300">
          <div className="font-bold text-white">Android</div>
          <ol className="list-decimal space-y-2 pl-5">
            <li>Откройте ссылку в Chrome.</li>
            <li>Войдите по коду.</li>
            <li>Меню Chrome → «Установить приложение» или «Добавить на главный экран».</li>
            <li>Опционально: соберите debug APK через `scripts/build-android-apk.ps1`.</li>
          </ol>
        </section>
      ) : null}

      {platform === "desktop" ? (
        <section className="game-panel space-y-2 text-sm text-slate-300">
          <div className="font-bold text-white">С ПК</div>
          <p>
            Запустите `scripts/mobile-lan-url.ps1` — скрипт покажет адрес вида `http://192.168.x.x:5173/m/pilot` для телефона в той же сети.
          </p>
        </section>
      ) : null}
    </div>
  );
}

function InstallLink({ label, url }: { label: string; url: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-3">
      <div className="text-xs uppercase tracking-[0.12em] text-cyan-100/60">{label}</div>
      <a href={url} className="mt-1 block break-all text-sm font-bold text-cyan-200 underline">
        {url}
      </a>
    </div>
  );
}
