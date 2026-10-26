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
  return { date: `${day.getFullYear()}-${String(day.getMonth()+1).padStart(2,"0")}-${String(day.getDate()).padStart(2,"0")}`, times };
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
  const dateFilter = page.getByLabel('Ημερομηνία ραντεβού', { exact: true });
  const today = await dateFilter.inputValue();
  expect(today).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  await expect(page.getByText(name, { exact: true })).toHaveCount(0);
  await dateFilter.fill(date);
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
  await expect(page.getByText(name, { exact: true })).toHaveCount(0);
});

test("expired session clears patient cards and requests login", async ({ page }) => {
  const { date } = await book(page, "E2E Synthetic Expired Session");
  await page.getByRole("button", { name: "Κλείσε Ραντεβού", exact: true }).click();
  await expect(page.getByText("Το ραντεβού κλείστηκε επιτυχώς.", { exact: true })).toBeVisible();
  await login(page);
  await page.getByLabel('Ημερομηνία ραντεβού', { exact: true }).fill(date);
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
  const filter = page.getByLabel('Ημερομηνία ραντεβού', { exact: true });
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
    await route.fulfill({ json: { items: [{ id: number, patient_name: `Synthetic Page ${number}`,
      starts_at: '2030-01-07T10:00:00+02:00', no_show: false, cancelled_at: null }],
      page: number, page_size: 25, has_more: number === 1 } });
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
  await page.getByLabel('Ημερομηνία ραντεβού', { exact: true }).fill('2030-01-08');
  await expect(page.getByText('Synthetic Page 1', { exact: true })).toBeVisible();
  expect(pages).toContain(2);
  expect(pages.at(-1)).toBe(1);
  expect(detailRequests).toBe(1);
});
