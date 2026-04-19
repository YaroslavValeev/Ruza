from apps.api.app.services_ops import diagnostics_snapshot


class MockSheets:
    def __init__(self):
        self.tabs = {
            "staff_users": [{"staff_user_id": "a", "phone": "1", "role": "admin"}],
            "bookings": [{"booking_id": "b", "date": "2026-05-14", "time": "10:00", "boat_id": "boat_01", "status": "confirmed"}],
            "checkins": [{"checkin_id": "c", "booking_id": "b", "status": "arrived", "method": "manual"}],
            "audit_log": [{"ts": "x", "actor": "y", "action": "z", "entity": "e", "entity_id": "id", "diff_json": "{}"}],
            "analytics_daily": [{"date": "2026-05-14", "utilization_pct": 0, "revenue_estimate": 0, "coach_attach_rate": 0, "no_show_rate": 0, "new_clients_count": 0}],
        }

    def validate_required_columns(self, tab, required):
        existing = set(self.tabs[tab][0].keys())
        return [c for c in required if c not in existing]


def test_diagnostics_snapshot_ok():
    snapshot = diagnostics_snapshot(MockSheets(), app_version="0.3.0", cache_ttl_seconds=30)
    assert snapshot["status"] == "ok"
    assert snapshot["app_version"] == "0.3.0"
    assert snapshot["cache_ttl_seconds"] == 30
