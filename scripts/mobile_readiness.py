from __future__ import annotations

import json
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_ROOT = REPO_ROOT / "icebeach-wakeclub" / "apps" / "dashboard"


blockers = 0


def pass_check(code: str, message: str) -> None:
    print(f"[PASS] {code}: {message}")


def blocker(code: str, message: str) -> None:
    global blockers
    blockers += 1
    print(f"[BLOCKER] {code}: {message}")


def read_text(path: Path) -> str:
    if not path.exists():
        blocker(f"file.{path.relative_to(REPO_ROOT)}", "missing")
        return ""
    return path.read_text(encoding="utf-8")


def require_contains(code: str, text: str, needle: str, message: str) -> None:
    if needle in text:
        pass_check(code, message)
    else:
        blocker(code, f"missing {needle!r}")


def check_index_html() -> None:
    html = read_text(DASHBOARD_ROOT / "index.html")
    if not html:
        return

    require_contains("mobile.viewport_fit", html, "viewport-fit=cover", "viewport supports iOS safe areas")
    require_contains("mobile.manifest_link", html, 'rel="manifest" href="/manifest.webmanifest"', "manifest is linked")
    require_contains("mobile.apple_capable", html, 'name="apple-mobile-web-app-capable" content="yes"', "iOS standalone mode is enabled")
    require_contains(
        "mobile.apple_status_bar",
        html,
        'name="apple-mobile-web-app-status-bar-style" content="black-translucent"',
        "iOS status bar style is configured",
    )
    require_contains("mobile.apple_touch_icon", html, 'rel="apple-touch-icon" href="/icons/icon-192.png"', "Apple touch icon is linked")
    require_contains("mobile.theme_color", html, 'name="theme-color"', "theme color is set")


def check_manifest() -> None:
    manifest_path = DASHBOARD_ROOT / "public" / "manifest.webmanifest"
    raw = read_text(manifest_path)
    if not raw:
        return

    try:
        manifest = json.loads(raw)
    except json.JSONDecodeError as exc:
        blocker("mobile.manifest_json", f"invalid JSON: {exc}")
        return

    expected = {
        "name": "Ice Beach Wake Club",
        "short_name": "Ice Beach",
        "start_url": "/m/pilot",
        "scope": "/",
        "display": "standalone",
        "orientation": "portrait",
    }
    for key, value in expected.items():
        actual = manifest.get(key)
        if actual == value:
            pass_check(f"mobile.manifest.{key}", f"{key}={value}")
        else:
            blocker(f"mobile.manifest.{key}", f"expected {value!r}, got {actual!r}")

    icons = manifest.get("icons", [])
    icon_sizes = {icon.get("sizes"): icon.get("src") for icon in icons if isinstance(icon, dict)}
    for size in ("192x192", "512x512"):
        src = icon_sizes.get(size)
        if not src:
            blocker(f"mobile.icon.{size}", "manifest icon is missing")
            continue
        icon_path = DASHBOARD_ROOT / "public" / src.lstrip("/")
        if icon_path.exists():
            pass_check(f"mobile.icon.{size}", f"{src} exists")
        else:
            blocker(f"mobile.icon.{size}", f"{src} does not exist")

    shortcut_urls = {
        shortcut.get("url")
        for shortcut in manifest.get("shortcuts", [])
        if isinstance(shortcut, dict)
    }
    for url in ("/m/pilot", "/m/owner"):
        if url in shortcut_urls:
            pass_check(f"mobile.shortcut.{url}", "shortcut is present")
        else:
            blocker(f"mobile.shortcut.{url}", "shortcut is missing")


def check_runtime_files() -> None:
    main = read_text(DASHBOARD_ROOT / "src" / "main.tsx")
    app_router = read_text(DASHBOARD_ROOT / "src" / "router" / "AppRouter.tsx")
    shell = read_text(DASHBOARD_ROOT / "src" / "mobile" / "MobileShell.tsx")
    install_page = read_text(DASHBOARD_ROOT / "src" / "mobile" / "MobileInstallPage.tsx")
    api_client = read_text(DASHBOARD_ROOT / "src" / "api" / "client.ts")
    nginx = read_text(DASHBOARD_ROOT / "nginx.conf")
    dockerfile = read_text(DASHBOARD_ROOT / "Dockerfile")
    env_example = read_text(DASHBOARD_ROOT / ".env.example")
    compose = read_text(REPO_ROOT / "docker-compose.yml")

    require_contains("mobile.service_worker_file", read_text(DASHBOARD_ROOT / "public" / "sw.js"), "caches.open", "service worker shell cache exists")
    require_contains("mobile.service_worker_registration", main, 'navigator.serviceWorker.register("/sw.js")', "service worker is registered")

    for route in ('path="pilot"', 'path="owner"', 'path="install"', 'path="/m/install"'):
        require_contains(f"mobile.route.{route}", app_router, route, "mobile route is wired")

    require_contains("mobile.safe_area_top", shell, "env(safe-area-inset-top)", "top safe-area inset is used")
    require_contains("mobile.safe_area_bottom", shell, "env(safe-area-inset-bottom)", "bottom safe-area inset is used")
    require_contains("mobile.dynamic_vh", shell, "min-h-[100dvh]", "dynamic viewport height is used")
    require_contains("mobile.touch_targets", shell, "min-h-[48px]", "mobile nav touch targets are at least 48px")

    require_contains("mobile.ios_copy", install_page, "Safari", "iOS install copy mentions Safari")
    require_contains("mobile.android_copy", install_page, "Android", "Android install copy is present")

    require_contains("mobile.api_relative_support", api_client, 'raw.startsWith("/")', "relative API base is supported")
    require_contains("mobile.api_cookie_credentials", api_client, 'credentials: "include"', "API requests include cookies")
    require_contains("mobile.api_lan_host_rewrite", api_client, "configured.hostname = browserHost", "LAN host rewrite avoids mobile loopback")

    require_contains("mobile.nginx_api_proxy", nginx, "location /api/", "dashboard nginx proxies /api")
    require_contains("mobile.nginx_api_upstream", nginx, "proxy_pass http://api:8000/", "dashboard nginx proxies to api service")
    require_contains("mobile.docker_default_api_base", dockerfile, "ARG VITE_API_BASE_URL=/api", "Docker build defaults to same-origin /api")
    require_contains("mobile.env_example_api_base", env_example, "VITE_API_BASE_URL=/api", "dashboard env example defaults to same-origin /api")
    require_contains("mobile.compose_api_base", compose, "VITE_API_BASE_URL: /api", "compose dashboard build arg uses same-origin /api")
    require_contains("mobile.compose_api_loopback", compose, '"127.0.0.1:8000:8000"', "API port is bound to loopback")
    require_contains("mobile.compose_dashboard_loopback", compose, '"127.0.0.1:5173:80"', "dashboard port is bound to loopback")
    if "./service-account.json:/run/secrets/service-account.json" in compose:
        blocker("mobile.compose_credentials", "production compose must not require a local service-account.json")
    else:
        pass_check("mobile.compose_credentials", "production compose accepts base64 credentials without a local file")


def check_no_visible_game_copy() -> None:
    pattern = re.compile(r"(Игрок|игрок|игров[а-яё]*)", re.IGNORECASE)
    scanned = 0
    offenders: list[str] = []
    for path in (DASHBOARD_ROOT / "src").rglob("*"):
        if path.suffix not in {".tsx", ".ts"}:
            continue
        scanned += 1
        text = path.read_text(encoding="utf-8")
        matches = pattern.findall(text)
        if matches:
            offenders.append(f"{path.relative_to(REPO_ROOT)}: {', '.join(sorted(set(matches)))}")

    if offenders:
        blocker("mobile.copy.training_terms", "visible source still contains game/player Russian copy:\n  " + "\n  ".join(offenders))
    else:
        pass_check("mobile.copy.training_terms", f"no Russian game/player copy in {scanned} dashboard source files")


def main() -> int:
    print("=== RUZA MOBILE READINESS CHECK ===")
    check_index_html()
    check_manifest()
    check_runtime_files()
    check_no_visible_game_copy()
    print(f"SUMMARY blockers={blockers}")
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
