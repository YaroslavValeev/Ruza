import { useEffect, useState } from "react";

import { getBoats } from "../api/client";
import type { BoatItem, BookingStatus, StaffRole, StaffSession } from "../types";
import { BOOKING_STATUS_LABELS } from "./label-dict";

// Словари без зависимостей вынесены в label-dict.ts (их грузит node-тест pilot-utils без React).
export { BOOKING_STATUS_LABELS, rideTypeLabel } from "./label-dict";

/** Единый словарь подписей интерфейса. Значения API не меняются — только отображение. */

export const ROLE_LABELS: Record<StaffRole, string> = {
  admin: "Администратор",
  operator: "Оператор",
  pilot: "Пилот",
  coach: "Тренер",
  marketing_read: "Маркетинг",
};

export function roleLabel(role: string | null | undefined): string {
  return (role && ROLE_LABELS[role as StaffRole]) || "Сотрудник";
}

export function statusLabel(status: string | null | undefined): string {
  return (status && BOOKING_STATUS_LABELS[status as BookingStatus]) || "Статус уточняется";
}

/** Шаги живой смены: полные подписи (от sm) и короткие для телефона. */
export const SHIFT_STEPS: Array<{ full: string; short: string }> = [
  { full: "Подтверждено", short: "Бронь" },
  { full: "На месте", short: "На месте" },
  { full: "Готово к старту", short: "Готово" },
  { full: "На воде", short: "На воде" },
  { full: "Завершено", short: "Финиш" },
];

export const LEAD_SOURCE_OPTIONS: Array<{ value: string; label: string }> = [
  { value: "offline", label: "Лично в клубе" },
  { value: "phone", label: "Звонок" },
  { value: "instagram", label: "Инстаграм" },
  { value: "telegram", label: "Телеграм" },
  { value: "vk", label: "ВКонтакте" },
  { value: "site", label: "Сайт" },
  { value: "referral", label: "Рекомендация" },
  { value: "other", label: "Другое" },
];

const LEAD_SOURCE_ALIASES: Record<string, string> = {
  ig: "instagram",
  tg: "telegram",
  website: "site",
  web: "site",
  call: "phone",
};

export function leadSourceLabel(value: string | null | undefined): string {
  if (!value) return "—";
  const key = value.trim().toLowerCase();
  const normalized = LEAD_SOURCE_ALIASES[key] ?? key;
  return LEAD_SOURCE_OPTIONS.find((item) => item.value === normalized)?.label ?? value;
}

/* ---------- Названия катеров ---------- */

const BOAT_CACHE_KEY = "mywave:boat-names";
let boatNames: Record<string, string> = readBoatCache();
const listeners = new Set<() => void>();
let boatsRequested = false;

function readBoatCache(): Record<string, string> {
  try {
    const raw = typeof window !== "undefined" ? window.localStorage.getItem(BOAT_CACHE_KEY) : null;
    return raw ? (JSON.parse(raw) as Record<string, string>) : {};
  } catch {
    return {};
  }
}

export function rememberBoats(boats: Array<Pick<BoatItem, "boat_id" | "boat_name">>): void {
  let changed = false;
  for (const boat of boats) {
    if (boat.boat_id && boat.boat_name && boat.boat_name !== boat.boat_id && boatNames[boat.boat_id] !== boat.boat_name) {
      boatNames = { ...boatNames, [boat.boat_id]: boat.boat_name };
      changed = true;
    }
  }
  if (!changed) return;
  try {
    window.localStorage.setItem(BOAT_CACHE_KEY, JSON.stringify(boatNames));
  } catch {
    /* хранилище недоступно — работаем из памяти */
  }
  listeners.forEach((listener) => listener());
}

/** Человекочитаемое имя катера: из справочника лодок, иначе «Катер N» по номеру в идентификаторе. */
export function boatLabel(boatId: string | null | undefined): string {
  if (!boatId) return "Катер не назначен";
  const known = boatNames[boatId];
  if (known) return known;
  const digits = boatId.match(/\d+/);
  return digits ? `Катер ${Number(digits[0])}` : "Катер";
}

/** Подгружает справочник лодок (только ролям, у которых есть доступ) и перерисовывает компонент. */
export function useBoatNames(session: Pick<StaffSession, "role" | "token"> | null | undefined): void {
  const [, setVersion] = useState(0);
  useEffect(() => {
    const listener = () => setVersion((value) => value + 1);
    listeners.add(listener);
    if (!boatsRequested && session && ["admin", "operator", "pilot"].includes(session.role)) {
      boatsRequested = true;
      void getBoats(session.token)
        .then((boats) => rememberBoats(boats))
        .catch(() => {
          boatsRequested = false;
        });
    }
    return () => {
      listeners.delete(listener);
    };
  }, [session?.role, session?.token]);
}

/* ---------- Предстартовая проверка и проверка сценария ---------- */

const PREFLIGHT_TITLES: Record<string, string> = {
  tab: "Таблица данных",
  staff: "Сотрудники",
  club_id: "Клуб",
  boats: "Катера",
  pricing: "Цены",
  schedule: "Расписание",
  availability: "Свободные слоты",
  booking_id: "Номера броней",
  client_id: "Номера клиентов",
  ride_type: "Дисциплины в бронях",
};

const TAB_LABELS: Record<string, string> = {
  bookings: "брони",
  clients: "клиенты",
  boats: "катера",
  pricing: "цены",
  schedule: "расписание",
  staff_users: "сотрудники",
  payments: "оплаты",
  checkins: "отметки о прибытии",
  leads: "лиды",
  analytics_daily: "дневная аналитика",
};

function firstNumber(text: string): string | null {
  const match = text.match(/=\s*(\d+)/) ?? text.match(/(\d+)/);
  return match ? match[1] : null;
}

/** Перевод строки проверки по её коду и уровню; исходный текст API остаётся в подсказке title. */
export function preflightCheckText(level: string, code: string, message: string): { title: string; text: string } {
  const [group, detail] = code.split(":");
  const title = group === "tab" && detail ? `Таблица «${TAB_LABELS[detail] ?? detail}»` : group === "staff" && detail ? `Роль «${roleLabel(detail)}»` : PREFLIGHT_TITLES[group] ?? "Проверка";
  const n = firstNumber(message);
  const ok = level === "PASS";
  switch (group) {
    case "tab":
      return { title, text: ok ? `Таблица доступна, столбцов: ${n ?? "—"}.` : "Таблица недоступна или повреждена." };
    case "staff":
      return { title, text: ok ? "Активный сотрудник с этой ролью есть." : "Нет активного сотрудника с этой ролью." };
    case "club_id":
      return { title, text: ok ? "Клуб определён." : level === "WARN" ? "У сотрудников указано несколько клубов." : "Не найден активный клуб у сотрудников." };
    case "boats":
      return { title, text: ok ? `Активных катеров: ${n ?? "—"}.` : "Нет активных катеров." };
    case "pricing":
      return { title, text: ok ? `Действующих строк цен: ${n ?? "—"}.` : "Нет действующих цен на эту дату." };
    case "schedule":
      return { title, text: ok ? `Строк расписания на этот день недели: ${n ?? "—"}.` : "Нет расписания на этот день недели." };
    case "availability":
      return { title, text: ok ? `Свободных слотов: ${n ?? "—"}.` : "На эту дату нет свободных слотов." };
    case "booking_id":
      return { title, text: ok ? "Повторов нет." : "Есть повторяющиеся номера броней." };
    case "client_id":
      return { title, text: ok ? "Повторов нет." : "Есть повторяющиеся номера клиентов." };
    case "ride_type":
      return { title, text: ok ? "У всех броней указана дисциплина." : "В части броней не указана дисциплина." };
    default:
      return { title, text: ok ? "Пройдено." : "Требует внимания." };
  }
}

const SMOKE_TITLES: Record<string, string> = {
  "clients.query": "Поиск клиента",
  "availability.slot": "Свободный слот",
  "bookings.create": "Создание брони",
  "bookings.persisted": "Сохранение брони",
  "bookings.ride_type": "Дисциплина в брони",
  "bookings.wetsuit_gender": "Пол для гидрокостюма",
  "bookings.wetsuit_size": "Размер гидрокостюма",
  "pilot.queue": "Очередь пилота",
  "kpi.breakdown": "Разрез аналитики",
  "bookings.cancel": "Отмена тестовой брони",
  smoke: "Сценарий",
};

export function smokeCheckText(level: string, code: string): { title: string; text: string } {
  const title = SMOKE_TITLES[code] ?? "Шаг проверки";
  return { title, text: level === "PASS" ? "Шаг выполнен." : "Шаг завершился ошибкой." };
}
