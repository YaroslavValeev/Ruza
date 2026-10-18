import { FormEvent, useEffect, useMemo, useState } from "react";

import { createBoard, createWetsuit, getInventoryBoards, getInventoryWetsuits, updateBoard, updateWetsuit } from "../api/client";
import { BoardIcon, WetsuitIcon } from "../components/equipment/icons";
import { boardKindLabel, genderLabel, invalidateInventoryCache } from "../lib/equipment";
import { rideTypeLabel } from "../lib/labels";
import type { BoardRef, RideType, StaffSession, WetsuitGender, WetsuitRef, WetsuitSize } from "../types";

type Tab = "boards" | "wetsuits";
type Toast = { type: "success" | "error"; message: string } | null;

const KINDS: RideType[] = ["wakeboard", "surf", "skim"];
const SIZES: WetsuitSize[] = ["XS", "S", "M", "L", "XL", "XXL"];
const GENDERS: Array<{ value: WetsuitGender; label: string }> = [
  { value: "female", label: "Женский" },
  { value: "male", label: "Мужской" },
];

type BoardDraft = { number: string; name: string; kind: RideType; length: string };
type WetsuitDraft = { number: string; size: WetsuitSize; gender: WetsuitGender };

const EMPTY_BOARD: BoardDraft = { number: "", name: "", kind: "wakeboard", length: "" };
const EMPTY_WETSUIT: WetsuitDraft = { number: "", size: "M", gender: "female" };

function parseLength(text: string): number | null {
  const value = Number(text.replace(",", ".").trim());
  return text.trim() && Number.isFinite(value) && value > 0 ? Math.round(value) : null;
}

function matches(query: string, ...parts: Array<string | null | undefined>): boolean {
  const q = query.trim().toLowerCase().replace(/№/g, "").trim();
  if (!q) return true;
  return parts.filter(Boolean).join(" ").toLowerCase().includes(q);
}

function StatusBadge({ active, feminine = false }: { active: boolean; feminine?: boolean }): JSX.Element {
  return active ? (
    <span className="rounded-full border border-emerald-700/25 bg-emerald-50 px-2.5 py-1 text-xs font-black text-emerald-800">В обороте</span>
  ) : (
    <span className="rounded-full border border-stone-500/30 bg-stone-100 px-2.5 py-1 text-xs font-black text-stone-600">{feminine ? "Выведена" : "Выведен"}</span>
  );
}

/** Администратор: справочник досок и гидрокостюмов для «Как в прошлый раз». */
export function InventoryPage({ session }: { session: StaffSession }): JSX.Element {
  const [tab, setTab] = useState<Tab>("boards");
  const [boards, setBoards] = useState<BoardRef[]>([]);
  const [wetsuits, setWetsuits] = useState<WetsuitRef[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<Toast>(null);
  const [query, setQuery] = useState("");
  const [showInactive, setShowInactive] = useState(false);
  const [boardDraft, setBoardDraft] = useState<BoardDraft>(EMPTY_BOARD);
  const [wetsuitDraft, setWetsuitDraft] = useState<WetsuitDraft>(EMPTY_WETSUIT);
  const [editingId, setEditingId] = useState("");
  const [editBoard, setEditBoard] = useState<BoardDraft>(EMPTY_BOARD);
  const [editWetsuit, setEditWetsuit] = useState<WetsuitDraft>(EMPTY_WETSUIT);

  async function load() {
    setLoading(true);
    try {
      const [nextBoards, nextWetsuits] = await Promise.all([getInventoryBoards(session.token, true), getInventoryWetsuits(session.token, true)]);
      setBoards(nextBoards);
      setWetsuits(nextWetsuits);
    } catch (err) {
      setToast({ type: "error", message: (err as Error).message });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [session.token]);

  async function mutate(action: () => Promise<unknown>, success: string) {
    setBusy(true);
    setToast(null);
    try {
      await action();
      invalidateInventoryCache();
      setToast({ type: "success", message: success });
      setEditingId("");
      await load();
    } catch (err) {
      setToast({ type: "error", message: (err as Error).message });
    } finally {
      setBusy(false);
    }
  }

  const visibleBoards = useMemo(
    () => boards.filter((item) => (showInactive || item.is_active !== false) && matches(query, item.number, item.name, boardKindLabel(item.kind))),
    [boards, query, showInactive],
  );
  const visibleWetsuits = useMemo(
    () => wetsuits.filter((item) => (showInactive || item.is_active !== false) && matches(query, item.number, item.size, genderLabel(item.gender))),
    [wetsuits, query, showInactive],
  );
  const activeBoards = boards.filter((item) => item.is_active !== false).length;
  const activeWetsuits = wetsuits.filter((item) => item.is_active !== false).length;

  const onAddBoard = (event: FormEvent) => {
    event.preventDefault();
    if (!boardDraft.number.trim()) {
      setToast({ type: "error", message: "Укажите номер доски." });
      return;
    }
    void mutate(
      () => createBoard({ number: boardDraft.number.trim(), name: boardDraft.name.trim(), kind: boardDraft.kind, length_cm: parseLength(boardDraft.length) }, session.token).then(() => setBoardDraft(EMPTY_BOARD)),
      `Доска № ${boardDraft.number.trim()} добавлена.`,
    );
  };

  const onAddWetsuit = (event: FormEvent) => {
    event.preventDefault();
    if (!wetsuitDraft.number.trim()) {
      setToast({ type: "error", message: "Укажите номер гидрокостюма." });
      return;
    }
    void mutate(
      () => createWetsuit({ number: wetsuitDraft.number.trim(), size: wetsuitDraft.size, gender: wetsuitDraft.gender }, session.token).then(() => setWetsuitDraft(EMPTY_WETSUIT)),
      `Гидрокостюм № ${wetsuitDraft.number.trim()} добавлен.`,
    );
  };

  return (
    <section className="space-y-5 sm:space-y-6">
      <header className="game-panel">
        <h1 className="game-heading">Инвентарь</h1>
        <p className="game-subheading mt-2 max-w-2xl">
          Доски и гидрокостюмы по номерам. Из этого списка оператор выбирает снаряжение при выдаче, а клиенту в следующий раз подставляется «Как в прошлый раз».
        </p>
        <div className="mt-4 grid grid-cols-2 gap-2 sm:max-w-md">
          <div className="game-stat p-3">
            <div className="text-xs uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">Досок в обороте</div>
            <div className="mt-1 text-xl font-black text-[color:var(--ink)]">{loading ? "—" : activeBoards}</div>
          </div>
          <div className="game-stat p-3">
            <div className="text-xs uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">Гидрокостюмов в обороте</div>
            <div className="mt-1 text-xl font-black text-[color:var(--ink)]">{loading ? "—" : activeWetsuits}</div>
          </div>
        </div>
      </header>

      {toast ? (
        <div
          role={toast.type === "error" ? "alert" : "status"}
          className={`game-panel ${toast.type === "success" ? "border-emerald-600/25 bg-emerald-50 text-emerald-900" : "border-red-600/25 bg-red-50 text-red-900"}`}
        >
          {toast.message}
        </div>
      ) : null}

      <section className="game-panel space-y-4">
        <div role="tablist" aria-label="Вид инвентаря" className="grid grid-cols-2 gap-2 sm:inline-grid sm:w-auto">
          <button
            type="button"
            role="tab"
            id="tab-boards"
            aria-selected={tab === "boards"}
            aria-controls="panel-inventory"
            onClick={() => {
              setTab("boards");
              setEditingId("");
            }}
            className={`game-tab min-h-11 ${tab === "boards" ? "game-tab-active" : ""}`}
          >
            Доски · {activeBoards}
          </button>
          <button
            type="button"
            role="tab"
            id="tab-wetsuits"
            aria-selected={tab === "wetsuits"}
            aria-controls="panel-inventory"
            onClick={() => {
              setTab("wetsuits");
              setEditingId("");
            }}
            className={`game-tab min-h-11 ${tab === "wetsuits" ? "game-tab-active" : ""}`}
          >
            Гидрокостюмы · {activeWetsuits}
          </button>
        </div>

        <div id="panel-inventory" role="tabpanel" aria-labelledby={tab === "boards" ? "tab-boards" : "tab-wetsuits"} className="space-y-4">
          {tab === "boards" ? (
            <form className="game-card grid gap-3 md:grid-cols-[minmax(8.5rem,0.7fr)_1.4fr_1fr_minmax(9rem,0.8fr)_auto] md:items-end" onSubmit={onAddBoard} aria-label="Новая доска">
              <div>
                <label htmlFor="new-board-number" className="mb-1.5 block text-sm font-bold text-[color:var(--ink-muted)]">Номер</label>
                <input id="new-board-number" className="game-input" inputMode="numeric" placeholder="Например, 7" value={boardDraft.number} onChange={(e) => setBoardDraft({ ...boardDraft, number: e.target.value })} required />
              </div>
              <div>
                <label htmlFor="new-board-name" className="mb-1.5 block text-sm font-bold text-[color:var(--ink-muted)]">Название</label>
                <input id="new-board-name" className="game-input" placeholder="Например, Ronix Koal" value={boardDraft.name} onChange={(e) => setBoardDraft({ ...boardDraft, name: e.target.value })} />
              </div>
              <div>
                <label htmlFor="new-board-kind" className="mb-1.5 block text-sm font-bold text-[color:var(--ink-muted)]">Тип</label>
                <select id="new-board-kind" className="game-input" value={boardDraft.kind} onChange={(e) => setBoardDraft({ ...boardDraft, kind: e.target.value as RideType })}>
                  {KINDS.map((kind) => <option key={kind} value={kind}>{rideTypeLabel(kind, { capitalize: true })}</option>)}
                </select>
              </div>
              <div>
                <label htmlFor="new-board-length" className="mb-1.5 block text-sm font-bold text-[color:var(--ink-muted)]">Длина, см</label>
                <input id="new-board-length" className="game-input" inputMode="numeric" placeholder="Например, 140" value={boardDraft.length} onChange={(e) => setBoardDraft({ ...boardDraft, length: e.target.value })} />
              </div>
              <button type="submit" className="game-button px-5" disabled={busy}>Добавить доску</button>
            </form>
          ) : (
            <form className="game-card grid gap-3 md:grid-cols-[minmax(8.5rem,0.7fr)_1fr_1fr_auto] md:items-end" onSubmit={onAddWetsuit} aria-label="Новый гидрокостюм">
              <div>
                <label htmlFor="new-wetsuit-number" className="mb-1.5 block text-sm font-bold text-[color:var(--ink-muted)]">Номер</label>
                <input id="new-wetsuit-number" className="game-input" inputMode="numeric" placeholder="Например, 14" value={wetsuitDraft.number} onChange={(e) => setWetsuitDraft({ ...wetsuitDraft, number: e.target.value })} required />
              </div>
              <div>
                <label htmlFor="new-wetsuit-size" className="mb-1.5 block text-sm font-bold text-[color:var(--ink-muted)]">Размер</label>
                <select id="new-wetsuit-size" className="game-input" value={wetsuitDraft.size} onChange={(e) => setWetsuitDraft({ ...wetsuitDraft, size: e.target.value as WetsuitSize })}>
                  {SIZES.map((size) => <option key={size} value={size}>{size}</option>)}
                </select>
              </div>
              <div>
                <label htmlFor="new-wetsuit-gender" className="mb-1.5 block text-sm font-bold text-[color:var(--ink-muted)]">Крой</label>
                <select id="new-wetsuit-gender" className="game-input" value={wetsuitDraft.gender} onChange={(e) => setWetsuitDraft({ ...wetsuitDraft, gender: e.target.value as WetsuitGender })}>
                  {GENDERS.map((gender) => <option key={gender.value} value={gender.value}>{gender.label}</option>)}
                </select>
              </div>
              <button type="submit" className="game-button px-5" disabled={busy}>Добавить гидрокостюм</button>
            </form>
          )}

          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <div className="flex-1">
              <label htmlFor="inventory-search" className="sr-only">Поиск по номеру или названию</label>
              <input id="inventory-search" type="search" className="game-input" placeholder="Поиск: номер, название, размер" value={query} onChange={(e) => setQuery(e.target.value)} />
            </div>
            <label className="game-card flex min-h-11 cursor-pointer items-center gap-3 px-3 py-2">
              <input type="checkbox" className="h-5 w-5 accent-[color:var(--accent)]" checked={showInactive} onChange={(e) => setShowInactive(e.target.checked)} />
              <span className="text-sm font-black text-[color:var(--ink)]">Показывать выведенные</span>
            </label>
          </div>

          {loading ? (
            <div className="game-card text-sm text-[color:var(--ink-muted)]">Загружаем справочник…</div>
          ) : tab === "boards" ? (
            visibleBoards.length === 0 ? (
              <div className="game-card text-sm text-[color:var(--ink-muted)]">{boards.length === 0 ? "Досок пока нет — добавьте первую выше." : "По запросу ничего не найдено."}</div>
            ) : (
              <ul className="grid gap-3 lg:grid-cols-2" aria-label="Доски">
                {visibleBoards.map((board) => {
                  const active = board.is_active !== false;
                  const editing = editingId === board.board_id;
                  return (
                    <li key={board.board_id} className={`game-card space-y-3 ${active ? "" : "opacity-75"}`}>
                      <div className="flex items-start gap-3">
                        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-[color:var(--accent-soft)] text-[color:var(--accent)]"><BoardIcon /></span>
                        <div className="min-w-0 flex-1">
                          <div className="text-lg font-black text-[color:var(--ink)]">№ {board.number}{board.name ? ` · ${board.name}` : ""}</div>
                          <div className="text-sm text-[color:var(--ink-muted)]">{[rideTypeLabel(board.kind, { capitalize: true }), board.length_cm ? `${board.length_cm} см` : ""].filter(Boolean).join(" · ")}</div>
                        </div>
                        <StatusBadge active={active} feminine />
                      </div>
                      {editing ? (
                        <form
                          className="grid gap-2 sm:grid-cols-2"
                          aria-label={`Изменить доску № ${board.number}`}
                          onSubmit={(event) => {
                            event.preventDefault();
                            void mutate(
                              () => updateBoard(board.board_id, { number: editBoard.number.trim(), name: editBoard.name.trim(), kind: editBoard.kind, length_cm: parseLength(editBoard.length) ?? 0 }, session.token),
                              `Доска № ${editBoard.number.trim()} сохранена.`,
                            );
                          }}
                        >
                          <div>
                            <label htmlFor={`eb-num-${board.board_id}`} className="mb-1 block text-xs font-bold text-[color:var(--ink-muted)]">Номер</label>
                            <input id={`eb-num-${board.board_id}`} className="game-input" value={editBoard.number} onChange={(e) => setEditBoard({ ...editBoard, number: e.target.value })} required />
                          </div>
                          <div>
                            <label htmlFor={`eb-name-${board.board_id}`} className="mb-1 block text-xs font-bold text-[color:var(--ink-muted)]">Название</label>
                            <input id={`eb-name-${board.board_id}`} className="game-input" value={editBoard.name} onChange={(e) => setEditBoard({ ...editBoard, name: e.target.value })} />
                          </div>
                          <div>
                            <label htmlFor={`eb-kind-${board.board_id}`} className="mb-1 block text-xs font-bold text-[color:var(--ink-muted)]">Тип</label>
                            <select id={`eb-kind-${board.board_id}`} className="game-input" value={editBoard.kind} onChange={(e) => setEditBoard({ ...editBoard, kind: e.target.value as RideType })}>
                              {KINDS.map((kind) => <option key={kind} value={kind}>{rideTypeLabel(kind, { capitalize: true })}</option>)}
                            </select>
                          </div>
                          <div>
                            <label htmlFor={`eb-len-${board.board_id}`} className="mb-1 block text-xs font-bold text-[color:var(--ink-muted)]">Длина, см</label>
                            <input id={`eb-len-${board.board_id}`} className="game-input" inputMode="numeric" value={editBoard.length} onChange={(e) => setEditBoard({ ...editBoard, length: e.target.value })} />
                          </div>
                          <div className="flex gap-2 sm:col-span-2">
                            <button type="submit" className="game-button flex-1 px-4" disabled={busy}>Сохранить</button>
                            <button type="button" className="game-button-secondary px-4" disabled={busy} onClick={() => setEditingId("")}>Отмена</button>
                          </div>
                        </form>
                      ) : (
                        <div className="flex flex-col gap-2 sm:flex-row">
                          <button
                            type="button"
                            className="game-button-secondary flex-1 px-4"
                            disabled={busy}
                            onClick={() => {
                              setEditingId(board.board_id);
                              setEditBoard({ number: board.number, name: board.name ?? "", kind: board.kind ?? "wakeboard", length: board.length_cm ? String(board.length_cm) : "" });
                            }}
                          >
                            Изменить
                          </button>
                          <button
                            type="button"
                            className="game-button-secondary flex-1 px-4"
                            disabled={busy}
                            onClick={() => void mutate(() => updateBoard(board.board_id, { is_active: !active }, session.token), active ? `Доска № ${board.number} выведена из оборота.` : `Доска № ${board.number} снова в обороте.`)}
                          >
                            {active ? "Вывести из оборота" : "Вернуть в оборот"}
                          </button>
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>
            )
          ) : visibleWetsuits.length === 0 ? (
            <div className="game-card text-sm text-[color:var(--ink-muted)]">{wetsuits.length === 0 ? "Гидрокостюмов пока нет — добавьте первый выше." : "По запросу ничего не найдено."}</div>
          ) : (
            <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3" aria-label="Гидрокостюмы">
              {visibleWetsuits.map((suit) => {
                const active = suit.is_active !== false;
                const editing = editingId === suit.wetsuit_id;
                return (
                  <li key={suit.wetsuit_id} className={`game-card space-y-3 ${active ? "" : "opacity-75"}`}>
                    <div className="flex items-start gap-3">
                      <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-[color:var(--accent-soft)] text-[color:var(--accent)]"><WetsuitIcon /></span>
                      <div className="min-w-0 flex-1">
                        <div className="text-lg font-black text-[color:var(--ink)]">№ {suit.number} · {suit.size ?? "—"}</div>
                        <div className="text-sm text-[color:var(--ink-muted)]">{genderLabel(suit.gender) || "крой не указан"}</div>
                      </div>
                      <StatusBadge active={active} />
                    </div>
                    {editing ? (
                      <form
                        className="grid gap-2 sm:grid-cols-3"
                        aria-label={`Изменить гидрокостюм № ${suit.number}`}
                        onSubmit={(event) => {
                          event.preventDefault();
                          void mutate(
                            () => updateWetsuit(suit.wetsuit_id, { number: editWetsuit.number.trim(), size: editWetsuit.size, gender: editWetsuit.gender }, session.token),
                            `Гидрокостюм № ${editWetsuit.number.trim()} сохранён.`,
                          );
                        }}
                      >
                        <div>
                          <label htmlFor={`ew-num-${suit.wetsuit_id}`} className="mb-1 block text-xs font-bold text-[color:var(--ink-muted)]">Номер</label>
                          <input id={`ew-num-${suit.wetsuit_id}`} className="game-input" value={editWetsuit.number} onChange={(e) => setEditWetsuit({ ...editWetsuit, number: e.target.value })} required />
                        </div>
                        <div>
                          <label htmlFor={`ew-size-${suit.wetsuit_id}`} className="mb-1 block text-xs font-bold text-[color:var(--ink-muted)]">Размер</label>
                          <select id={`ew-size-${suit.wetsuit_id}`} className="game-input" value={editWetsuit.size} onChange={(e) => setEditWetsuit({ ...editWetsuit, size: e.target.value as WetsuitSize })}>
                            {SIZES.map((size) => <option key={size} value={size}>{size}</option>)}
                          </select>
                        </div>
                        <div>
                          <label htmlFor={`ew-gender-${suit.wetsuit_id}`} className="mb-1 block text-xs font-bold text-[color:var(--ink-muted)]">Крой</label>
                          <select id={`ew-gender-${suit.wetsuit_id}`} className="game-input" value={editWetsuit.gender} onChange={(e) => setEditWetsuit({ ...editWetsuit, gender: e.target.value as WetsuitGender })}>
                            {GENDERS.map((gender) => <option key={gender.value} value={gender.value}>{gender.label}</option>)}
                          </select>
                        </div>
                        <div className="flex gap-2 sm:col-span-3">
                          <button type="submit" className="game-button flex-1 px-4" disabled={busy}>Сохранить</button>
                          <button type="button" className="game-button-secondary px-4" disabled={busy} onClick={() => setEditingId("")}>Отмена</button>
                        </div>
                      </form>
                    ) : (
                      <div className="flex flex-col gap-2 sm:flex-row">
                        <button
                          type="button"
                          className="game-button-secondary flex-1 px-4"
                          disabled={busy}
                          onClick={() => {
                            setEditingId(suit.wetsuit_id);
                            setEditWetsuit({ number: suit.number, size: suit.size ?? "M", gender: suit.gender ?? "female" });
                          }}
                        >
                          Изменить
                        </button>
                        <button
                          type="button"
                          className="game-button-secondary flex-1 px-4"
                          disabled={busy}
                          onClick={() => void mutate(() => updateWetsuit(suit.wetsuit_id, { is_active: !active }, session.token), active ? `Гидрокостюм № ${suit.number} выведен из оборота.` : `Гидрокостюм № ${suit.number} снова в обороте.`)}
                        >
                          {active ? "Вывести из оборота" : "Вернуть в оборот"}
                        </button>
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </section>
    </section>
  );
}
