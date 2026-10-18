"""«Как в прошлый раз»: справочник инвентаря (доски, гидрокостюмы) и выдача снаряжения.

Все данные берутся из уже прочитанных строк: на запрос списка добавляется не больше
трёх чтений вкладок (boards, wetsuits, staff_users), а не чтение на каждую запись.
"""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, Iterable
from uuid import uuid4

from fastapi import HTTPException, status

from packages.sheets import SheetWrapper
from packages.sheets.schema import OPTIONAL_COLUMNS

from .common import parse_bool
from .ride_runtime import iter_booking_slots

DRINK_CHOICES = ("coffee", "chocolate", "none")
RIDE_KINDS = ("wakeboard", "surf", "skim")
WETSUIT_SIZES = ("XS", "S", "M", "L", "XL", "XXL")
WETSUIT_GENDERS = ("male", "female")
VISITED_STATUSES = {"arrived", "ready", "in_progress", "done"}
NO_EQUIPMENT_STATUSES = {"cancelled", "no_show"}
EQUIPMENT_COLUMNS: tuple[str, ...] = OPTIONAL_COLUMNS["bookings"]
EQUIPMENT_ITEM_FIELDS = (
    "wetsuit_id",
    "board_id",
    "drink",
    "equipment_issued_by",
    "equipment_issued_by_name",
    "equipment_issued_at",
    "wetsuit",
    "board",
    "last_time",
    "visits_before",
)

INVENTORY_TABS: dict[str, tuple[str, str]] = {
    "boards": ("board_id", "brd"),
    "wetsuits": ("wetsuit_id", "wst"),
}
INVENTORY_LABELS = {"boards": "Доска", "wetsuits": "Гидрокостюм"}
INVENTORY_NOT_FOUND = {"boards": "Доска не найдена в справочнике.", "wetsuits": "Гидрокостюм не найден в справочнике."}

MIGRATION_HINT = "Запустите миграцию Таблицы: python -m packages.sheets (см. MIGRATION.md)."


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _int_or_none(value: Any) -> int | None:
    text = str(value if value is not None else "").strip()
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _number_sort_key(number: str) -> tuple[int, str]:
    match = re.match(r"\s*(\d+)", number or "")
    return (int(match.group(1)) if match else 10**9, (number or "").strip().lower())


def _norm_number(number: Any) -> str:
    return str(number or "").strip().lstrip("№").strip().lower()


def _is_active(row: dict[str, str]) -> bool:
    raw = row.get("is_active")
    if raw is None or str(raw).strip() == "":
        return True
    return parse_bool(raw)


# ---------------------------------------------------------------------------
# Справочник инвентаря
# ---------------------------------------------------------------------------


def board_ref(row: dict[str, str]) -> dict[str, Any]:
    kind = row.get("kind") or ""
    length = _int_or_none(row.get("length_cm"))
    return {
        "board_id": row.get("board_id", ""),
        "number": str(row.get("number", "")).strip(),
        "name": str(row.get("name", "")).strip(),
        "kind": kind if kind in RIDE_KINDS else None,
        "length_cm": length if length else None,
        "is_active": _is_active(row),
    }


def wetsuit_ref(row: dict[str, str]) -> dict[str, Any]:
    size = str(row.get("size") or "").strip().upper()
    gender = str(row.get("gender") or "").strip().lower()
    return {
        "wetsuit_id": row.get("wetsuit_id", ""),
        "number": str(row.get("number", "")).strip(),
        "size": size if size in WETSUIT_SIZES else None,
        "gender": gender if gender in WETSUIT_GENDERS else None,
        "is_active": _is_active(row),
    }


def _inventory_rows(sheet: SheetWrapper, tab: str, club_id: str) -> list[dict[str, str]]:
    id_column = INVENTORY_TABS[tab][0]
    return [
        row
        for row in sheet.read_optional_tab(tab)
        if row.get("club_id") == club_id and row.get(id_column)
    ]


def list_inventory(sheet: SheetWrapper, *, tab: str, club_id: str, include_inactive: bool = True) -> list[dict[str, Any]]:
    to_ref = board_ref if tab == "boards" else wetsuit_ref
    items = [to_ref(row) for row in _inventory_rows(sheet, tab, club_id)]
    if not include_inactive:
        items = [item for item in items if item["is_active"]]
    items.sort(key=lambda item: (not item["is_active"], _number_sort_key(item["number"])))
    return items


def inventory_maps(sheet: SheetWrapper, club_id: str) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    boards = {row["board_id"]: board_ref(row) for row in _inventory_rows(sheet, "boards", club_id)}
    wetsuits = {row["wetsuit_id"]: wetsuit_ref(row) for row in _inventory_rows(sheet, "wetsuits", club_id)}
    return boards, wetsuits


def _require_tab(sheet: SheetWrapper, tab: str) -> None:
    if sheet.get_headers(tab) is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"В Google Таблице нет вкладки «{tab}». {MIGRATION_HINT}",
        )


def _serialize_inventory_fields(fields: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in fields.items():
        if isinstance(value, bool):
            out[key] = "true" if value else "false"
        elif value is None:
            out[key] = ""
        else:
            out[key] = str(value).strip()
    if "length_cm" in out and out["length_cm"] in {"0", ""}:
        out["length_cm"] = ""
    return out


def _assert_unique_number(rows: Iterable[dict[str, str]], tab: str, number: str, *, except_id: str | None = None) -> None:
    id_column = INVENTORY_TABS[tab][0]
    wanted = _norm_number(number)
    for row in rows:
        if except_id and row.get(id_column) == except_id:
            continue
        if _norm_number(row.get("number")) == wanted:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"{INVENTORY_LABELS[tab]} № {str(number).strip()} уже есть в справочнике.",
            )


def create_inventory_item(sheet: SheetWrapper, *, tab: str, club_id: str, fields: dict[str, Any], actor: str) -> dict[str, Any]:
    _require_tab(sheet, tab)
    id_column, prefix = INVENTORY_TABS[tab]
    rows = _inventory_rows(sheet, tab, club_id)
    _assert_unique_number(rows, tab, str(fields.get("number", "")))
    now = _now_iso()
    item_id = f"{prefix}_{uuid4().hex[:8]}"
    row = {
        id_column: item_id,
        "club_id": club_id,
        **_serialize_inventory_fields(fields),
        "created_at": now,
        "updated_at": now,
    }
    row.setdefault("is_active", "true")
    sheet.append_row(tab, row, unique_key=id_column)
    sheet.write_audit("inventory_created", tab, item_id, row, actor=actor)
    return board_ref(row) if tab == "boards" else wetsuit_ref(row)


def update_inventory_item(
    sheet: SheetWrapper,
    *,
    tab: str,
    club_id: str,
    item_id: str,
    fields: dict[str, Any],
    actor: str,
) -> dict[str, Any]:
    _require_tab(sheet, tab)
    id_column, _ = INVENTORY_TABS[tab]
    rows = _inventory_rows(sheet, tab, club_id)
    current = next((row for row in rows if row.get(id_column) == item_id), None)
    if current is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=INVENTORY_NOT_FOUND[tab])
    if fields.get("number") is not None:
        _assert_unique_number(rows, tab, str(fields["number"]), except_id=item_id)
    patch = _serialize_inventory_fields(fields)
    patch["updated_at"] = _now_iso()
    sheet.update_by_id(tab, id_column, item_id, patch, actor=actor)
    action = "inventory_deactivated" if patch.get("is_active") == "false" else "inventory_updated"
    sheet.write_audit(action, tab, item_id, {"before": dict(current), "after": patch}, actor=actor)
    merged = {**current, **patch}
    return board_ref(merged) if tab == "boards" else wetsuit_ref(merged)


# ---------------------------------------------------------------------------
# «Как в прошлый раз»
# ---------------------------------------------------------------------------


def _has_equipment(row: dict[str, str]) -> bool:
    return any(str(row.get(column) or "").strip() for column in ("wetsuit_id", "board_id", "drink"))


def _drink(value: Any) -> str | None:
    text = str(value or "").strip().lower()
    return text if text in DRINK_CHOICES else None


def _ref_or_placeholder(kind: str, item_id: str, refs: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    if not item_id:
        return None
    ref = refs.get(item_id)
    if ref is not None:
        return dict(ref)
    # Вещь удалили из справочника вручную: показываем без номера, а не падаем.
    return {f"{kind}_id": item_id, "number": "", "is_active": False}


class EquipmentContext:
    """Индекс истории выдач по клиентам, построенный из уже прочитанных строк."""

    def __init__(
        self,
        *,
        boards: dict[str, dict[str, Any]],
        wetsuits: dict[str, dict[str, Any]],
        staff_names: dict[str, str],
        clients: dict[str, dict[str, str]],
        booking_rows: Iterable[dict[str, str]],
    ) -> None:
        self.boards = boards
        self.wetsuits = wetsuits
        self.staff_names = staff_names
        self.clients = clients
        self.reset_at = {client_id: str(row.get("prefs_reset_at") or "").strip() for client_id, row in clients.items()}
        self.history: dict[str, list[dict[str, str]]] = {}
        for row in booking_rows:
            if row.get("status") in VISITED_STATUSES and row.get("client_id"):
                self.history.setdefault(row["client_id"], []).append(row)
        for rows in self.history.values():
            rows.sort(key=lambda row: (row.get("date", ""), row.get("time", ""), row.get("booking_id", "")))

    def last_time_for(self, *, client_id: str, before_date: str, before_time: str, exclude_booking_id: str) -> tuple[dict[str, Any] | None, int]:
        reset_at = self.reset_at.get(client_id, "")
        visits_before = 0
        last_row: dict[str, str] | None = None
        cutoff = (str(before_date), str(before_time))
        for row in self.history.get(client_id, []):
            if row.get("booking_id") == exclude_booking_id:
                continue
            if (row.get("date", ""), row.get("time", "")) >= cutoff:
                break
            visits_before += 1
            if not _has_equipment(row):
                continue
            stamp = str(row.get("equipment_issued_at") or row.get("date") or "")
            if reset_at and stamp <= reset_at:
                continue
            last_row = row
        if last_row is None:
            return None, visits_before
        ride_type = last_row.get("ride_type") or ""
        return (
            {
                "booking_id": last_row.get("booking_id", ""),
                "date": last_row.get("date", ""),
                "time": last_row.get("time", ""),
                "ride_type": ride_type if ride_type in RIDE_KINDS else None,
                "wetsuit": _ref_or_placeholder("wetsuit", str(last_row.get("wetsuit_id") or "").strip(), self.wetsuits),
                "board": _ref_or_placeholder("board", str(last_row.get("board_id") or "").strip(), self.boards),
                "drink": _drink(last_row.get("drink")),
                "issued_by_name": self.staff_names.get(str(last_row.get("equipment_issued_by") or ""), ""),
                "issued_at": str(last_row.get("equipment_issued_at") or ""),
                "visits_before": visits_before,
            },
            visits_before,
        )

    def enrich(self, item: dict[str, Any]) -> dict[str, Any]:
        item["wetsuit"] = _ref_or_placeholder("wetsuit", str(item.get("wetsuit_id") or ""), self.wetsuits)
        item["board"] = _ref_or_placeholder("board", str(item.get("board_id") or ""), self.boards)
        item["equipment_issued_by_name"] = self.staff_names.get(str(item.get("equipment_issued_by") or ""), "")
        last_time, visits_before = self.last_time_for(
            client_id=str(item.get("client_id", "")),
            before_date=str(item.get("date", "")),
            before_time=str(item.get("time", "")),
            exclude_booking_id=str(item.get("booking_id", "")),
        )
        item["last_time"] = last_time
        item["visits_before"] = visits_before
        return item


def build_context(
    sheet: SheetWrapper,
    *,
    club_id: str,
    clients: dict[str, dict[str, str]],
    booking_rows: Iterable[dict[str, str]],
) -> EquipmentContext:
    boards, wetsuits = inventory_maps(sheet, club_id)
    staff_names = {
        row.get("staff_user_id", ""): row.get("full_name", "")
        for row in sheet.read_tab("staff_users")
        if row.get("club_id") in {club_id, "", None}
    }
    return EquipmentContext(
        boards=boards,
        wetsuits=wetsuits,
        staff_names=staff_names,
        clients=clients,
        booking_rows=[row for row in booking_rows if row.get("club_id") == club_id],
    )


def booking_equipment_fields(row: dict[str, str]) -> dict[str, Any]:
    """Сырые поля снаряжения из строки bookings (на старых Таблицах — пусто)."""
    return {
        "wetsuit_id": str(row.get("wetsuit_id") or "").strip() or None,
        "board_id": str(row.get("board_id") or "").strip() or None,
        "drink": _drink(row.get("drink")),
        "equipment_issued_by": str(row.get("equipment_issued_by") or ""),
        "equipment_issued_at": str(row.get("equipment_issued_at") or ""),
    }


def redact_for_role(item: dict[str, Any], role: str) -> dict[str, Any]:
    """Маркетинг не видит снаряжение совсем, пилот — только доску."""
    if role == "marketing_read":
        for field in EQUIPMENT_ITEM_FIELDS:
            item[field] = "" if field in {"equipment_issued_by", "equipment_issued_by_name", "equipment_issued_at"} else None
        return item
    if role == "pilot":
        item["wetsuit_id"] = None
        item["wetsuit"] = None
        item["drink"] = None
        item["equipment_issued_by"] = ""
        item["equipment_issued_by_name"] = ""
        last_time = item.get("last_time")
        if isinstance(last_time, dict):
            item["last_time"] = {
                **last_time,
                "wetsuit": None,
                "drink": None,
                "issued_by_name": "",
            }
    return item


def _time_minutes(text: str) -> int:
    try:
        hours, minutes = str(text or "0:0").split(":")[:2]
        return int(hours) * 60 + int(minutes)
    except ValueError:
        return -10_000


def find_conflicts(
    booking_rows: Iterable[dict[str, str]],
    target: dict[str, str],
    *,
    boards: dict[str, dict[str, Any]],
    wetsuits: dict[str, dict[str, Any]],
    clients: dict[str, dict[str, str]],
) -> list[str]:
    """Предупреждения (не блокировки): та же вещь выдана на пересекающуюся запись в пределах часа."""
    wetsuit_id = str(target.get("wetsuit_id") or "").strip()
    board_id = str(target.get("board_id") or "").strip()
    if not wetsuit_id and not board_id:
        return []
    target_slots = set(iter_booking_slots(target))
    target_start = _time_minutes(target.get("time", ""))
    warnings: list[str] = []
    for other in booking_rows:
        if other.get("booking_id") == target.get("booking_id"):
            continue
        if other.get("club_id") != target.get("club_id") or other.get("date") != target.get("date"):
            continue
        if other.get("status") in NO_EQUIPMENT_STATUSES:
            continue
        overlaps = bool(target_slots & set(iter_booking_slots(other))) or abs(_time_minutes(other.get("time", "")) - target_start) < 60
        if not overlaps:
            continue
        who = clients.get(other.get("client_id", ""), {}).get("full_name", "") or "другой клиент"
        when = other.get("time", "")
        if wetsuit_id and str(other.get("wetsuit_id") or "").strip() == wetsuit_id:
            number = wetsuits.get(wetsuit_id, {}).get("number", "")
            warnings.append(f"Гидрокостюм № {number} уже выдан на {when} ({who}). Проверьте, что его вернули.")
        if board_id and str(other.get("board_id") or "").strip() == board_id:
            number = boards.get(board_id, {}).get("number", "")
            warnings.append(f"Доска № {number} уже выдана на {when} ({who}). Проверьте, что её вернули.")
    return warnings


def _require_booking_columns(sheet: SheetWrapper) -> None:
    headers = sheet.get_headers("bookings")
    if headers is None:
        return
    missing = [column for column in EQUIPMENT_COLUMNS if column not in headers]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Во вкладке bookings нет колонок {', '.join(missing)}. {MIGRATION_HINT}",
        )


def _load(sheet: SheetWrapper, club_id: str) -> tuple[dict[str, dict[str, str]], list[dict[str, str]]]:
    clients = {row.get("client_id", ""): row for row in sheet.read_tab("clients") if row.get("club_id") == club_id}
    rows = [row for row in sheet.read_tab("bookings") if row.get("club_id") == club_id]
    return clients, rows


def _find_row(rows: list[dict[str, str]], booking_id: str) -> dict[str, str]:
    row = next((row for row in rows if row.get("booking_id") == booking_id), None)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Запись не найдена")
    return row


def _assert_can_edit(row: dict[str, str], *, role: str, actor: str, fields: dict[str, Any]) -> None:
    if row.get("status") in NO_EQUIPMENT_STATUSES:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Запись отменена — снаряжение не выдаётся.")
    if role == "coach":
        own = parse_bool(row.get("coach_required")) and row.get("coach_user_id") == actor
        if not own:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Тренер меняет доску только в своих записях.")
        if any(key != "board_id" for key in fields):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Тренер может менять только доску.")


def _validate_ref(kind: str, value: str, refs: dict[str, dict[str, Any]], current: str) -> None:
    if not value or value == current:
        return
    ref = refs.get(value)
    if ref is None or not ref.get("is_active"):
        detail = (
            "Гидрокостюм не найден в справочнике или выведен из оборота."
            if kind == "wetsuit"
            else "Доска не найдена в справочнике или выведена из оборота."
        )
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


def _item_for_row(
    sheet: SheetWrapper,
    *,
    club_id: str,
    row: dict[str, str],
    rows: list[dict[str, str]],
    clients: dict[str, dict[str, str]],
    ctx: EquipmentContext,
) -> dict[str, Any]:
    from .bookings import _booking_to_item  # локальный импорт: bookings импортирует этот модуль
    from .payments import payment_summaries_by_booking

    payments = [payment for payment in sheet.read_tab("payments") if payment.get("club_id") == club_id]
    summary = payment_summaries_by_booking([row], payments).get(row.get("booking_id", ""))
    return ctx.enrich(_booking_to_item(row, clients, summary))


def update_equipment(
    sheet: SheetWrapper,
    *,
    club_id: str,
    booking_id: str,
    fields: dict[str, Any],
    actor: str,
    role: str,
    extra_warnings: list[str] | None = None,
    audit_action: str = "equipment_issued",
) -> tuple[dict[str, Any], list[str]]:
    clients, rows = _load(sheet, club_id)
    row = _find_row(rows, booking_id)
    _assert_can_edit(row, role=role, actor=actor, fields=fields)
    _require_booking_columns(sheet)
    boards, wetsuits = inventory_maps(sheet, club_id)

    patch: dict[str, str] = {}
    if "wetsuit_id" in fields:
        value = str(fields["wetsuit_id"] or "").strip()
        _validate_ref("wetsuit", value, wetsuits, str(row.get("wetsuit_id") or ""))
        patch["wetsuit_id"] = value
    if "board_id" in fields:
        value = str(fields["board_id"] or "").strip()
        _validate_ref("board", value, boards, str(row.get("board_id") or ""))
        patch["board_id"] = value
    if "drink" in fields:
        value = str(fields["drink"] or "").strip().lower()
        if value and value not in DRINK_CHOICES:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Напиток: кофе, шоколад или «не нужно».")
        patch["drink"] = value
    if not patch:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Нечего сохранять: укажите гидрокостюм, доску или напиток.")

    updated_row = {**row, **patch}
    if _has_equipment(updated_row):
        patch["equipment_issued_by"] = actor
        patch["equipment_issued_at"] = _now_iso()
    else:
        patch["equipment_issued_by"] = ""
        patch["equipment_issued_at"] = ""
    updated_row = {**row, **patch}

    sheet.update_by_id("bookings", "booking_id", booking_id, patch, actor=actor)
    before = {column: str(row.get(column) or "") for column in EQUIPMENT_COLUMNS}
    sheet.write_audit(audit_action, "booking", booking_id, {"before": before, "after": patch}, actor=actor)

    rows = [updated_row if other.get("booking_id") == booking_id else other for other in rows]
    warnings = list(extra_warnings or []) + find_conflicts(rows, updated_row, boards=boards, wetsuits=wetsuits, clients=clients)
    ctx = build_context(sheet, club_id=club_id, clients=clients, booking_rows=rows)
    item = _item_for_row(sheet, club_id=club_id, row=updated_row, rows=rows, clients=clients, ctx=ctx)
    return item, warnings


def repeat_last_equipment(
    sheet: SheetWrapper,
    *,
    club_id: str,
    booking_id: str,
    actor: str,
    role: str,
) -> tuple[dict[str, Any], list[str]]:
    clients, rows = _load(sheet, club_id)
    row = _find_row(rows, booking_id)
    ctx = build_context(sheet, club_id=club_id, clients=clients, booking_rows=rows)
    last_time, _ = ctx.last_time_for(
        client_id=row.get("client_id", ""),
        before_date=row.get("date", ""),
        before_time=row.get("time", ""),
        exclude_booking_id=booking_id,
    )
    if not last_time:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="У клиента нет прошлых выдач — заполните вручную.")

    fields: dict[str, Any] = {}
    skipped: list[str] = []
    wetsuit = last_time.get("wetsuit")
    if wetsuit and role != "coach":
        if wetsuit.get("is_active"):
            fields["wetsuit_id"] = wetsuit["wetsuit_id"]
        else:
            skipped.append(f"Гидрокостюм № {wetsuit.get('number') or '—'} выведен из оборота — выберите другой.")
    board = last_time.get("board")
    if board:
        if board.get("is_active"):
            fields["board_id"] = board["board_id"]
        else:
            skipped.append(f"Доска № {board.get('number') or '—'} выведена из оборота — выберите другую.")
    if last_time.get("drink") and role != "coach":
        fields["drink"] = last_time["drink"]
    if not fields:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=" ".join(skipped) or "Повторять нечего — заполните вручную.")
    return update_equipment(
        sheet,
        club_id=club_id,
        booking_id=booking_id,
        fields=fields,
        actor=actor,
        role=role,
        extra_warnings=skipped,
        audit_action="equipment_repeat_last",
    )


def reset_client_prefs(sheet: SheetWrapper, *, club_id: str, client_id: str, actor: str) -> dict[str, str]:
    client = next(
        (row for row in sheet.read_tab("clients") if row.get("club_id") == club_id and row.get("client_id") == client_id),
        None,
    )
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Клиент не найден")
    headers = sheet.get_headers("clients")
    if headers is not None and "prefs_reset_at" not in headers:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Во вкладке clients нет колонки prefs_reset_at. {MIGRATION_HINT}",
        )
    now = _now_iso()
    sheet.update_by_id("clients", "client_id", client_id, {"prefs_reset_at": now}, actor=actor)
    sheet.write_audit("client_prefs_reset", "client", client_id, {"prefs_reset_at": now}, actor=actor)
    return {"client_id": client_id, "prefs_reset_at": now}
