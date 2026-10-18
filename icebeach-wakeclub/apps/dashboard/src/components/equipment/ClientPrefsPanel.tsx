import { useEffect, useId, useMemo, useState } from "react";

import { repeatLastEquipment, resetClientPrefs, updateBookingEquipment } from "../../api/client";
import { formatDateRu } from "../../lib/dates";
import {
  boardDetails,
  boardOptionLabel,
  drinkLabel,
  genderLabel,
  hasIssuedEquipment,
  issuedByPhrase,
  issuedClock,
  lastTimeCaption,
  numberLabel,
  supportsClientPrefs,
  wetsuitOptionLabel,
  wetsuitTitle,
} from "../../lib/equipment";
import type { BoardRef, BookingItem, DrinkChoice, EquipmentUpdateRequest, StaffSession, WetsuitRef } from "../../types";
import { DrinkSegmented } from "./DrinkSegmented";
import { BoardIcon, CupIcon, WetsuitIcon } from "./icons";
import { ComboOption, InventoryCombobox } from "./InventoryCombobox";

type InventoryLike = {
  boards: BoardRef[];
  wetsuits: WetsuitRef[];
  loading: boolean;
  unavailable: boolean;
};

type Props = {
  session: StaffSession;
  booking: BookingItem;
  inventory: InventoryLike;
  onUpdated: (booking: BookingItem) => void;
  /** Тренер: видит всё, меняет только доску. */
  boardOnly?: boolean;
  /** Карточка в списке броней: без подвала и с меньшими отступами. */
  dense?: boolean;
};

type Source = {
  wetsuit?: WetsuitRef | null;
  board?: BoardRef | null;
  drink?: DrinkChoice | null;
};

function PrefTile({ icon, title, value, sub }: { icon: JSX.Element; title: string; value: string; sub?: string }): JSX.Element {
  return (
    <div className="flex min-h-[68px] items-center gap-3 rounded-[18px] border border-[color:var(--border)] bg-[#FFFCFA] p-3">
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[color:var(--accent-soft)] text-[color:var(--accent)]">{icon}</span>
      <div className="min-w-0">
        <div className="text-[11px] font-black uppercase tracking-[0.08em] text-[color:var(--ink-muted)]">{title}</div>
        <div className="truncate text-[15px] font-black leading-tight text-[color:var(--ink)]">{value}</div>
        {sub ? <div className="truncate text-xs text-[color:var(--ink-muted)]">{sub}</div> : null}
      </div>
    </div>
  );
}

function Tiles({ source, dense }: { source: Source; dense?: boolean }): JSX.Element {
  const wetsuit = source.wetsuit;
  const board = source.board;
  return (
    <div className={`grid gap-2.5 ${dense ? "grid-cols-1" : "md:grid-cols-3"}`}>
      <PrefTile
        icon={<WetsuitIcon />}
        title="Гидрокостюм"
        value={wetsuit ? wetsuitTitle(wetsuit) : "Не выдавали"}
        sub={wetsuit ? genderLabel(wetsuit.gender) || undefined : undefined}
      />
      <PrefTile
        icon={<BoardIcon />}
        title="Доска"
        value={board ? [numberLabel(board.number), board.name].filter(Boolean).join(" · ") : "Не выдавали"}
        sub={board ? boardDetails(board) || undefined : undefined}
      />
      <PrefTile icon={<CupIcon />} title="Напиток" value={source.drink ? drinkLabel(source.drink) : "Не указан"} sub={source.drink && source.drink !== "none" ? "после заезда" : undefined} />
    </div>
  );
}

/**
 * «Как в прошлый раз»: блок в карточке брони после отметки о прибытии.
 * Состояния: постоянный клиент (подсказка + выдача в одно касание), первый визит, уже выдано, правка.
 */
export function ClientPrefsPanel({ session, booking, inventory, onUpdated, boardOnly = false, dense = false }: Props): JSX.Element | null {
  const uid = useId();
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  const issued = hasIssuedEquipment(booking);
  const last = booking.last_time ?? null;

  const [wetsuitId, setWetsuitId] = useState("");
  const [boardId, setBoardId] = useState("");
  const [drink, setDrink] = useState<DrinkChoice | "">("");

  function prefill() {
    const pickActive = <T extends { is_active?: boolean }>(ref: T | null | undefined): T | null => (ref && ref.is_active !== false ? ref : null);
    if (issued) {
      setWetsuitId(booking.wetsuit_id ?? "");
      setBoardId(booking.board_id ?? "");
      setDrink(booking.drink ?? "");
    } else if (last) {
      setWetsuitId(pickActive(last.wetsuit)?.wetsuit_id ?? "");
      setBoardId(pickActive(last.board)?.board_id ?? "");
      setDrink(last.drink ?? "");
    } else {
      setWetsuitId("");
      setBoardId("");
      setDrink("");
    }
  }

  useEffect(() => {
    setEditing(false);
    setWarnings([]);
    setError(null);
  }, [booking.booking_id]);

  const wetsuitOptions = useMemo<ComboOption[]>(() => {
    const wantedSize = booking.wetsuit_size ?? null;
    const wantedGender = booking.wetsuit_gender ?? null;
    const list = inventory.wetsuits.map((ref) => {
      const fits = Boolean(wantedSize && ref.size === wantedSize && (!wantedGender || !ref.gender || ref.gender === wantedGender));
      return {
        value: ref.wetsuit_id,
        label: wetsuitOptionLabel(ref),
        hint: fits ? "по брони" : undefined,
        keywords: [ref.number, ref.size, genderLabel(ref.gender), genderLabel(ref.gender, true)].filter(Boolean).join(" "),
        fits,
      };
    });
    list.sort((a, b) => Number(b.fits) - Number(a.fits));
    // Уже выданный, но выведенный из оборота гидрокостюм — оставить видимым.
    if (booking.wetsuit && !list.some((item) => item.value === booking.wetsuit?.wetsuit_id)) {
      list.push({ value: booking.wetsuit.wetsuit_id, label: wetsuitOptionLabel(booking.wetsuit), hint: "выведен", keywords: booking.wetsuit.number, fits: false });
    }
    return list;
  }, [booking.wetsuit, booking.wetsuit_gender, booking.wetsuit_size, inventory.wetsuits]);

  const boardOptions = useMemo<ComboOption[]>(() => {
    const list = inventory.boards.map((ref) => ({
      value: ref.board_id,
      label: boardOptionLabel(ref),
      hint: ref.kind && ref.kind === booking.ride_type ? "по дисциплине" : undefined,
      keywords: [ref.number, ref.name, boardDetails(ref)].filter(Boolean).join(" "),
    }));
    if (booking.board && !list.some((item) => item.value === booking.board?.board_id)) {
      list.push({ value: booking.board.board_id, label: boardOptionLabel(booking.board), hint: "выведена", keywords: booking.board.number });
    }
    return list;
  }, [booking.board, booking.ride_type, inventory.boards]);

  if (!supportsClientPrefs(booking)) {
    return null;
  }

  async function run(action: () => Promise<{ booking: BookingItem; warnings: string[] }>) {
    setBusy(true);
    setError(null);
    try {
      const result = await action();
      onUpdated(result.booking);
      setWarnings(result.warnings);
      setEditing(false);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const repeat = () => run(() => repeatLastEquipment(booking.booking_id, session.token));

  const save = () => {
    const payload: EquipmentUpdateRequest = boardOnly ? { board_id: boardId } : { wetsuit_id: wetsuitId, board_id: boardId, drink };
    return run(() => updateBookingEquipment(booking.booking_id, payload, session.token));
  };

  const resetPrefs = async () => {
    if (!window.confirm("Сбросить «Как в прошлый раз» для этого клиента? Прошлые выдачи в бронях сохранятся, но подсказываться больше не будут.")) return;
    setBusy(true);
    setError(null);
    try {
      await resetClientPrefs(booking.client_id, session.token);
      onUpdated({ ...booking, last_time: null });
      setWarnings([]);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const startEdit = () => {
    prefill();
    setWarnings([]);
    setEditing(true);
  };

  const issuedSource: Source = { wetsuit: booking.wetsuit, board: booking.board, drink: booking.drink };
  const lastSource: Source = last ? { wetsuit: last.wetsuit, board: last.board, drink: last.drink } : {};
  const issuedWho = issuedByPhrase(booking.equipment_issued_by_name, "past");
  const issuedAt = issuedClock(booking.equipment_issued_at);
  const titleId = `${uid}-title`;
  const drinkLabelId = `${uid}-drink`;
  const inventoryEmpty = !inventory.loading && !inventory.unavailable && inventory.boards.length === 0 && inventory.wetsuits.length === 0;

  const box = issued || last ? "border-[color:var(--accent-border)] bg-[color:var(--shift-wash)]" : "border-dashed border-[color:var(--accent-border)] bg-[#FFFCFA]";

  return (
    <section aria-labelledby={titleId} className={`rounded-[22px] border ${dense ? "p-3" : "p-4"} ${box} space-y-3`}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <h3 id={titleId} className="text-xs font-black uppercase tracking-[0.12em] text-[color:var(--accent)]">
          {issued ? "Снаряжение выдано" : last ? "Как в прошлый раз" : "Предпочтений пока нет"}
        </h3>
        {issued ? (
          <span className="text-xs text-[color:var(--ink-muted)]">{[issuedAt ? `в ${issuedAt}` : "", issuedWho].filter(Boolean).join(" · ")}</span>
        ) : last ? (
          <span className="text-xs text-[color:var(--ink-muted)]">{lastTimeCaption(last)}</span>
        ) : null}
      </div>

      {!editing ? (
        issued ? (
          <Tiles source={issuedSource} dense={dense} />
        ) : last ? (
          <Tiles source={lastSource} dense={dense} />
        ) : (
          <div>
            <p className="text-sm text-[color:var(--ink-muted)]">Заполните при выдаче экипировки — в следующий раз всё подставится само.</p>
            <div className="mt-2 flex flex-wrap gap-1.5" aria-hidden="true">
              <span className="rounded-full border border-dashed border-stone-400 px-2.5 py-1 text-xs text-[color:var(--ink-muted)]">
                {booking.wetsuit_required && booking.wetsuit_size ? `Гидрокостюм: размер ${booking.wetsuit_size} из брони` : "Гидрокостюм — ?"}
              </span>
              <span className="rounded-full border border-dashed border-stone-400 px-2.5 py-1 text-xs text-[color:var(--ink-muted)]">Доска — ?</span>
              <span className="rounded-full border border-dashed border-stone-400 px-2.5 py-1 text-xs text-[color:var(--ink-muted)]">Кофе или шоколад?</span>
            </div>
          </div>
        )
      ) : (
        <div className="space-y-3">
          {inventory.unavailable ? (
            <div className="rounded-2xl border border-amber-700/25 bg-amber-50 px-3 py-2 text-sm text-amber-900" role="status">
              Справочник инвентаря недоступен. Обратитесь к администратору.
            </div>
          ) : inventoryEmpty ? (
            <div className="rounded-2xl border border-amber-700/25 bg-amber-50 px-3 py-2 text-sm text-amber-900" role="status">
              Справочник пуст: доски и гидрокостюмы добавляет администратор в разделе «Инвентарь».
            </div>
          ) : null}
          <div className={`grid gap-3 ${boardOnly ? "" : dense ? "lg:grid-cols-[0.9fr_1.2fr_1.4fr]" : "md:grid-cols-[0.9fr_1.25fr_1.6fr]"}`}>
            {!boardOnly ? (
              <InventoryCombobox
                id={`${uid}-wetsuit`}
                label="Гидрокостюм"
                options={wetsuitOptions}
                value={wetsuitId}
                onChange={setWetsuitId}
                placeholder="№ или размер"
                disabled={busy || inventory.loading}
              />
            ) : null}
            <InventoryCombobox
              id={`${uid}-board`}
              label="Доска"
              options={boardOptions}
              value={boardId}
              onChange={setBoardId}
              placeholder="№ или название"
              disabled={busy || inventory.loading}
            />
            {!boardOnly ? (
              <div>
                <div id={drinkLabelId} className="mb-1.5 text-sm font-bold text-[color:var(--ink-muted)]">Напиток</div>
                <DrinkSegmented value={drink} onChange={setDrink} labelId={drinkLabelId} disabled={busy} />
              </div>
            ) : null}
          </div>
        </div>
      )}

      {warnings.length > 0 ? (
        <ul className="space-y-1 rounded-2xl border border-amber-700/25 bg-amber-50 px-3 py-2 text-sm text-amber-900" role="status">
          {warnings.map((warning) => (
            <li key={warning}>⚠ {warning}</li>
          ))}
        </ul>
      ) : null}
      {error ? (
        <div className="rounded-2xl border border-red-700/25 bg-red-50 px-3 py-2 text-sm text-red-900" role="alert">
          {error}
        </div>
      ) : null}

      <div className="flex flex-col gap-2 sm:flex-row">
        {editing ? (
          <>
            <button type="button" className="game-button flex-1 px-5" disabled={busy} onClick={() => void save()}>
              {busy ? "Сохраняем…" : "Сохранить выдачу"}
            </button>
            <button type="button" className="game-button-secondary px-5" disabled={busy} onClick={() => setEditing(false)}>
              Отмена
            </button>
          </>
        ) : issued ? (
          <button type="button" className="game-button-secondary px-5 sm:ml-auto" disabled={busy} onClick={startEdit}>
            {boardOnly ? "Сменить доску" : "Изменить выдачу"}
          </button>
        ) : last ? (
          <>
            <button type="button" className="game-button flex-1 px-5" disabled={busy} onClick={() => void repeat()}>
              {busy ? "Выдаём…" : boardOnly ? "Выдать доску как в прошлый раз" : "Выдать как в прошлый раз"}
            </button>
            <button type="button" className="game-button-secondary px-5" disabled={busy} onClick={startEdit}>
              Изменить
            </button>
          </>
        ) : (
          <button type="button" className="game-button-secondary flex-1 px-5" disabled={busy} onClick={startEdit}>
            {boardOnly ? "Выбрать доску" : "Заполнить при выдаче"}
          </button>
        )}
      </div>

      {session.role === "admin" && last && !issued && !editing ? (
        <button
          type="button"
          className="min-h-11 text-left text-sm font-bold text-[color:var(--ink-muted)] underline decoration-dotted underline-offset-4 hover:text-[color:var(--accent)]"
          disabled={busy}
          onClick={() => void resetPrefs()}
        >
          Сбросить предпочтения клиента
        </button>
      ) : null}

      {!dense ? (
        <div className="flex flex-col gap-1 border-t border-dashed border-[color:var(--border)] pt-2 text-xs text-[color:var(--ink-muted)] sm:flex-row sm:justify-between">
          <span>Видят администратор, оператор и тренер; пилот — только доску.</span>
          <span className="sm:whitespace-nowrap">Сохранится в брони {formatDateRu(booking.date)}</span>
        </div>
      ) : null}
    </section>
  );
}
