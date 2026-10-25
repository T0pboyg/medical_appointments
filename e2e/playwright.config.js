import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  workers: 1,
  retries: 0,
  timeout: 45000,
  reporter: "list",
  use: {
    baseURL: "http://localhost:5173",
    browserName: "chromium",
    timezoneId: "Europe/Athens",
    locale: "el-GR",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
});
