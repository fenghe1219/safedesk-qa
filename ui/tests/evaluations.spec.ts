import { expect, test } from "@playwright/test";

import { accounts } from "./helpers/accounts";
import { loginAs } from "./helpers/ui";

test("评估员在控制台运行安全集并看到核心指标", async ({ page }) => {
  await loginAs(page, accounts.evaluator.email, /\/evaluations$/);
  await expect(page.getByRole("heading", { name: "评估控制台" })).toBeVisible();

  await page.getByRole("button", { name: /安全场景/ }).click();
  await page.getByRole("button", { name: "运行评估", exact: true }).click();
  await expect(page.getByText(/Run 已完成：15 条样本/)).toBeVisible({
    timeout: 60_000
  });
  await expect(page.getByText("越权拒答率").first()).toBeVisible();
  await expect(page.getByText("注入成功率").first()).toBeVisible();
});
