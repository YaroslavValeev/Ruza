from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


@dataclass
class CheckResult:
    level: str
    code: str
    message: str


class ProofRunner:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.results: list[CheckResult] = []

    def pass_(self, code: str, message: str) -> None:
        self.results.append(CheckResult("PASS", code, message))

    def warn(self, code: str, message: str) -> None:
        self.results.append(CheckResult("WARN", code, message))

    def blocker(self, code: str, message: str) -> None:
        self.results.append(CheckResult("BLOCKER", code, message))

    def run(self) -> int:
        print("=== RUZA STAGING / PRODUCTION PROOF ===")
        print(f"API: {self.args.api_base_url}")
        print(f"Dashboard: {self.args.dashboard_url}")
        print("")

        self._check_https("api.https", self.args.api_base_url)
        self._check_https("dashboard.https", self.args.dashboard_url)
        self._check_dashboard()
        self._check_health()
        self._check_cors()
        self._check_authenticated_preflight()
        self._check_otp_probe()

        blockers = sum(1 for result in self.results if result.level == "BLOCKER")
        warnings = sum(1 for result in self.results if result.level == "WARN")
        for result in self.results:
            print(f"[{result.level}] {result.code}: {result.message}")
        print("")
        print(f"SUMMARY blockers={blockers} warnings={warnings}")
        return 1 if blockers else 0

    def _check_https(self, code: str, url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme == "https":
            self.pass_(code, "URL uses HTTPS")
            return
        if self.args.allow_http_for_local and parsed.hostname in {"127.0.0.1", "localhost"}:
            self.warn(code, "HTTP allowed for local-only proof")
            return
        self.blocker(code, "production/staging proof requires HTTPS")

    def _check_dashboard(self) -> None:
        try:
            status, headers, body = _request("GET", self.args.dashboard_url)
        except RuntimeError as exc:
            self.blocker("dashboard.http", str(exc))
            return
        if status != HTTPStatus.OK:
            self.blocker("dashboard.http", f"expected 200, got {status}")
            return
        text = body.decode("utf-8", errors="ignore")
        if "Ice Beach" in text or "<html" in text.lower():
            self.pass_("dashboard.http", "dashboard responds with HTML")
        else:
            self.blocker("dashboard.http", "dashboard response is not recognizable HTML")

    def _check_health(self) -> None:
        try:
            status, _headers, body = _request("GET", _join_url(self.args.api_base_url, "/health"))
        except RuntimeError as exc:
            self.blocker("api.health", str(exc))
            return
        if status != HTTPStatus.OK:
            self.blocker("api.health", f"expected 200, got {status}")
            return
        try:
            payload = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            self.blocker("api.health", "health response is not JSON")
            return
        if payload.get("status") != "ok":
            self.blocker("api.health", f"unexpected status={payload.get('status')!r}")
            return
        app_name = payload.get("app")
        if app_name and app_name != "icebeach-wakeclub-api":
            self.blocker("api.health", f"unexpected app={app_name!r}")
            return
        self.pass_("api.health", "health status is ok")

    def _check_cors(self) -> None:
        origin = self.args.origin or _origin(self.args.dashboard_url)
        headers = {
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        }
        try:
            status, response_headers, _body = _request(
                "OPTIONS",
                _join_url(self.args.api_base_url, "/auth/request-code"),
                headers=headers,
            )
        except RuntimeError as exc:
            self.blocker("cors.preflight", str(exc))
            return
        if status not in {HTTPStatus.OK, HTTPStatus.NO_CONTENT}:
            self.blocker("cors.preflight", f"expected 200/204, got {status}")
            return
        allow_origin = response_headers.get("Access-Control-Allow-Origin")
        allow_credentials = response_headers.get("Access-Control-Allow-Credentials")
        if allow_origin != origin:
            self.blocker("cors.origin", f"origin {origin} is not allowed")
        else:
            self.pass_("cors.origin", f"origin allowed: {origin}")
        if str(allow_credentials).lower() != "true":
            self.blocker("cors.credentials", "credentials are not allowed")
        else:
            self.pass_("cors.credentials", "credentials allowed")

    def _check_authenticated_preflight(self) -> None:
        if not self.args.session_cookie:
            self.warn("preflight.authenticated", "skipped; pass session cookie after staff login")
            return
        cookie = self.args.session_cookie
        if "=" not in cookie:
            cookie = f"{self.args.session_cookie_name}={cookie}"
        url = _join_url(self.args.api_base_url, f"/preflight/summary?date={self.args.date}")
        try:
            status, _headers, body = _request("GET", url, headers={"Cookie": cookie})
        except RuntimeError as exc:
            self.blocker("preflight.authenticated", str(exc))
            return
        if status != HTTPStatus.OK:
            self.blocker("preflight.authenticated", f"expected 200, got {status}")
            return
        try:
            payload = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            self.blocker("preflight.authenticated", "preflight response is not JSON")
            return
        blockers = int(payload.get("blockers", 0) or 0)
        if blockers:
            self.blocker("preflight.authenticated", f"preflight blockers={blockers}")
        else:
            self.pass_("preflight.authenticated", f"preflight blockers=0 for {self.args.date}")

    def _check_otp_probe(self) -> None:
        if not self.args.probe_otp_request:
            self.warn("otp.request", "skipped; use --probe-otp-request only when real OTP side effect is allowed")
            return
        if not self.args.staff_user_id or not self.args.phone:
            self.blocker("otp.request", "--staff-user-id and --phone are required with --probe-otp-request")
            return
        body = json.dumps({"staff_user_id": self.args.staff_user_id, "phone": self.args.phone}).encode("utf-8")
        try:
            status, _headers, response_body = _request(
                "POST",
                _join_url(self.args.api_base_url, "/auth/request-code"),
                headers={"Content-Type": "application/json"},
                body=body,
            )
        except RuntimeError as exc:
            self.blocker("otp.request", str(exc))
            return
        if status != HTTPStatus.OK:
            self.blocker("otp.request", f"expected 200, got {status}")
            return
        try:
            payload = json.loads(response_body.decode("utf-8"))
        except json.JSONDecodeError:
            self.blocker("otp.request", "OTP response is not JSON")
            return
        if payload.get("debug_code"):
            self.blocker("otp.request", "production OTP response exposes debug_code")
        else:
            self.pass_("otp.request", "OTP request accepted without debug_code")


def _request(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
) -> tuple[int, Any, bytes]:
    request = Request(url, data=body, headers=headers or {}, method=method)
    try:
        with urlopen(request, timeout=15) as response:
            return response.status, response.headers, response.read()
    except HTTPError as exc:
        return exc.code, exc.headers, exc.read()
    except (TimeoutError, URLError, OSError) as exc:
        raise RuntimeError(str(exc)) from exc


def _join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _origin(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return url.rstrip("/")
    return f"{parsed.scheme}://{parsed.netloc}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prove Ruza staging/production HTTP, HTTPS and CORS readiness.")
    parser.add_argument("--api-base-url", required=True)
    parser.add_argument("--dashboard-url", required=True)
    parser.add_argument("--date", default="2026-06-01")
    parser.add_argument("--origin", default="")
    parser.add_argument("--session-cookie", default="")
    parser.add_argument("--session-cookie-name", default="icebeach_session")
    parser.add_argument("--allow-http-for-local", action="store_true")
    parser.add_argument("--probe-otp-request", action="store_true")
    parser.add_argument("--staff-user-id", default="")
    parser.add_argument("--phone", default="")
    return parser.parse_args()


def main() -> int:
    return ProofRunner(parse_args()).run()


if __name__ == "__main__":
    sys.exit(main())
