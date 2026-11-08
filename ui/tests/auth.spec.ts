import { expect, test } from "@playwright/test";

import { accounts, PASSWORD } from "./helpers/accounts";
import { loginAs } from "./helpers/ui";

test.describe("认证与会话", () => {
  test("未登录访问工作台会跳转到登录页", async ({ page }) => {
    await page.goto("/chat");
    await expect(page).toHaveURL(/\/login$/);
    await expect(page.getByRole("heading", { name: "进入工作台" })).toBeVisible();
  });

  test("错误密码不会建立会话", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("邮箱").fill(accounts.employee.email);
    await page.getByLabel("密码").fill(`${PASSWORD}-wrong`);
    await page.getByRole("button", { name: /登录 SafeDesk/ }).click();
    await expect(page.getByRole("alert")).toBeVisible();
    await expect(page).toHaveURL(/\/login$/);
  });

  test("员工登录后刷新仍保持 Cookie 会话", async ({ page }) => {
    await loginAs(page, accounts.employee.email, /\/chat$/);
    await expect(page.getByRole("heading", { name: /你好，林晓/ })).toBeVisible();
    await page.reload();
    await expect(page).toHaveURL(/\/chat$/);
    await expect(page.getByRole("heading", { name: /你好，林晓/ })).toBeVisible();
  });

  test("员工访问评估与审计页面会看到权限拒绝", async ({ page }) => {
    await loginAs(page, accounts.employee.email, /\/chat$/);
    for (const path of ["/evaluations", "/audit", "/approvals"]) {
      await page.goto(path);
      await expect(page.getByRole("heading", { name: "当前角色没有访问权限" })).toBeVisible();
      await expect(page).toHaveURL(new RegExp(`${path}$`));
    }
  });
});
