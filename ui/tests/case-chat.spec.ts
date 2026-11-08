import { expect, test } from "@playwright/test";

import { accounts } from "./helpers/accounts";
import { loginAs, openChatAndCreateCase } from "./helpers/ui";

test("员工创建 Case 后通过 SSE 获得带引用回答并可核对原文", async ({ page }) => {
  await loginAs(page, accounts.employee.email, /\/chat$/);

  const sseResponse = page.waitForResponse(
    (response) =>
      response.url().includes("/messages") && response.request().method() === "POST"
  );
  await page.goto("/chat");
  await page.waitForLoadState("networkidle");
  await page
    .getByPlaceholder(/描述你遇到的 IT 或行政问题/)
    .fill("我的 VPN 一直连不上，提示证书无效。");
  await page.getByRole("button", { name: "创建 Case", exact: true }).click();
  await expect(page).toHaveURL(/\/cases\/case_/);

  const response = await sseResponse;
  expect(response.status()).toBe(200);
  expect(response.headers()["content-type"]).toContain("text/event-stream");

  await expect(page.getByRole("heading", { name: "知识回答" })).toBeVisible();
  await expect(page.getByText("已回答").first()).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("heading", { name: "证据与来源" })).toBeVisible();
  await expect(page.getByText(/条引用/).first()).toBeVisible();

  const citation = page.getByText("VPN 使用与排障指南").first();
  await expect(citation).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: "查看原文" }).first().click();
  await expect(page.getByText("来源原文", { exact: true })).toBeVisible();
  await expect(page.locator("mark").first()).toBeVisible();
});

test("员工创建 Case 后能看到工单草稿而不直接建单", async ({ page }) => {
  await loginAs(page, accounts.employee.email, /\/chat$/);
  await openChatAndCreateCase(
    page,
    "打印机报错 0x0000011b，Windows 11，帮我建个工单"
  );
  await expect(page.getByText("工单待确认").first()).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("支持人员确认后创建工单").first()).toBeVisible();
  await expect(page.getByRole("button", { name: "确认创建工单" })).toHaveCount(0);
});
