import { useCallback, useEffect, useState } from "react";

import { getInventoryBoards, getInventoryWetsuits, isApiError } from "../api/client";
import type { BoardRef, BookingItem, DrinkChoice, LastTimeItem, RideType, WetsuitGender, WetsuitRef } from "../types";
import { formatDateRu } from "./dates";
import { inferGenderFromFullName } from "./gender";
import { rideTypeLabel } from "./labels";

/** «Как в прошлый раз»: подписи и форматирование снаряжения. */

export const DRINK_OPTIONS: Array<{ value: DrinkChoice; label: string }> = [
  { value: "coffee", label: "Кофе" },
  { value: "chocolate", label: "Шоколад" },
  { value: "none", label: "Не нужно" },
];

const DRINK_LABELS: Record<DrinkChoice, string> = {
  coffee: "Кофе",
  chocolate: "Горячий шоколад",
  none: "Не нужно",
};

export function drinkLabel(value: DrinkChoice | null | undefined): string {
  return value ? DRINK_LABELS[value] ?? "—" : "—";
}

const BOARD_KIND_ADJ: Record<RideType, string> = {
  wakeboard: "вейкборд",
  surf: "вейксерф",
  skim: "вейкским",
};

export function boardKindLabel(kind: RideType | null | undefined, options: { capitalize?: boolean } = {}): string {
  if (!kind) return "";
  return options.capitalize ? rideTypeLabel(kind, { capitalize: true }) : BOARD_KIND_ADJ[kind] ?? "";
}

export function genderLabel(gender: WetsuitGender | null | undefined, short = false): string {
  if (gender === "female") return short ? "жен." : "женский";
  if (gender === "male") return short ? "муж." : "мужской";
  return "";
}

export function numberLabel(number: string | null | undefined): string {
  const text = String(number ?? "").trim();
  return text ? `№ ${text}` : "№ —";
}

/** «№ 14 · M» */
export function wetsuitTitle(ref: WetsuitRef | null | undefined): string {
  if (!ref) return "—";
  return [numberLabel(ref.number), ref.size].filter(Boolean).join(" · ");
}

/** «№ 14 · M · жен.» — для списков выбора. */
export function wetsuitOptionLabel(ref: WetsuitRef): string {
  return [numberLabel(ref.number), ref.size, genderLabel(ref.gender, true)].filter(Boolean).join(" · ");
}

/** «№ 7 · Ronix Koal Classic» */
export function boardTitle(ref: BoardRef | null | undefined): string {
  if (!ref) return "—";
  return [numberLabel(ref.number), ref.name].filter(Boolean).join(" · ");
}

/** «вейксерф · 142 см» */
export function boardDetails(ref: BoardRef | null | undefined): string {
  if (!ref) return "";
  return [boardKindLabel(ref.kind), ref.length_cm ? `${ref.length_cm} см` : ""].filter(Boolean).join(" · ");
}

export function boardOptionLabel(ref: BoardRef): string {
  return [boardTitle(ref), boardDetails(ref)].filter(Boolean).join(" · ");
}

export function hasIssuedEquipment(booking: Pick<BookingItem, "wetsuit_id" | "board_id" | "drink">): boolean {
  return Boolean(booking.wetsuit_id || booking.board_id || booking.drink);
}

/** API знает про «Как в прошлый раз» (новые поля есть в ответе). */
export function supportsClientPrefs(booking: BookingItem): boolean {
  return "last_time" in booking || "board_id" in booking;
}

/** «5-й визит» */
export function visitOrdinal(visitsBefore: number | null | undefined): string {
  const n = Math.max(0, Number(visitsBefore) || 0) + 1;
  return `${n}-й визит`;
}

/** «выдавала Ольга Кузнецова» — глагол по роду, если род понятен из имени. */
export function issuedByPhrase(name: string | null | undefined, tense: "past-habitual" | "past" = "past-habitual"): string {
  const text = String(name ?? "").trim();
  if (!text) return "";
  const gender = inferGenderFromFullName(text);
  const verb = tense === "past" ? (gender === "female" ? "выдала" : gender === "male" ? "выдал" : "выдано:") : gender === "female" ? "выдавала" : gender === "male" ? "выдавал" : "выдано:";
  return `${verb} ${text}`;
}

export function lastTimeCaption(lastTime: LastTimeItem): string {
  const parts = [`визит ${formatDateRu(lastTime.date)}`];
  const who = issuedByPhrase(lastTime.issued_by_name);
  if (who) parts.push(who);
  return parts.join(" · ");
}

export function issuedClock(iso: string | null | undefined): string {
  if (!iso) return "";
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) return "";
  return parsed.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Moscow" });
}

const EQUIPMENT_KEYS = [
  "wetsuit",
  "board",
  "last_time",
  "visits_before",
  "equipment_issued_by_name",
] as const;

/**
 * Слияние ответа PATCH статуса/подготовки/таймера с карточкой: эти ответы не несут
 * «Как в прошлый раз» (last_time, подписи снаряжения) — оставляем то, что уже было.
 */
export function mergeBookingUpdate<T extends object, U extends object>(current: T, updated: U): T & U {
  const merged = { ...current, ...updated } as unknown as Record<string, unknown>;
  const prev = current as Record<string, unknown>;
  const next = updated as Record<string, unknown>;
  for (const key of EQUIPMENT_KEYS) {
    if ((next[key] === null || next[key] === undefined || next[key] === "") && prev[key] !== undefined) {
      merged[key] = prev[key];
    }
  }
  return merged as unknown as T & U;
}

type InventoryState = {
  boards: BoardRef[];
  wetsuits: WetsuitRef[];
  loading: boolean;
  /** Сервер ещё не обновлён (нет /inventory) или справочник не настроен. */
  unavailable: boolean;
  reload: () => void;
};

let inventoryCache: { token: string | undefined; at: number; boards: BoardRef[]; wetsuits: WetsuitRef[] } | null = null;
const INVENTORY_TTL_MS = 60_000;

export function invalidateInventoryCache(): void {
  inventoryCache = null;
}

/** Активный инвентарь для выбора при выдаче. Кэш на минуту, чтобы карточки не дёргали API по очереди. */
export function useInventory(token: string | undefined, enabled = true): InventoryState {
  const fresh = inventoryCache && inventoryCache.token === token && Date.now() - inventoryCache.at < INVENTORY_TTL_MS ? inventoryCache : null;
  const [boards, setBoards] = useState<BoardRef[]>(fresh?.boards ?? []);
  const [wetsuits, setWetsuits] = useState<WetsuitRef[]>(fresh?.wetsuits ?? []);
  const [loading, setLoading] = useState(!fresh && enabled);
  const [unavailable, setUnavailable] = useState(false);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (!enabled) return;
    const cached = inventoryCache && inventoryCache.token === token && Date.now() - inventoryCache.at < INVENTORY_TTL_MS ? inventoryCache : null;
    if (cached && tick === 0) {
      setBoards(cached.boards);
      setWetsuits(cached.wetsuits);
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    Promise.all([getInventoryBoards(token), getInventoryWetsuits(token)])
      .then(([nextBoards, nextWetsuits]) => {
        if (cancelled) return;
        inventoryCache = { token, at: Date.now(), boards: nextBoards, wetsuits: nextWetsuits };
        setBoards(nextBoards);
        setWetsuits(nextWetsuits);
        setUnavailable(false);
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setUnavailable(isApiError(error, 404) || isApiError(error));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [token, enabled, tick]);

  const reload = useCallback(() => {
    invalidateInventoryCache();
    setTick((value) => value + 1);
  }, []);

  return { boards, wetsuits, loading, unavailable, reload };
}
