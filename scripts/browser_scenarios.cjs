// Run against scripts/demo_local.py only; Playwright is a separate QA dependency.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const playwrightPath = fs.existsSync(path.join(__dirname, 'browser-qa/node_modules/playwright'))
  ? './browser-qa/node_modules/playwright'
  : 'playwright';
const { chromium } = require(playwrightPath);

const baseURL = process.env.QA_DASHBOARD_URL || 'http://127.0.0.1:15173';
const target = new URL(baseURL);
assert(['127.0.0.1', 'localhost', '[::1]'].includes(target.hostname), 'Use a local demo URL');
assert.equal(process.env.QA_ALLOW_DEMO, 'true', 'Set QA_ALLOW_DEMO=true for synthetic data only');
const demoDate = process.env.DEMO_DATE || new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Moscow' }).format(new Date());
const output = path.resolve(process.env.QA_OUTPUT_DIR || '.runlogs/browser-qa');
fs.mkdirSync(output, { recursive: true });
const results = [];
const browserErrors = [];

async function scenario(name, task) {
  try {
    await task();
    results.push({ name, status: 'PASS' });
  } catch (error) {
    results.push({ name, status: 'FAIL', error: error.message });
  }
  console.log(JSON.stringify(results[results.length - 1]));
}

async function login(context, role) {
  const page = await context.newPage();
  page.on('pageerror', (error) => browserErrors.push(error.message));
  await page.goto('/login');
  await page.getByRole('button', { name: new RegExp(`^${role}$`, 'i') }).click();
  const requested = page.waitForResponse((response) => response.url().endsWith('/auth/request-code'));
  await page.getByRole('button', { name: /^Получить код$/i }).click();
  const request = await requested;
  assert.equal(request.status(), 200, `Demo login request failed for ${role}`);
  assert((await request.json()).debug_code, `Synthetic OTP is missing for ${role}`);
  const hint = page.getByText(/Тестовый код:/);
  await hint.waitFor();
  const otp = (await hint.innerText()).match(/\d{6}/)?.[0];
  assert(otp, 'Local demo must provide a synthetic OTP');
  await page.getByLabel('Одноразовый код', { exact: true }).fill(otp);
  await page.getByRole('button', { name: /^Войти$/i }).click();
  await page.waitForURL(/\/(bookings|pilot)$/);
  return page;
}

async function selectDate(page) {
  await page.locator('input[type="date"]').first().fill(demoDate);
}

(async () => {
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.QA_CHROMIUM_EXECUTABLE ? { executablePath: process.env.QA_CHROMIUM_EXECUTABLE } : {}),
  });
  try {
    const options = { baseURL, timezoneId: 'Europe/Moscow' };
    const operatorContext = await browser.newContext(options);
    const pilotContext = await browser.newContext({ ...options, viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
    const adminContext = await browser.newContext(options);
    let operator;
    let pilot;
    let admin;

    await scenario('anonymous session and protected route', async () => {
      const context = await browser.newContext(options);
      const page = await context.newPage();
      let sessionCalls = 0;
      page.on('request', (request) => { if (request.url().includes('/auth/me')) sessionCalls++; });
      await page.goto('/bookings');
      await page.getByLabel('Телефон', { exact: true }).waitFor();
      assert.equal(sessionCalls, 0, 'Anonymous page must not spam auth/me');
      await context.close();
    });

    await scenario('operator arrival, warmup, explicit pilot handoff', async () => {
      operator = await login(operatorContext, 'Оператор');
      await selectDate(operator);
      const card = operator.locator('article').filter({ hasText: 'Ирина Смирнова' });
      await card.waitFor();
      await card.getByRole('button', { name: /^На месте$/i }).click();
      await card.getByRole('button', { name: /^Размялся$/i }).click();
      await card.getByRole('button', { name: /Передать пилоту/i }).first().click();
      await card.getByText(/^Готово к старту$/i).first().waitFor();
      assert.equal(await card.getByRole('button', { name: /Запустить сет/i }).count(), 0);
      await operator.reload();
      await operator.getByRole('button', { name: /^Выйти$/i }).waitFor();
      await selectDate(operator);
    });

    await scenario('mobile pilot start and second-by-second countdown', async () => {
      pilot = await login(pilotContext, 'Пилот');
      await pilot.goto('/m/pilot');
      await selectDate(pilot);
      const card = pilot.locator('article').filter({ hasText: 'Ирина Смирнова' });
      await card.waitFor();
      assert.equal(await card.getByRole('button', { name: /^Неявка$/i }).count(), 0);
      await card.getByRole('button', { name: /Запустить сет/i }).first().click();
      const clock = pilot.locator('.shift-clock span');
      await clock.waitFor();
      const first = await clock.innerText();
      await pilot.waitForFunction((previous) => document.querySelector('.shift-clock span')?.textContent !== previous, first, { timeout: 3500 });
      assert(await clock.innerText(), 'Clock must remain visible');
      const cardClock = card.locator('.game-stat').filter({ hasText: 'Осталось' }).locator('div').last();
      const cardFirst = await cardClock.innerText();
      await pilot.waitForFunction((previous) => {
        const article = [...document.querySelectorAll('article')].find((item) => item.textContent.includes('Ирина Смирнова'));
        const stat = [...(article?.querySelectorAll('.game-stat') || [])].find((item) => item.textContent.includes('Осталось'));
        return stat?.lastElementChild?.textContent !== previous;
      }, cardFirst, { timeout: 3500 });
      const dimensions = await pilot.evaluate(() => ({ width: innerWidth, scroll: document.documentElement.scrollWidth }));
      assert(dimensions.scroll <= dimensions.width + 1, 'Mobile page must not overflow horizontally');
      await pilot.screenshot({ path: path.join(output, 'mobile-pilot-running.png'), fullPage: true });
    });

    await scenario('pilot pause, stop and operator observes completion', async () => {
      assert(pilot && operator, 'Role setup must succeed');
      const card = pilot.locator('article').filter({ hasText: 'Ирина Смирнова' });
      await card.getByRole('button', { name: /^Пауза/i }).first().click();
      await card.getByRole('button', { name: /^Завершить заезд/i }).first().click();
      await card.getByText(/Фактическое время/i).waitFor();
      await operator.reload();
      await selectDate(operator);
      const operatorCard = operator.locator('article').filter({ hasText: 'Ирина Смирнова' });
      await operatorCard.getByText(/^Завершено$/i).first().waitFor();
    });

    await scenario('admin payment recorded and KPI uses paid money', async () => {
      admin = await login(adminContext, 'Администратор');
      await selectDate(admin);
      const card = admin.locator('article').filter({ hasText: 'Ирина Смирнова' });
      await card.getByRole('button', { name: /^Зафиксировать оплату$/i }).click();
      await card.getByLabel('Сумма оплаты в рублях').fill('12000');
      await card.getByRole('button', { name: /^Зафиксировать$/i }).click();
      await card.getByText(/^Оплачено$/i).waitFor();
      const response = await adminContext.request.get(`/api/kpi/summary?period=day&date_from=${demoDate}`);
      assert.equal(response.status(), 200);
      const kpi = await response.json();
      assert.equal(kpi.net_revenue_minor, 1200000);
      await admin.screenshot({ path: path.join(output, 'admin-paid-booking.png'), fullPage: true });
    });

    await scenario('pilot gets assigned boat only; operator logout clears session', async () => {
      const assigned = await pilotContext.request.get(`/api/bookings?date=${demoDate}`);
      assert.equal(assigned.status(), 200);
      assert((await assigned.json()).every((booking) => booking.boat_id === 'boat_1'));
      const logoutResponse = operator.waitForResponse((response) => response.url().endsWith('/auth/logout'));
      await operator.getByRole('button', { name: /^Выйти$/i }).click();
      assert.equal((await logoutResponse).status(), 200);
      await operator.getByLabel('Телефон', { exact: true }).waitFor();
      const response = await operatorContext.request.get('/api/auth/me');
      assert.equal(response.status(), 401);
    });

    await scenario('browser JavaScript has no unhandled exceptions', async () => {
      assert.deepEqual(browserErrors, []);
    });
  } finally {
    await browser.close();
    fs.writeFileSync(path.join(output, 'results.json'), JSON.stringify({ baseURL, demoDate, results }, null, 2));
  }
  if (results.some((result) => result.status !== 'PASS')) process.exitCode = 1;
})().catch((error) => { console.error(error.message); process.exitCode = 1; });
