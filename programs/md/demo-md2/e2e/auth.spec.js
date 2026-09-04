// @tags: e2e,auth
// 登录/注册/退出 主链路冒烟：验证 SPA 引导、鉴权对话框接线、登录态切换。
// 该路径无后端集成测试覆盖（后端测的是 /api/auth/* HTTP，这里测真实浏览器接线）。
import { test, expect } from '@playwright/test';

const E2E_USER = 'e2e_auth';
const E2E_PASS = 'p@ssw0rd';

async function openLoginDialog(page) {
  await page.goto('/');
  // 默认侧边栏在"文件"页签，登录/云文档按钮在 cloudPanel 内（默认隐藏）。
  // 直接调用应用自身的 switchSidebarTab 切到云端页签（比模拟 tab 点击更确定）。
  await page.evaluate(() => window.editor.switchSidebarTab('cloud'));
  await expect(page.locator('#btnCloudLogin')).toBeVisible();
  await page.click('#btnCloudLogin');
  await expect(page.locator('.auth-dialog')).toBeVisible();
}

test('注册新用户后进入已登录态，退出后回到未登录态', async ({ page }) => {
  await openLoginDialog(page);
  await page.fill('#authUsername', E2E_USER);
  await page.fill('#authPassword', E2E_PASS);

  // 先尝试登录（用户可能因上一轮 e2e 已存在）；失败则注册
  await page.click('.auth-login');
  const loggedIn = await page.locator('#cloudUser').filter({ hasText: E2E_USER }).waitFor({ timeout: 8_000 })
    .then(() => true).catch(() => false);
  if (!loggedIn) {
    // 清空可能的错误提示并注册
    await page.click('.auth-register');
    await expect(page.locator('#cloudUser')).toContainText(E2E_USER, { timeout: 10_000 });
  }

  // 已登录：登录按钮隐藏、退出按钮可见、用户名展示
  await expect(page.locator('#btnCloudLogin')).toBeHidden();
  await expect(page.locator('#btnCloudLogout')).toBeVisible();
  await expect(page.locator('#cloudUser')).toContainText(E2E_USER);

  // 退出
  await page.click('#btnCloudLogout');
  await expect(page.locator('#btnCloudLogin')).toBeVisible();
  await expect(page.locator('#btnCloudLogout')).toBeHidden();
  await expect(page.locator('#cloudTree')).toContainText(/未登录|登录/);
});

test('未登录触达云文档保存被引导到登录对话框', async ({ page }) => {
  await page.goto('/');
  await page.evaluate(() => window.editor.switchSidebarTab('cloud'));
  await expect(page.locator('#btnCloudLogin')).toBeVisible();
  // 未登录态可新建草稿（本地），但保存到云端时 isAuthenticated 守卫应弹出登录框
  await page.click('#btnCloudNewFile');
  await page.click('#btnCloudToolbarSave');
  await expect(page.locator('.auth-dialog')).toBeVisible({ timeout: 5_000 });
});
