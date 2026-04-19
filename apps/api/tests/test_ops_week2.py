from apps.api.app.services_ops import build_availability, create_booking


class MockSheets:
    def __init__(self):
        self.tabs = {
            "schedule": [
                {
                    "weekday": "thursday",
                    "time": "10:00",
                    "boat_id": "boat_01",
                    "capacity": "2",
                    "is_active": "TRUE",
                }
            ],
            "slot_overrides": [],
            "bookings": [],
            "audit_log": [],
        }

    def validate_required_columns(self, tab, required):
        existing = set(self.tabs[tab][0].keys()) if self.tabs.get(tab) else set(required)
        return [c for c in required if c not in existing]

    def find(self, tab, predicate):
        return [row for row in self.tabs.get(tab, []) if predicate(row)]

    def append_row(self, tab, row):
        self.tabs.setdefault(tab, []).append(row)

    def write_audit(self, **kwargs):
        self.tabs["audit_log"].append(kwargs)


def test_availability_for_empty_day_remaining_capacity():
    sheets = MockSheets()
    slots = build_availability(sheets, date_iso="2026-05-14")
    assert len(slots) == 1
    assert slots[0]["remaining"] == 2


def test_create_booking_is_idempotent_and_writes_audit():
    sheets = MockSheets()
    request = {
        "client_id": "client_1",
        "date": "2026-05-14",
        "time": "10:00",
        "boat_id": "boat_01",
        "coach_required": False,
        "price_base": 3000,
        "price_coach": 0,
        "coach_user_id": "",
    }

    first = create_booking(sheets=sheets, request=request, actor="staff_operator")
    second = create_booking(sheets=sheets, request=request, actor="staff_operator")

    assert first["idempotent_replay"] is False
    assert second["idempotent_replay"] is True
    assert len(sheets.tabs["bookings"]) == 1
    assert len(sheets.tabs["audit_log"]) == 1


def test_create_booking_fails_when_slot_full():
    sheets = MockSheets()
    for idx in range(2):
        sheets.tabs["bookings"].append(
            {
                "booking_id": f"bk_{idx}",
                "date": "2026-05-14",
                "time": "10:00",
                "boat_id": "boat_01",
                "client_id": f"client_{idx}",
                "status": "confirmed",
            }
        )

    request = {
        "client_id": "client_3",
        "date": "2026-05-14",
        "time": "10:00",
        "boat_id": "boat_01",
        "coach_required": False,
        "price_base": 3000,
        "price_coach": 0,
        "coach_user_id": "",
    }

    try:
        create_booking(sheets=sheets, request=request, actor="staff_operator")
        assert False, "Expected SLOT_FULL"
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 409
        assert exc.detail["code"] == "SLOT_FULL"
