"""Start owned, isolated demo processes and run browser regressions."""
from __future__ import annotations

import argparse
from datetime import datetime
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
from urllib.request import ProxyHandler, build_opener
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "icebeach-wakeclub/apps/dashboard"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-port", type=int, default=18001)
    parser.add_argument("--dashboard-port", type=int, default=15175)
    parser.add_argument("--chromium", default="")
    args = parser.parse_args()
    for port in (args.api_port, args.dashboard_port):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", port))

    node = shutil.which("node")
    if not node:
        raise RuntimeError("Node is required")
    playwright = ROOT / "scripts/browser-qa/node_modules/playwright"
    env = dict(os.environ)
    env.update(
        PYTHONPATH=str(ROOT / "icebeach-wakeclub"),
        APP_ENV="demo",
        SPREADSHEET_ID="demo-sheet",
        GOOGLE_SERVICE_ACCOUNT_JSON=str(ROOT / "scripts/demo_local.py"),
        SESSION_SECRET="demo-secret-not-for-production",
        AUTH_DEBUG_CODE_IN_RESPONSE="true",
        TELEGRAM_BOT_TOKEN="",
        OTP_DELIVERY_WEBHOOK_URL="",
        OTP_DELIVERY_WEBHOOK_TOKEN="",
        DEMO_DATE=datetime.now(ZoneInfo("Europe/Moscow")).date().isoformat(),
        QA_ALLOW_DEMO="true",
        QA_DASHBOARD_URL=f"http://127.0.0.1:{args.dashboard_port}",
        VITE_API_BASE_URL="/api",
        VITE_API_PROXY_TARGET=f"http://127.0.0.1:{args.api_port}",
        SHIFT_QA_PLAYWRIGHT_PATH=str(playwright),
    )
    chromium = args.chromium or subprocess.check_output(
        [node, "-e", "console.log(require('./scripts/browser-qa/node_modules/playwright').chromium.executablePath())"],
        cwd=ROOT, text=True,
    ).strip()
    env["QA_CHROMIUM_EXECUTABLE"] = chromium
    env["SHIFT_QA_CHROMIUM"] = chromium
    logs = ROOT / ".runlogs"
    logs.mkdir(exist_ok=True)
    children = []
    try:
        with (logs / "owned-api.log").open("w", encoding="utf-8") as api_log, (logs / "owned-dashboard.log").open("w", encoding="utf-8") as web_log:
            children.append(subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "scripts.demo_local:app", "--host", "127.0.0.1", "--port", str(args.api_port)],
                cwd=ROOT, env=env, stdout=api_log, stderr=subprocess.STDOUT,
            ))
            children.append(subprocess.Popen(
                [node, "node_modules/vite/bin/vite.js", "--host", "127.0.0.1", "--port", str(args.dashboard_port), "--strictPort"],
                cwd=DASHBOARD, env=env, stdout=web_log, stderr=subprocess.STDOUT,
            ))
            opener = build_opener(ProxyHandler({}))
            for url in (env["VITE_API_PROXY_TARGET"] + "/health", env["QA_DASHBOARD_URL"] + "/login"):
                deadline = time.monotonic() + 45
                while True:
                    if any(child.poll() is not None for child in children):
                        raise RuntimeError("A QA child process exited; inspect .runlogs/owned-*.log")
                    try:
                        with opener.open(url, timeout=2) as response:
                            if response.status == 200:
                                break
                    except OSError:
                        pass
                    if time.monotonic() >= deadline:
                        raise RuntimeError(f"Local QA startup timeout: {url}")
                    time.sleep(0.2)
            commands = [
                ([node, "scripts/browser_scenarios.cjs"], ROOT),
                ([node, "tests/shift-timer-regression/run.mjs"], DASHBOARD),
                ([node, "--test", "tests/shift-timer-regression/date.test.mjs"], DASHBOARD),
            ]
            failed = False
            for command, cwd in commands:
                result = subprocess.run(command, cwd=cwd, env=env, check=False)
                failed |= result.returncode != 0
            return int(failed)
    finally:
        # Terminate only handles returned by this runner's Popen calls.
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=10)


if __name__ == "__main__":
    raise SystemExit(main())
