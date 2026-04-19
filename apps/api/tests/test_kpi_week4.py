from apps.api.app.services_ops import kpi_drilldown, kpi_view


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
            "bookings": [
                {
                    "booking_id": "bk_done",
                    "date": "2026-05-14",
                    "time": "10:00",
                    "boat_id": "boat_01",
                    "client_id": "c1",
                    "status": "done",
                    "total_price": "5000",
                    "coach_required": "TRUE",
                },
                {
                    "booking_id": "bk_no_show",
                    "date": "2026-05-14",
                    "time": "11:00",
                    "boat_id": "boat_01",
                    "client_id": "c2",
                    "status": "no_show",
                    "total_price": "0",
                    "coach_required": "FALSE",
                },
            ],
            "analytics_daily": [],
            "checkins": [],
            "slot_overrides": [],
            "audit_log": [],
        }

    def validate_required_columns(self, tab, required):
        existing = set(self.tabs[tab][0].keys()) if self.tabs.get(tab) else set(required)
        return [c for c in required if c not in existing]

    def find(self, tab, predicate):
        return [row for row in self.tabs.get(tab, []) if predicate(row)]

    def append_row(self, tab, row):
        self.tabs.setdefault(tab, []).append(row)

    def update_by_id(self, tab, id_field, id_value, patch):
        for row in self.tabs.get(tab, []):
            if row.get(id_field) == id_value:
                row.update(patch)
                return True
        return False

    def write_audit(self, **kwargs):
        self.tabs["audit_log"].append(kwargs)


def test_kpi_today_computes_and_upserts_daily():
    sheets = MockSheets()
    result = kpi_view(sheets=sheets, period="today", today_iso="2026-05-14")
    assert result["metrics"]["revenue_estimate"] == 5000.0
    assert result["metrics"]["no_show_rate"] == 50.0
    assert len(sheets.tabs["analytics_daily"]) == 1
    assert len(sheets.tabs["audit_log"]) == 1


def test_kpi_drilldown_returns_metric_rows():
    sheets = MockSheets()
    detail = kpi_drilldown(
        sheets=sheets,
        period="today",
        metric="revenue_estimate",
        today_iso="2026-05-14",
    )
    assert detail["count"] == 1
    assert detail["bookings"][0]["booking_id"] == "bk_done"
