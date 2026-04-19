from apps.api.app.services_ops import create_checkin, get_pilot_queue, update_booking_status


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
            "checkins": [],
            "bookings": [
                {
                    "booking_id": "bk_1",
                    "date": "2026-05-14",
                    "time": "10:00",
                    "boat_id": "boat_01",
                    "client_id": "89161117779",
                    "status": "confirmed",
                }
            ],
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

    def update_by_id(self, tab, id_field, id_value, patch):
        for row in self.tabs.get(tab, []):
            if row.get(id_field) == id_value:
                row.update(patch)
                return True
        return False


def test_checkin_updates_booking_and_audit():
    sheets = MockSheets()
    created = create_checkin(
        sheets=sheets,
        booking_id="bk_1",
        method="phone",
        status="arrived",
        actor="staff_operator",
    )
    assert created["idempotent_replay"] is False
    assert sheets.tabs["bookings"][0]["status"] == "checked_in"
    assert len(sheets.tabs["audit_log"]) == 2


def test_pilot_queue_contains_ready_state_and_masked_client():
    sheets = MockSheets()
    create_checkin(
        sheets=sheets,
        booking_id="bk_1",
        method="phone",
        status="ready",
        actor="staff_operator",
    )
    queue = get_pilot_queue(sheets=sheets, date_iso="2026-05-14", boat_id="boat_01")
    assert queue[0]["ready_state"] == "ready"
    assert "***" in queue[0]["client"]


def test_role_transition_forbidden_for_pilot_cancel():
    sheets = MockSheets()
    try:
        update_booking_status(
            sheets=sheets,
            booking_id="bk_1",
            new_status="cancelled",
            actor="staff_pilot",
            actor_role="pilot",
        )
        assert False, "Expected forbidden transition"
    except Exception as exc:
        assert exc.status_code == 403
        assert exc.detail["code"] == "FORBIDDEN"
