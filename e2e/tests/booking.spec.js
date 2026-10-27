import { test, expect } from "@playwright/test";

async function selectFutureDay(page) {
  await page.goto("/");
  const now = new Date();
  const day = new Date(now.getFullYear(), now.getMonth() + 1, 1);
  while ([0, 6].includes(day.getDay())) day.setDate(day.getDate() + 1);
  await page.getByRole("button", { name: "Επόμενος μήνας" }).click();
  await page.locator("button.calendar-day").filter({ hasText: new RegExp(`^${day.getDate()}$`) }).click();
  const times = page.getByRole("group", { name: "Ώρα ραντεβού" });
  await expect(times).toBeVisible();
  return { date: `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, "0")}-${String(day.getDate()).padStart(2, "0")}`, times };
}

async function book(page, name) {
  const { date, times } = await selectFutureDay(page);
  const time = await times.getByRole("button").first().innerText();
  await times.getByRole("button", { name: time, exact: true }).click();
  await page.getByLabel("Ονοματεπώνυμο", { exact: true }).fill(name);
  await page.getByLabel("Τηλέφωνο", { exact: true }).fill("6900000000");
  await page.getByLabel("ΑΜΚΑ", { exact: true }).fill("00000000000");
  return { date, time };
}

async function login(page) {
  const result = await page.request.post("/api/__e2e/login", { headers: { Origin: "http://localhost:5173" } });
  expect(result.ok()).toBeTruthy();
  await page.goto("/admin");
  await expect(page.getByRole("button", { name: "Αποσύνδεση", exact: true })).toBeEnabled();
}

async function selectAdminRange(page, from, to = from) {
  await page.getByLabel('Από ημερομηνία', { exact: true }).fill(from);
  await page.getByLabel('Έως ημερομηνία', { exact: true }).fill(to);
}

test("booking -> admin -> audited cancellation -> slot becomes free", async ({ page }) => {
  const name = "E2E Synthetic Cancellation";
  const { date, time } = await book(page, name);
  const created = page.waitForResponse(r => r.url().endsWith("/api/appointments") && r.request().method() === "POST");
  await page.getByRole("button", { name: "Κλείσε Ραντεβού", exact: true }).click();
  const response = await created;
  expect(response.status()).toBe(201);
  await expect(page.getByText("Το ραντεβού κλείστηκε επιτυχώς.", { exact: true })).toBeVisible();
  const booked = await page.request.get(`/api/availability?date=${date}`);
  expect(await booked.json()).not.toContain(time);

  await login(page);
  const dateFilter = page.getByLabel('Από ημερομηνία', { exact: true });
  const today = await dateFilter.inputValue();
  expect(today).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  await expect(page.getByText(name, { exact: true })).toHaveCount(0);
  await selectAdminRange(page, date);
  const records = await (await page.request.get(`/api/appointments?appointment_date=${date}`)).json();
  const saved = records.find(item => item.patient_name === name);
  expect(saved).toBeDefined();
  const id = saved.id;
  const card = page.getByRole("article", { name: `Ραντεβού ${id}`, exact: true });
  await expect(card.getByText(name, { exact: true })).toBeVisible();
  const amkaFilter = page.getByLabel('Αναζήτηση με ΑΜΚΑ', { exact: true });
  await amkaFilter.fill('000');
  await expect(page.getByText('Συμπλήρωσε ακριβώς 11 ψηφία ΑΜΚΑ.', { exact: true })).toBeVisible();
  await expect(card).toHaveCount(0);
  await amkaFilter.fill('11111111111');
  await expect(page.getByText('Δεν βρέθηκαν ραντεβού με τα επιλεγμένα φίλτρα.', { exact: true })).toBeVisible();
  await amkaFilter.fill('00000000000');
  await expect(card).toBeVisible();
  page.once("dialog", dialog => dialog.accept());
  await card.getByRole("button", { name: "Ακύρωση ραντεβού", exact: true }).click();
  await expect(card.getByText("Ακυρωμένο", { exact: true })).toBeVisible();
  const audit = await page.request.get(`/api/__e2e/audit/${id}`);
  expect(await audit.json()).toEqual({ cancellations: 1 });
  const freed = await page.request.get(`/api/availability?date=${date}`);
  expect(await freed.json()).toContain(time);
  await expect(dateFilter).toHaveValue(date);
  await page.getByRole('button', { name: 'Καθαρισμός φίλτρων', exact: true }).click();
  await expect(dateFilter).toHaveValue(today);
  await expect(page.getByLabel('Έως ημερομηνία', { exact: true })).toHaveValue(today);
  await expect(page.getByText(name, { exact: true })).toHaveCount(0);
});

test("expired session clears patient cards and requests login", async ({ page }) => {
  const { date } = await book(page, "E2E Synthetic Expired Session");
  await page.getByRole("button", { name: "Κλείσε Ραντεβού", exact: true }).click();
  await expect(page.getByText("Το ραντεβού κλείστηκε επιτυχώς.", { exact: true })).toBeVisible();
  await login(page);
  await selectAdminRange(page, date);
  const card = page.getByRole("article").filter({ hasText: "E2E Synthetic Expired Session" });
  await expect(card).toBeVisible();
  const csrf = await (await page.request.get("/api/auth/csrf")).json();
  const expired = await page.request.post("/api/__e2e/expire", { headers: { Origin: "http://localhost:5173", "X-CSRF-Token": csrf.csrf_token } });
  expect(expired.ok()).toBeTruthy();
  expect(await expired.json()).toEqual({ expired: true, session_retained: true });
  page.once("dialog", dialog => dialog.accept());
  await card.getByRole("button", { name: "Ακύρωση ραντεβού", exact: true }).click();
  await expect(page.getByRole("link", { name: "Σύνδεση προσωπικού", exact: true })).toBeVisible();
  await expect(page.getByRole("article")).toHaveCount(0);
});

test("failed booking request shows an error instead of success", async ({ page }) => {
  await book(page, "E2E Synthetic Network Failure");
  await page.route("**/api/appointments", route => route.request().method() === "POST" ? route.abort("failed") : route.continue());
  await page.getByRole("button", { name: "Κλείσε Ραντεβού", exact: true }).click();
  await expect(page.getByText("Δεν ήταν δυνατή η επικοινωνία με τον server.", { exact: true })).toBeVisible();
  await expect(page.getByText("Το ραντεβού κλείστηκε επιτυχώς.", { exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Κλείσε Ραντεβού", exact: true })).toBeEnabled();
});

test("admin list can retry after a network error without losing the date", async ({ page }) => {
  let fail = true;
  await page.route('**/api/appointments/page?*', route => fail ? route.abort('failed') : route.continue());
  await login(page);
  const filter = page.getByLabel('Από ημερομηνία', { exact: true });
  const selected = await filter.inputValue();
  await expect(page.getByText('Δεν ήταν δυνατή η φόρτωση των ραντεβού.', { exact: true })).toBeVisible();
  fail = false;
  await page.getByRole('button', { name: 'Επανάληψη φόρτωσης', exact: true }).click();
  await expect(page.getByText('Δεν βρέθηκαν ραντεβού με τα επιλεγμένα φίλτρα.', { exact: true })).toBeVisible();
  await expect(filter).toHaveValue(selected);
});

test("admin pages summaries and loads private details only on demand", async ({ page }) => {
  const pages = [];
  let detailRequests = 0;
  await page.route('**/api/appointments/page?*', async route => {
    const url = new URL(route.request().url());
    const number = Number(url.searchParams.get('page'));
    pages.push(number);
    await route.fulfill({
      json: {
        items: [{
          id: number, patient_name: `Synthetic Page ${number}`,
          starts_at: '2030-01-07T10:00:00+02:00', no_show: false, cancelled_at: null
        }],
        page: number, page_size: 25, has_more: number === 1
      }
    });
  });
  await page.route('**/api/appointments/1', async route => {
    detailRequests++;
    await route.fulfill({ json: { id: 1, patient_phone: '+306900000000', patient_AMKA: '00000000000' } });
  });
  await login(page);
  await expect(page.getByText('Synthetic Page 1', { exact: true })).toBeVisible();
  expect(detailRequests).toBe(0);
  await page.getByRole('button', { name: 'Λεπτομέρειες', exact: true }).click();
  await expect(page.getByText('+306900000000', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Κλείσιμο λεπτομερειών', exact: true }).click();
  await expect(page.getByText('+306900000000', { exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: 'Επόμενη σελίδα', exact: true }).click();
  await expect(page.getByText('Synthetic Page 2', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Επόμενη σελίδα', exact: true })).toBeDisabled();
  await selectAdminRange(page, '2030-01-08');
  await expect(page.getByText('Synthetic Page 1', { exact: true })).toBeVisible();
  expect(pages).toContain(2);
  expect(pages.at(-1)).toBe(1);
  expect(detailRequests).toBe(1);
});

test("admin date range validates limits and preserves range across pages", async ({ page }) => {
  const requests = [];
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route('**/api/appointments/page?*', async route => {
    const params = new URL(route.request().url()).searchParams;
    requests.push(Object.fromEntries(params));
    const number = Number(params.get('page'));
    await route.fulfill({
      json: {
        items: [{
          id: number, patient_name: `Range Synthetic ${number}`,
          starts_at: '2030-01-07T10:00:00+02:00', no_show: false, cancelled_at: null
        }],
        page: number, page_size: 25, has_more: number === 1,
      }
    });
  });
  await login(page);
  await selectAdminRange(page, '2030-01-01', '2030-01-31');
  await expect(page.getByText('Range Synthetic 1', { exact: true })).toBeVisible();
  await expect.poll(() => requests.at(-1)?.date_to).toBe('2030-01-31');
  await page.getByLabel('Αναζήτηση με ΑΜΚΑ', { exact: true }).fill('00000000000');
  await expect.poll(() => requests.at(-1)?.patient_AMKA).toBe('00000000000');
  await page.getByRole('button', { name: 'Επόμενη σελίδα', exact: true }).click();
  await expect(page.getByText('Range Synthetic 2', { exact: true })).toBeVisible();
  expect(requests.at(-1)).toMatchObject({ date_from: '2030-01-01', date_to: '2030-01-31', page: '2', patient_AMKA: '00000000000' });
  await page.getByLabel('Έως ημερομηνία', { exact: true }).fill('2030-01-30');
  await expect.poll(() => requests.at(-1)?.date_to).toBe('2030-01-30');
  expect(requests.at(-1).page).toBe('1');
  const count = requests.length;
  await page.getByLabel('Έως ημερομηνία', { exact: true }).fill('2030-02-01');
  await expect(page.getByText('Επίλεξε διάστημα έως 31 ημερών.', { exact: true })).toBeVisible();
  await expect(page.getByRole('article')).toHaveCount(0);
  await page.waitForTimeout(400);
  expect(requests).toHaveLength(count);
  await selectAdminRange(page, '2030-01-10', '2030-01-09');
  await expect(page.getByText('Το «Έως» δεν μπορεί να προηγείται του «Από».', { exact: true })).toBeVisible();
  await page.getByLabel('Από ημερομηνία', { exact: true }).fill('');
  await expect(page.getByText('Συμπλήρωσε και τις δύο ημερομηνίες.', { exact: true })).toBeVisible();
  await page.waitForTimeout(400);
  expect(requests).toHaveLength(count);
  expect(errors).toEqual([]);
});


test("admin calendar selects a day and filters the appointment list", async ({ page }) => {
  const errors = [];
  const listRequests = [];

  page.on("pageerror", error => errors.push(error.message));

  await page.route("**/api/appointments/calendar?*", async route => {
    const params = new URL(route.request().url()).searchParams;
    const year = params.get("year").padStart(4, "0");
    const month = params.get("month").padStart(2, "0");

    await route.fulfill({
      json: {
        days: [
          { date: `${year}-${month}-07`, count: 3 },
        ],
      },
    });
  });

  await page.route("**/api/appointments/page?*", async route => {
    const params = new URL(route.request().url()).searchParams;
    listRequests.push(Object.fromEntries(params));

    await route.fulfill({
      json: {
        items: [],
        page: Number(params.get("page")),
        page_size: 25,
        has_more: false,
      },
    });
  });

  await login(page);

  const calendar = page.getByRole("region", {
    name: "Ημερολόγιο ραντεβού",
    exact: true,
  });

  await expect(calendar).toBeVisible();

  const countedDay = calendar.getByRole("button", {
    name: /^\d{4}-\d{2}-07: 3 μη ακυρωμένα ραντεβού$/,
  });

  await expect(countedDay).toBeVisible();

  const date = (await countedDay.getAttribute("aria-label"))
    .split(":")[0];

  await countedDay.click();

  await expect(
    page.getByLabel("Από ημερομηνία", { exact: true })
  ).toHaveValue(date);

  await expect(
    page.getByLabel("Έως ημερομηνία", { exact: true })
  ).toHaveValue(date);

  await expect.poll(() => listRequests.at(-1)?.date_from)
    .toBe(date);

  expect(listRequests.at(-1)).toMatchObject({
    date_from: date,
    date_to: date,
    page: "1",
  });

  await expect(countedDay).toHaveAttribute("aria-pressed", "true");

  await calendar.getByRole("button", {
    name: "Επόμενος μήνας ημερολογίου admin",
    exact: true,
  }).click();

  const nextCountedDay = calendar.getByRole("button", {
    name: /^\d{4}-\d{2}-07: 3 μη ακυρωμένα ραντεβού$/,
  });

  await expect(nextCountedDay).toBeVisible();
  await expect(nextCountedDay).not.toHaveAttribute(
    "aria-label",
    `${date}: 3 μη ακυρωμένα ραντεβού`
  );

  expect(errors).toEqual([]);
});
