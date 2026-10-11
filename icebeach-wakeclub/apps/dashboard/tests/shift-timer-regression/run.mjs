import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { createServer } from "vite";

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.SHIFT_QA_PLAYWRIGHT_PATH || "playwright");
const root = fileURLToPath(new URL("../../", import.meta.url));
const mockClient = `
export const getShiftLive = () => window.shiftQa.getLive();
export const runBookingTimerAction = (id, action) => window.shiftQa.mutate(id, action);
export const updateBookingStatus = (id, status) => window.shiftQa.mutate(id, status);
export const updateBookingPrep = (id, patch) => window.shiftQa.mutate(id, patch.arrival_action || patch.warmup_state);
`;
const server = await createServer({
  root, configFile: false, envDir: path.dirname(fileURLToPath(import.meta.url)),
  cacheDir: path.join(root, "tests/shift-timer-regression/.runlogs/vite"),
  optimizeDeps: { entries: ["tests/shift-timer-regression/fixture.tsx"] },
  server: { host: "127.0.0.1", port: 0 },
  plugins: [{
    name: "isolated-shift-api-mocks",
    enforce: "pre",
    load(id) {
      if (id.replaceAll("\\", "/").endsWith("/src/api/client.ts")) return mockClient;
      if (process.env.SHIFT_QA_BASELINE === "1" && id.replaceAll("\\", "/").endsWith("/LiveShiftStrip.tsx")) {
        return execFileSync("git", ["show", "1256d90:icebeach-wakeclub/apps/dashboard/src/components/shift-timer/LiveShiftStrip.tsx"], { cwd: root, encoding: "utf8" });
      }
    },
    configureServer(vite) {
      vite.middlewares.use((req, res, next) => {
        if (req.url !== "/") return next();
        res.setHeader("Content-Type", "text/html");
        res.end('<!doctype html><meta name="viewport" content="width=device-width, initial-scale=1"><div id="root"></div><script type="module" src="/tests/shift-timer-regression/fixture.tsx"></script>');
      });
    },
  }],
});
let browser;
let checks = 0;
try {
  await server.listen();
  const url = server.resolvedUrls.local[0];
  browser = await chromium.launch(process.env.SHIFT_QA_CHROMIUM
    ? { executablePath: process.env.SHIFT_QA_CHROMIUM }
    : { channel: "msedge" });
  for (const viewport of [{ width: 1366, height: 900 }, { width: 390, height: 844 }]) {
    const page = await browser.newPage({ viewport, timezoneId: "Europe/Moscow" });
    const errors = [];
    const blocked = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.route("**/*", (route) => {
      if (new URL(route.request().url()).origin === new URL(url).origin) return route.continue();
      blocked.push(route.request().url());
      return route.abort();
    });
    const now = new Date("2026-10-10T09:00:00Z");
    await page.clock.install({ time: now });
    await page.clock.pauseAt(now);
    const wait = async (fn, arg) => {
      for (let attempt = 0; attempt < 100; attempt += 1) {
        if (await page.evaluate(fn, arg)) return;
        await new Promise((resolve) => setTimeout(resolve, 50));
      }
      throw new Error(`Fixture did not settle: ${fn}`);
    };
    await page.goto(url);
    await wait(() => window.shiftQa?.liveCalls === 1 && document.querySelector(".shift-clock span"));
    const focus = page.getByTestId("focus");
    const clock = page.locator(".shift-clock span");
    const check = async (label, task) => { await task(); checks += 1; console.log(`PASS ${viewport.width}px ${label}`); };
    const reset = async (role, status, state, allowTimer = true, allowCancel = true) => {
      await page.evaluate((args) => window.shiftQa.reset(...args), [role, status, state, allowTimer, allowCancel]);
      await wait(([role, status, state]) => {
        const main = document.querySelector("main");
        return main?.dataset.role === role && main.dataset.status === status && main.dataset.state === state;
      }, [role, status, state]);
    };
    await check("countdown ticks between API polls and changes warning tone", async () => {
      assert.equal(await clock.textContent(), "05:05");
      await page.clock.runFor(1000);
      assert.equal(await clock.textContent(), "05:04");
      await page.clock.runFor(4000);
      assert.equal(await clock.textContent(), "05:00");
      assert.equal(await page.locator(".shift-clock-warm").count(), 1);
      assert.equal(await page.evaluate(() => window.shiftQa.liveCalls), 1);
    });
    await check("paused countdown is frozen, running reaches zero, polling rebases", async () => {
      await page.evaluate(() => { window.shiftQa.liveBooking.timer_state = "paused"; window.shiftQa.liveBooking.remaining_seconds = 61; window.dispatchEvent(new CustomEvent("icebeach:shift-live-refresh")); });
      await wait(() => document.querySelector(".shift-clock span")?.textContent === "01:01");
      await page.clock.runFor(3000);
      assert.equal(await clock.textContent(), "01:01");
      await page.evaluate(() => { window.shiftQa.liveBooking.timer_state = "running"; window.shiftQa.liveBooking.remaining_seconds = 1; window.dispatchEvent(new CustomEvent("icebeach:shift-live-refresh")); });
      await wait(() => document.querySelector(".shift-clock span")?.textContent === "00:01");
      await page.clock.runFor(1000);
      assert.equal(await clock.textContent(), "00:00");
      assert.equal(await page.locator(".shift-clock-hot").count(), 1);
      await page.evaluate(() => { window.shiftQa.liveBooking.remaining_seconds = 120; });
      await page.clock.runFor(1000);
      await wait(() => document.querySelector(".shift-clock span")?.textContent === "02:00");
      await page.clock.runFor(1000);
      assert.equal(await clock.textContent(), "01:59");
    });
    for (const role of ["admin", "operator", "pilot", "coach", "marketing_read"]) {
      for (const status of ["confirmed", "late", "arrived", "ready", "in_progress", "done", "cancelled", "no_show"]) {
        await check(`${role}/${status} role and FSM button matrix`, async () => {
          await reset(role, status, status === "in_progress" ? "running" : status === "done" ? "completed" : "idle");
          const before = ["confirmed", "late", "arrived", "ready"].includes(status);
          const manager = ["admin", "operator"].includes(role);
          const prep = ["admin", "operator", "pilot"].includes(role) && before;
          const noShow = focus.getByRole("button", { name: "Не пришел", exact: true });
          assert.equal(await noShow.count(), Number(manager && before));
          if (manager && before) assert.equal(await noShow.isDisabled(), !["confirmed", "late"].includes(status));
          assert.equal(await focus.getByRole("button", { name: "Отменить", exact: true }).count(), Number(manager && before));
          assert.equal(await focus.locator(".pilot-boat-button").count(), Number(["admin", "pilot"].includes(role) && ["ready", "in_progress"].includes(status)));
          const arrival = focus.getByRole("button", { name: "Приехал", exact: true });
          assert.equal(await arrival.count(), Number(prep));
          if (prep) {
            assert.equal(await arrival.isDisabled(), status === "ready");
            assert.equal(await focus.getByRole("button", { name: "Не приехал", exact: true }).isDisabled(), !["confirmed", "late"].includes(status));
            assert.equal(await focus.getByRole("button", { name: "Размялся", exact: true }).isDisabled(), !["arrived", "ready"].includes(status));
          }
        });
      }
    }
    await check("timer/cancel opt-in flags are preserved", async () => {
      await reset("admin", "ready", "idle", false, false);
      assert.equal(await focus.locator(".pilot-boat-button").count(), 0);
      assert.equal(await focus.getByRole("button", { name: "Отменить", exact: true }).count(), 0);
    });
    for (const role of ["pilot", "admin"]) {
      await check(`${role} start -> pause -> stop preserves callback updates and fact`, async () => {
        await reset(role, "ready", "idle");
        for (const [action, nextLabel] of [["start", "Пауза"], ["pause", "Завершить мягко"], ["stop", null]]) {
          await focus.locator(".pilot-boat-button").click();
          assert.equal(await page.evaluate(() => window.shiftQa.calls.at(-1).action), action);
          assert.equal(await focus.locator(".pilot-boat-button").isDisabled(), true);
          await page.evaluate(() => window.shiftQa.finish());
          await wait((label) => label ? document.querySelector('[data-testid="focus"] .pilot-boat-label')?.textContent === label : !document.querySelector('[data-testid="focus"] .pilot-boat-button'), nextLabel);
        }
        assert.match(await focus.textContent(), /01:15/);
        assert.deepEqual(await page.evaluate(() => window.shiftQa.calls.map((call) => call.action)), ["start", "pause", "stop"]);
      });
    }
    await check("duplicate focus/queue clicks send one request; other booking stays enabled", async () => {
      await reset("pilot", "ready", "idle");
      await page.evaluate(() => {
        document.querySelector('[data-testid="focus"] .pilot-boat-button').click();
        document.querySelector('[data-testid="duplicate"] .pilot-boat-button').click();
      });
      assert.equal(await page.evaluate(() => window.shiftQa.calls.length), 1);
      assert.equal(await page.getByTestId("duplicate").locator(".pilot-boat-button").isDisabled(), true);
      assert.equal(await page.getByTestId("other").locator(".pilot-boat-button").isDisabled(), false);
      await page.evaluate(() => window.shiftQa.finish(true));
      await wait(() => document.querySelector('[data-testid="focus"]')?.textContent.includes("Mock request failed"));
      assert.equal(await focus.locator(".pilot-boat-button").isDisabled(), false);
      assert.equal(await page.getByTestId("duplicate").locator(".pilot-boat-button").isDisabled(), false);
      await page.getByTestId("duplicate").locator(".pilot-boat-button").click();
      assert.equal(await page.evaluate(() => window.shiftQa.calls.length), 2);
      await page.evaluate(() => window.shiftQa.finish());
      await wait(() => document.querySelector('[data-testid="focus"] .pilot-boat-label')?.textContent === "Пауза");
    });
    await check("cross-action duplicates also share the booking lock", async () => {
      await reset("admin", "confirmed", "idle");
      await focus.getByRole("button", { name: "Не пришел", exact: true }).click();
      const buttons = await page.getByTestId("duplicate").getByRole("button").all();
      for (const button of buttons) assert.equal(await button.isDisabled(), true);
      assert.equal(await page.evaluate(() => window.shiftQa.calls[0].action), "no_show");
      await page.evaluate(() => window.shiftQa.finish());
      await wait(() => !document.querySelector('[data-testid="focus"] button'));
    });
    await check("timer helper edge cases and full primary-action FSM", async () => {
      const failures = await page.evaluate(() => {
        const { getLiveRemainingSeconds: remaining, getPrimaryTimerAction: primary } = window.shiftQa.timer;
        const errors = [];
        const expect = (actual, expected, label) => { if (actual !== expected) errors.push(label); };
        expect(remaining(null, 0, 1000), 0, "empty");
        expect(remaining({ timer_state: "running", remaining_seconds: 10 }, 1000, 999), 10, "backward clock");
        expect(remaining({ timer_state: "running", remaining_seconds: 10 }, 1000, 1999), 10, "fractional tick");
        for (const state of ["idle", "paused", "completed"]) expect(remaining({ timer_state: state, remaining_seconds: 10 }, 0, 60000), 10, state);
        expect(remaining({ timer_state: "running", remaining_seconds: 10 }, 0, 60000), 0, "zero floor");
        for (const status of ["confirmed", "late", "arrived", "ready", "in_progress", "done", "cancelled", "no_show"]) {
          for (const timer_state of ["idle", "running", "paused", "completed"]) {
            const expected = status === "ready" && timer_state === "idle" ? "start" : status === "in_progress" && timer_state === "running" ? "pause" : status === "in_progress" && timer_state === "paused" ? "stop" : null;
            expect(primary({ status, timer_state }), expected, `${status}/${timer_state}`);
          }
        }
        return errors;
      });
      assert.deepEqual(failures, []);
    });
    await check("mobile local date at Moscow/UTC midnight and year rollover", async () => {
      for (const [instant, expected] of [
        ["2026-10-09T20:59:59Z", "2026-10-09"],
        ["2026-10-09T21:00:00Z", "2026-10-10"],
        ["2026-10-09T23:59:59Z", "2026-10-10"],
        ["2026-10-10T00:00:00Z", "2026-10-10"],
        ["2026-12-31T21:00:00Z", "2027-01-01"],
      ]) {
        await page.clock.setFixedTime(new Date(instant));
        assert.equal(await page.evaluate(() => window.shiftQa.getToday()), expected, instant);
      }
    });
    await check("no page errors, external requests or horizontal overflow", async () => {
      assert.deepEqual(errors, []);
      assert.deepEqual(blocked, []);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
    });
    await page.close();
  }
  console.log(`PASS ${checks} browser regression scenarios (desktop + mobile); API is mocked, external requests blocked.`);
} finally {
  await browser?.close();
  await server.close();
}
