import { useMemo } from "react";

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
        <div className="text-xs font-black uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">Установка без магазина приложений</div>
        <h2 className="text-xl font-black text-[color:var(--ink)]">Два телефона: пилот и клуб</h2>
        <p className="text-sm text-[color:var(--ink-muted)]">
          Откройте ссылку на телефоне, подключённом к сети клуба, войдите по коду и добавьте ярлык на главный экран.
        </p>
      </section>

      <section className="game-panel space-y-3">
        <div className="text-sm font-bold text-[color:var(--ink)]">Ссылки для закладок</div>
        <InstallLink label="Пилот" url={pilotUrl} />
        <InstallLink label="Клуб" url={ownerUrl} />
      </section>

      {platform === "ios" ? (
        <section className="game-panel space-y-2 text-sm text-[color:var(--ink-muted)]">
          <div className="font-bold text-[color:var(--ink)]">Айфон и айпад</div>
          <ol className="list-decimal space-y-2 pl-5">
            <li>Откройте ссылку в браузере Safari, а не во встроенном браузере мессенджера.</li>
            <li>Войдите по коду как обычно.</li>
            <li>Нажмите «Поделиться» → «На экран „Домой“».</li>
            <li>Запускайте MyWave Club с главного экрана как отдельное приложение.</li>
          </ol>
        </section>
      ) : null}

      {platform === "android" ? (
        <section className="game-panel space-y-2 text-sm text-[color:var(--ink-muted)]">
          <div className="font-bold text-[color:var(--ink)]">Андроид</div>
          <ol className="list-decimal space-y-2 pl-5">
            <li>Откройте ссылку в браузере Chrome.</li>
            <li>Войдите по коду.</li>
            <li>Меню браузера → «Установить приложение» или «Добавить на главный экран».</li>
          </ol>
        </section>
      ) : null}

      {platform === "desktop" ? (
        <section className="game-panel space-y-2 text-sm text-[color:var(--ink-muted)]">
          <div className="font-bold text-[color:var(--ink)]">С компьютера</div>
          <p>
            Откройте эту страницу на телефоне: адрес для сети клуба подскажет администратор. Ссылки выше подходят для закладок.
          </p>
        </section>
      ) : null}
    </div>
  );
}

function InstallLink({ label, url }: { label: string; url: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--panel-solid)] p-3">
      <div className="text-xs uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">{label}</div>
      <a href={url} className="mt-1 block break-all text-sm font-bold text-[color:var(--accent)] underline">
        {url}
      </a>
    </div>
  );
}
