import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { stripTypeScriptTypes } from "node:module";
import test from "node:test";

// Load the actual mobile helper without npm dependencies (local Node 24).
process.env.TZ = "Europe/Moscow";
const mobileUrl = new URL("../../src/mobile/pilot-utils.ts", import.meta.url);
const datesUrl = new URL("../../src/lib/dates.ts", import.meta.url);
const labelsUrl = new URL("../../src/lib/label-dict.ts", import.meta.url);
const source = readFileSync(mobileUrl, "utf8")
  .replace('"../lib/dates"', JSON.stringify(datesUrl.href))
  .replace('"../lib/label-dict"', JSON.stringify(labelsUrl.href));
const { getToday } = await import(`data:text/javascript,${encodeURIComponent(stripTypeScriptTypes(source))}`);

for (const [instant, expected] of [
  ["2026-10-09T20:59:59Z", "2026-10-09"],
  ["2026-10-09T21:00:00Z", "2026-10-10"],
  ["2026-10-09T23:59:59Z", "2026-10-10"],
  ["2026-10-10T00:00:00Z", "2026-10-10"],
  ["2026-12-31T21:00:00Z", "2027-01-01"],
]) {
  test(`mobile local date in Europe/Moscow at ${instant}`, (t) => {
    t.mock.timers.enable({ apis: ["Date"], now: new Date(instant) });
    assert.equal(new Date().getTimezoneOffset(), -180);
    assert.equal(getToday(), expected);
  });
}
