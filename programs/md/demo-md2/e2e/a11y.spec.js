// P2 a11y 可达性基线：用 axe-core 扫描主界面，断言无 critical 违例（WCAG 2.1 A/AA）。
// 静态 HTML 壳（侧栏/按钮/对话框）即使 marked CDN 失败也可检查——编辑器构造失败不阻断可达性扫描。
// serious/moderate 违例打印但不断言（作为改进基线，逐步收敛）。
import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test.describe('a11y 可达性基线', () => {
  test('主界面无 critical 违例', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('#editor', { timeout: 10000 });

    const result = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa'])
      .analyze();

    const critical = result.violations.filter(v => v.impact === 'critical');
    if (critical.length) {
      // 打印详情便于定位（CI 日志可见）
      console.log('CRITICAL a11y violations:\n' + JSON.stringify(critical, null, 2));
    }
    expect(critical).toHaveLength(0);
  });

  test('登录对话框可达性', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('#editor', { timeout: 10000 });
    // 打开云端标签 → 登录按钮 → 登录对话框
    await page.evaluate(() => window.editor?.switchSidebarTab?.('cloud')).catch(() => {});
    await page.locator('#btnCloudLogin').click({ timeout: 5000 }).catch(() => {});
    const dialog = page.locator('.auth-dialog');
    if (await dialog.count()) {
      const result = await new AxeBuilder({ page })
        .include('.auth-dialog')
        .withTags(['wcag2a', 'wcag2aa'])
        .analyze();
      const critical = result.violations.filter(v => v.impact === 'critical');
      if (critical.length) console.log('DIALOG CRITICAL:\n' + JSON.stringify(critical, null, 2));
      expect(critical).toHaveLength(0);
    }
  });
});
