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
  const records = await (await page.request.get('/api/appointments')).json();
  const saved = records.find(item => item.patient_name === name);
  expect(saved).toBeDefined();
  const id = saved.id;
  const card = page.getByRole("article", { name: `Ραντεβού ${id}`, exact: true });
  await expect(card.getByText(name, { exact: true })).toBeVisible();
  page.once("dialog", dialog => dialog.accept());
  await card.getByRole("button", { name: "Ακύρωση ραντεβού", exact: true }).click();
  await expect(card.getByText("Ακυρωμένο", { exact: true })).toBeVisible();
  const audit = await page.request.get(`/api/__e2e/audit/${id}`);
  expect(await audit.json()).toEqual({ cancellations: 1 });
  const freed = await page.request.get(`/api/availability?date=${date}`);
  expect(await freed.json()).toContain(time);
});

test("expired session clears patient cards and requests login", async ({ page }) => {
  await book(page, "E2E Synthetic Expired Session");
  await page.getByRole("button", { name: "Κλείσε Ραντεβού", exact: true }).click();
  await expect(page.getByText("Το ραντεβού κλείστηκε επιτυχώς.", { exact: true })).toBeVisible();
  await login(page);
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
