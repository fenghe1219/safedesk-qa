import { expect, type Page } from "@playwright/test";

import { PASSWORD } from "./accounts";

export async function loginAs(
  page: Page,
  email: string,
  expectedUrl: RegExp
): Promise<void> {
  await page.goto("/login");
  await page.getByLabel("邮箱").fill(email);
  await page.getByLabel("密码").fill(PASSWORD);
  await page.getByRole("button", { name: /登录 SafeDesk/ }).click();
  await expect(page).toHaveURL(expectedUrl);
}

export async function openChatAndCreateCase(
  page: Page,
  prompt: string
): Promise<string> {
  await page.goto("/chat");
  await expect(page.getByRole("heading", { name: /你好/ })).toBeVisible();
  await page.waitForLoadState("networkidle");
  await page.getByPlaceholder(/描述你遇到的 IT 或行政问题/).fill(prompt);
  await page.getByRole("button", { name: "创建 Case", exact: true }).click();
  await expect(page).toHaveURL(/\/cases\/case_/);
  const caseId = new URL(page.url()).pathname.split("/").pop();
  expect(caseId).toBeTruthy();
  return caseId as string;
}
