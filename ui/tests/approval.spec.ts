import { expect, test } from "@playwright/test";

import { accounts } from "./helpers/accounts";
import { createVpnApproval } from "./helpers/api";
import { loginAs } from "./helpers/ui";

test("审批人核对参数后批准执行并推动 Case 解决", async ({ page }) => {
  const fixture = await createVpnApproval();
  await loginAs(page, accounts.approver.email, /\/approvals$/);
  await page.goto(`/approvals?approval=${encodeURIComponent(fixture.approvalId)}`);

  await expect(page.getByRole("heading", { name: fixture.caseTitle })).toBeVisible();
  await expect(page.getByText("重置 VPN 证书").first()).toBeVisible();
  await expect(page.getByText("待审批").first()).toBeVisible();

  await page.getByRole("button", { name: "批准执行" }).click();
  await page.getByLabel(/我已核对固定参数哈希/).check();
  await page.getByRole("button", { name: "确认批准并执行" }).click();
  await expect(
    page.getByText("动作已执行并通过只读复核，Case 已解决。")
  ).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("已批准").first()).toBeVisible();

  await page.getByRole("link", { name: /打开 Case/ }).click();
  await expect(page.getByText("已解决").first()).toBeVisible();
});
