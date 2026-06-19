"""CLI prototype: voice FSM + API check-in (requires running API + session cookie manual)."""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request

from .fsm import run_cli


def post_checkin(api_base: str, phone: str, date: str, session_cookie: str) -> None:
    payload = json.dumps({"method": "phone", "phone": phone, "date": date, "status": "arrived"}).encode("utf-8")
    request = urllib.request.Request(
        f"{api_base.rstrip('/')}/checkins",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Cookie": session_cookie,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            body = response.read().decode("utf-8")
            print(f"API check-in OK: {body}")
    except urllib.error.HTTPError as exc:
        print(f"API check-in failed: {exc.code} {exc.read().decode('utf-8', errors='ignore')}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ice Beach voice check-in prototype")
    parser.add_argument("--api", default=os.getenv("API_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--date", default=os.getenv("CHECKIN_DATE", "2026-06-01"))
    parser.add_argument("--session-cookie", default=os.getenv("SESSION_COOKIE", ""))
    args = parser.parse_args()

    def on_checkin(phone: str) -> None:
        if not args.session_cookie:
            print("SESSION_COOKIE not set — skipping API call (FSM demo only).")
            return
        post_checkin(args.api, phone, args.date, args.session_cookie)

    run_cli(on_checkin=on_checkin)


if __name__ == "__main__":
    main()
