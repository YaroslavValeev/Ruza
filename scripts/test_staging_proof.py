from __future__ import annotations

import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class ProofHandler(BaseHTTPRequestHandler):
    server_version = "RuzaProofTest/1.0"

    def do_GET(self) -> None:
        if self.path == "/dashboard":
            self._send(200, b"<!doctype html><html><title>Ice Beach Dashboard</title></html>", "text/html")
            return
        if self.path == "/health":
            self._send_json(200, {"status": "ok", "app": "icebeach-wakeclub-api"})
            return
        if self.path.startswith("/preflight/summary"):
            cookie = self.headers.get("Cookie", "")
            if "icebeach_session=test-session" not in cookie:
                self._send_json(401, {"detail": "Not authenticated"})
                return
            self._send_json(200, {"date": "2026-06-01", "blockers": 0, "warnings": 0, "checks": []})
            return
        self._send_json(404, {"detail": "Not found"})

    def do_OPTIONS(self) -> None:
        origin = self.headers.get("Origin", "")
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Credentials", "true")
        self.send_header("Access-Control-Allow-Headers", "content-type")
        self.send_header("Access-Control-Allow-Methods", "POST")
        self.end_headers()

    def do_POST(self) -> None:
        if self.path == "/auth/request-code":
            self._send_json(
                200,
                {
                    "delivery_channel": "sms",
                    "expires_in_seconds": 300,
                    "debug_code": None,
                    "staff_user_id": "staff_admin_001",
                    "full_name": "Admin",
                },
            )
            return
        self._send_json(404, {"detail": "Not found"})

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def _send_json(self, status: int, payload: dict[str, object]) -> None:
        self._send(status, json.dumps(payload).encode("utf-8"), "application/json")

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run_proof(*args: str) -> subprocess.CompletedProcess[str]:
    script = Path(__file__).with_name("staging_proof.py")
    return subprocess.run(
        [sys.executable, str(script), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def main() -> int:
    server = ThreadingHTTPServer(("127.0.0.1", 0), ProofHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"
    try:
        good = run_proof(
            "--api-base-url",
            base_url,
            "--dashboard-url",
            f"{base_url}/dashboard",
            "--allow-http-for-local",
            "--session-cookie",
            "test-session",
            "--probe-otp-request",
            "--staff-user-id",
            "staff_admin_001",
            "--phone",
            "+70000000000",
        )
        print(good.stdout)
        if good.returncode != 0 or "SUMMARY blockers=0" not in good.stdout:
            print("[BLOCKER] staging proof success case failed")
            return 1

        blocked = run_proof("--api-base-url", base_url, "--dashboard-url", f"{base_url}/dashboard")
        print(blocked.stdout)
        if blocked.returncode == 0 or "production/staging proof requires HTTPS" not in blocked.stdout:
            print("[BLOCKER] staging proof accepted HTTP without local override")
            return 1

        print("[PASS] staging proof behavior verified")
        return 0
    finally:
        server.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
