#!/usr/bin/env python3
"""Smoke the in-memory demo API (no Google Sheets).

[WSL2]
  PYTHONPATH="$PWD/icebeach-wakeclub" python3 scripts/smoke_demo.py

[PowerShell]
  $env:PYTHONPATH=(Resolve-Path .\\icebeach-wakeclub).Path
  python scripts\\smoke_demo.py
"""

from __future__ import annotations

import sys
from datetime import date

import httpx

BASE = "http://127.0.0.1:8000"
TODAY = date.today().isoformat()


def _fail(code: str, message: str) -> None:
    print(f"[FAIL] {code}: {message}")
    raise SystemExit(1)


def _pass(code: str, message: str) -> None:
    print(f"[PASS] {code}: {message}")


def _login(client: httpx.Client, phone: str) -> dict:
    requested = client.post("/auth/request-code", json={"phone": phone})
    if requested.status_code != 200:
        _fail("auth.request", f"{phone} -> {requested.status_code} {requested.text}")
    payload = requested.json()
    code = payload.get("debug_code")
    if not code:
        _fail("auth.debug_code", "debug OTP is empty; start scripts/demo_local.py, not production API")
    verified = client.post("/auth/verify-code", json={"phone": phone, "code": code})
    if verified.status_code != 200:
        _fail("auth.verify", f"{phone} -> {verified.status_code} {verified.text}")
    return verified.json()


def main() -> None:
    try:
        with httpx.Client(base_url=BASE, timeout=10.0) as client:
            health = client.get("/health")
            if health.status_code != 200 or health.json().get("status") != "ok":
                _fail("health", health.text)
            _pass("health", "ok")

            operator = _login(client, "+79990000001")
            _pass("login.operator", operator.get("role", ""))

            bookings = client.get("/bookings", params={"date": TODAY})
            if bookings.status_code != 200:
                _fail("bookings", bookings.text)
            rows = bookings.json()
            if not rows:
                _fail("bookings.seed", f"no demo bookings for {TODAY}")
            _pass("bookings.seed", f"{len(rows)} on {TODAY}")

            ready = next((row for row in rows if row.get("status") == "ready"), None)
            if ready is None:
                _fail("bookings.ready", "expected seeded ready booking")
            _pass("bookings.ready", ready["booking_id"])

            confirmed = next((row for row in rows if row.get("status") == "confirmed"), None)
            if confirmed and confirmed.get("client_phone"):
                arrived = client.post(
                    "/checkins",
                    json={
                        "method": "phone",
                        "phone": confirmed["client_phone"],
                        "date": TODAY,
                        "status": "arrived",
                        "booking_id": confirmed["booking_id"],
                    },
                )
                if arrived.status_code != 200:
                    _fail("checkin.arrived", arrived.text)
                _pass("checkin.arrived", confirmed["booking_id"])

            client.post("/auth/logout")
            pilot = _login(client, "+79990000002")
            _pass("login.pilot", pilot.get("role", ""))

            started = client.patch(
                f"/bookings/{ready['booking_id']}/status",
                json={"status": "in_progress"},
            )
            if started.status_code != 200:
                _fail("pilot.start", started.text)
            finished = client.patch(
                f"/bookings/{ready['booking_id']}/status",
                json={"status": "done"},
            )
            if finished.status_code != 200:
                _fail("pilot.done", finished.text)
            _pass("pilot.cycle", f"{ready['booking_id']} done")

            client.post("/auth/logout")
            admin = _login(client, "+79990000000")
            _pass("login.admin", admin.get("role", ""))
            kpi = client.get("/kpi/summary", params={"period": "day", "date_from": TODAY})
            if kpi.status_code != 200:
                _fail("kpi", kpi.text)
            sessions = kpi.json().get("sessions_count", 0)
            if sessions < 1:
                _fail("kpi.sessions", f"expected >=1 done session, got {sessions}")
            _pass("kpi.sessions", str(sessions))

            leads = client.get("/leads")
            if leads.status_code != 200:
                _fail("leads", leads.text)
            _pass("leads", str(len(leads.json())))
    except httpx.ConnectError:
        _fail("connect", "API не запущен. Сначала start-demo / demo_local.py")

    print("SUMMARY failures=0")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] unexpected: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
