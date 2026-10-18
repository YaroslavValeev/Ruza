import { boardDetails, boardTitle } from "../../lib/equipment";
import type { BoardRef } from "../../types";
import { BoardIcon } from "./icons";

type Props = {
  board?: BoardRef | null;
  lastBoard?: BoardRef | null;
  compact?: boolean;
};

/** Вид пилота: только доска, без редактирования. */
export function BoardChip({ board, lastBoard, compact }: Props): JSX.Element | null {
  const shown = board ?? lastBoard ?? null;
  if (!shown) return null;
  const issued = Boolean(board);
  const sameAsLast = issued && lastBoard && lastBoard.board_id === board?.board_id;
  const details = boardDetails(shown);
  const sub = issued ? [details, sameAsLast ? "как в прошлый раз" : ""].filter(Boolean).join(" · ") : ["в прошлый раз", details].filter(Boolean).join(" · ");

  return (
    <div
      className={`flex items-center gap-3 rounded-[18px] border border-[color:var(--accent-border)] bg-[color:var(--shift-wash)] ${compact ? "px-3 py-2" : "p-3"}`}
      aria-label={`Доска: ${boardTitle(shown)}${issued ? ", выдана" : ", ещё не выдана"}`}
      role="group"
    >
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[color:var(--accent-soft)] text-[color:var(--accent)]">
        <BoardIcon />
      </span>
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-black text-[color:var(--ink)]">Доска {boardTitle(shown)}</div>
        {sub ? <div className="truncate text-xs text-[color:var(--ink-muted)]">{sub}</div> : null}
      </div>
      {issued ? (
        <span className="shrink-0 rounded-full border border-emerald-700/25 bg-emerald-50 px-2.5 py-1 text-[11px] font-black text-emerald-800">Выдана</span>
      ) : (
        <span className="shrink-0 rounded-full border border-amber-700/25 bg-amber-50 px-2.5 py-1 text-[11px] font-black text-amber-900">Не выдана</span>
      )}
    </div>
  );
}
