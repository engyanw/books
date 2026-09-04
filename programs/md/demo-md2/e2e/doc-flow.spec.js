// @tags: e2e,doc-flow
// 文档主链路：登录→新建云端文档→编辑→保存→刷新重开验证内容持久→导出 .md 下载。
// 这条链路是 SPA↔后端 集成边界的核心，之前仅有后端 HTTP 测试，无真实浏览器覆盖。
// 编辑器为普通 <textarea id="editor">（Monaco 在无 requirejs 时不加载，回退到 textarea，
// app.js:411-420），cloudSave 读取 editor.value 落库，故用 fill/inputValue 即可驱动。
import { test, expect } from '@playwright/test';
import fs from 'fs';

const E2E_USER = 'e2e_flow';
const E2E_PASS = 'p@ssw0rd';
const DOC_CONTENT = '# e2e 标题\n\n正文内容 e2e-marker-12345';

async function loginOrRegister(page, user, pass) {
  await page.goto('/');
  // 默认侧边栏在"文件"页签，登录按钮在 cloudPanel 内（默认隐藏）→切到云端页签
  await page.evaluate(() => window.editor.switchSidebarTab('cloud'));
  await expect(page.locator('#btnCloudLogin')).toBeVisible();
  await page.click('#btnCloudLogin');
  await expect(page.locator('.auth-dialog')).toBeVisible();
  await page.fill('#authUsername', user);
  await page.fill('#authPassword', pass);
  await page.click('.auth-login');
  const ok = await page.locator('#cloudUser').filter({ hasText: user }).waitFor({ timeout: 8_000 })
    .then(() => true).catch(() => false);
  if (!ok) {
    await page.click('.auth-register');
    await expect(page.locator('#cloudUser')).toContainText(user, { timeout: 10_000 });
  }
  await expect(page.locator('#btnCloudLogout')).toBeVisible();
}

test('新建云端文档→编辑→保存→刷新重开内容持久', async ({ page }) => {
  await loginOrRegister(page, E2E_USER, E2E_PASS);

  // 新建云端文件（草稿制：保存时才落库）
  await page.click('#btnCloudNewFile');
  await expect(page.locator('#editor')).toBeVisible();
  await page.fill('#editor', DOC_CONTENT);

  // 保存到云端：#btnCloudToolbarSave → cloudSave → saveDraft → POST /api/docs → openCloudFile
  await page.click('#btnCloudToolbarSave');
  // 云端树出现该文档条目（轮询：刷新是异步的）
  await expect.poll(async () => page.locator('#cloudTree .file-item').count(), { timeout: 15_000 })
    .toBeGreaterThanOrEqual(1);

  // 刷新：_restoreCloudSession 按 cloudDocId 重新打开上次文档，editor 应恢复内容
  await page.reload();
  await expect(page.locator('#cloudUser')).toContainText(E2E_USER);  // 自动恢复登录态
  await expect(page.locator('#editor')).toHaveValue(/e2e-marker-12345/, { timeout: 15_000 });
});

test('本地文档导出 Markdown 触发文件下载', async ({ page }) => {
  await loginOrRegister(page, E2E_USER, E2E_PASS);

  // 切到干净的"本地文档"状态：清除上次云端文档引用后刷新（避免 saveToFile 走 cloudSave）
  await page.evaluate(() => localStorage.removeItem('cloudDocId'));
  await page.reload();
  await expect(page.locator('#cloudUser')).toContainText(E2E_USER);

  const exportContent = '# 导出测试\n\nexport-marker-98765';
  await page.fill('#editor', exportContent);
  // 强制走 blob 下载兜底（headless 下 showSaveFilePicker 不可用/会弹原生框）
  await page.evaluate(() => { try { delete window.showSaveFilePicker; } catch (e) {} });

  await page.click('#btnExport');
  await expect(page.locator('#exportMenu')).toBeVisible();
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.click('[data-export="md"]'),
  ]);
  expect(download.suggestedFilename()).toMatch(/\.md$/);
  const path = await download.path();
  expect(path).toBeTruthy();
  const text = fs.readFileSync(path, 'utf8');
  expect(text).toContain('export-marker-98765');
});
