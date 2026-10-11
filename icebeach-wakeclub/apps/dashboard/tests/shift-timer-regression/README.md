# Isolated Shift UI Regression

Run in local PowerShell from `icebeach-wakeclub/apps/dashboard` within the QA worktree:

```powershell
$env:SHIFT_QA_PLAYWRIGHT_PATH = 'C:\Users\X230\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules\playwright'
node tests/shift-timer-regression/run.mjs
node --test tests/shift-timer-regression/date.test.mjs
npm exec --no -- tsc --noEmit
npm run build
```

Uses existing React/Vite dependencies and bundled Playwright, without adding a test
framework or changing package manifests. The browser defaults to installed Edge
(headless Chromium). Set `SHIFT_QA_CHROMIUM` to an existing Chromium executable if
Edge is unavailable; set `SHIFT_QA_PLAYWRIGHT_PATH` to the available Playwright
module path. Normal Node module resolution is also supported.
Wait for dependency installation in the shared worktree to finish before running
these checks. The harness keeps its Vite cache in its own ignored `.runlogs`.
The standalone date test uses built-in Node 24 TypeScript stripping and test
mocks, and can run without `node_modules`.

The standalone Vite server binds to loopback on an ephemeral port. Its plugin
replaces the API client with deferred in-memory mocks before the real client can
load. External browser requests are blocked. No session tokens, Sheets, Telegram,
SMS, backend services or repository `.env` files are used. Existing components
and styles are rendered at desktop and mobile sizes in Europe/Moscow.

Coverage: live countdown between polls, pause/expiry/rebasing/tone, all five roles
and eight booking statuses, timer/cancel opt-in flags, pilot/admin
start-pause-stop, duplicate focus/queue controls, lock release on rejection and
retry, unrelated booking independence, cross-action locking, timer helper edge
cases, local dates at Moscow/UTC midnight and year rollover, browser errors and
horizontal overflow. This is not a full mobile page or iOS Safari test.

To prove the countdown regression detects the old bug without editing files:

```powershell
$env:SHIFT_QA_BASELINE = '1'
node tests/shift-timer-regression/run.mjs
# Expected failure: 05:05 remains unchanged instead of advancing to 05:04.
Remove-Item Env:SHIFT_QA_BASELINE
```

The optional baseline mode loads only the historical strip from Git `1256d90`.
It does not change the checkout or access a remote.
