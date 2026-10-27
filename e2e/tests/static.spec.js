import { test, expect } from "@playwright/test";

test.skip(process.env.STATIC_FRONTEND !== "1", "Static Caddy configuration only");

test("built SPA routes, assets and security headers", async ({ request }) => {
  for (const path of ["/", "/admin"]) {
    const response = await request.get(path);
    expect(response.status()).toBe(200);
    expect(response.headers()["content-type"]).toContain("text/html");
    expect(response.headers()["cache-control"]).toBe("no-cache");
    expect(response.headers()["x-content-type-options"]).toBe("nosniff");
    expect(response.headers()["content-security-policy"]).toContain("connect-src 'self'");
    const html = await response.text();
    expect(html).not.toContain("/@vite/client");
    expect(html).not.toContain("/main.jsx");
    const asset = html.match(/src="([^"]+\.js)"/)[1];
    const bundle = await request.get(asset);
    expect(bundle.status()).toBe(200);
    expect(bundle.headers()["cache-control"]).toContain("immutable");
    expect(await bundle.text()).not.toContain("e2e-only-proxy-secret");
  }
  expect((await request.get("/assets/not-found.js")).status()).toBe(404);
});

test("API routing preserves errors and overwrites untrusted proxy identity", async ({ request }) => {
  const missing = await request.get("/api/does-not-exist");
  expect(missing.status()).toBe(404);
  expect(missing.headers()["content-type"]).toContain("application/json");
  const protectedList = await request.get("/api/appointments/page");
  expect(protectedList.status()).toBe(401);
  const result = await request.post("/api/__e2e/login", { headers: {
    Origin: "http://localhost:5173", "X-API-Proxy-Secret": "forged-secret",
    "X-Forwarded-For": "not-an-ip", "X-Forwarded-Host": "untrusted.invalid",
  } });
  expect(result.status()).toBe(200);
});
