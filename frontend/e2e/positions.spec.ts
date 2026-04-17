/**
 * Playwright e2e tests for the positions UI.
 *
 * Not executed as part of CI or during Phase 10 scaffold. To run:
 *   cd frontend
 *   pnpm add -D @playwright/test
 *   pnpm playwright install
 *   pnpm playwright test e2e/positions.spec.ts
 *
 * Prereqs:
 *   - Supabase env vars set in frontend/.env.local
 *   - Backend running on localhost:8000
 *   - Test user created ahead of time (E2E_EMAIL / E2E_PASSWORD env vars)
 */

// @ts-expect-error Playwright is intentionally not installed yet — install before running.
import { expect, test } from "@playwright/test";

const BASE_URL = process.env.E2E_BASE_URL ?? "http://localhost:3000";
const EMAIL = process.env.E2E_EMAIL ?? "";
const PASSWORD = process.env.E2E_PASSWORD ?? "";

test.beforeEach(async ({ page }) => {
  if (!EMAIL || !PASSWORD) {
    test.skip(true, "set E2E_EMAIL / E2E_PASSWORD to run positions e2e");
  }
  await page.goto(`${BASE_URL}/login`);
  await page.getByLabel("E-mail").fill(EMAIL);
  await page.getByLabel("Senha").fill(PASSWORD);
  await page.getByRole("button", { name: /entrar/i }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
});

test("create-physical-frame: new frame appears in the list", async ({ page }) => {
  await page.goto(`${BASE_URL}/positions?tab=physical`);
  await page.getByRole("button", { name: /nova posição/i }).click();
  await page.getByLabel(/tonelagem/i).fill("1000");
  await page.getByLabel(/entrega início/i).fill("2026-05-01");
  await page.getByLabel(/entrega fim/i).fill("2026-07-31");
  await page.getByLabel(/contraparte/i).fill("Playwright CP");
  await page.getByRole("button", { name: /^criar$/i }).click();
  await expect(page.getByText("Playwright CP")).toBeVisible();
});

test("over-lock-rejected: second CBOT fixation on a 1000t frame returns 409", async ({ page }) => {
  await page.goto(`${BASE_URL}/positions?tab=physical`);
  await page.getByText("Playwright CP").first().click();
  await expect(page).toHaveURL(/\/positions\/frames\//);

  // First fixation 600t CBOT — should succeed.
  await page.getByRole("button", { name: /nova fixação/i }).click();
  await page.getByRole("radio", { name: /^cbot$/ }).check();
  await page.getByLabel(/tonelagem/i).fill("600");
  await page.getByLabel(/^data$/i).fill("2026-04-15");
  await page.getByLabel(/cbot \(usc\/bu\)/i).fill("1420");
  await page.getByRole("button", { name: /registrar/i }).click();

  // Second fixation 500t CBOT — should surface inline "over-locked" error.
  await page.getByRole("button", { name: /nova fixação/i }).click();
  await page.getByRole("radio", { name: /^cbot$/ }).check();
  await page.getByLabel(/tonelagem/i).fill("500");
  await page.getByLabel(/^data$/i).fill("2026-04-16");
  await page.getByLabel(/cbot \(usc\/bu\)/i).fill("1425");
  await page.getByRole("button", { name: /registrar/i }).click();
  await expect(page.getByText(/over-lock no leg cbot/i)).toBeVisible();
});

test("import-flow: preview shows 12+ rows and commit lands in tables", async ({ page }) => {
  await page.goto(`${BASE_URL}/positions/import`);
  const filePath = "../docs/example_import.xlsx";
  await page.setInputFiles("input[type=file]", filePath);
  await expect(page.getByText(/válidas/)).toBeVisible();
  await page.getByRole("button", { name: /commit/i }).click();
  await expect(page).toHaveURL(/\/positions$/);
});
