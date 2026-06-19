export function UnauthorizedPage(): JSX.Element {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-950 p-6 text-slate-100">
      <div className="rounded-xl bg-slate-900 p-6">
        <h1 className="mb-2 text-xl font-semibold">Доступ запрещен</h1>
        <p className="text-sm text-slate-400">У вашей роли нет прав на эту страницу.</p>
      </div>
    </div>
  );
}
