// @ts-check
import { test, expect } from '@playwright/test';

const BASE_URL = 'http://localhost:5173';

test.describe('文档重新处理功能', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(BASE_URL);
    await expect(page.getByRole('button', { name: '上传文档' })).toBeVisible();
  });

  test('重新处理文档应显示成功提示或错误提示', async ({ page }) => {
    // 1. 通过 dispatchEvent 选中目标文档行
    const targetText = '巩佳知-简历';
    const row = page.locator('tr').filter({ hasText: targetText }).first();
    await expect(row).toBeVisible();
    const checkbox = row.locator('input[type="checkbox"]').first();
    await checkbox.evaluate((el) => {
      el.checked = true;
      el.dispatchEvent(new Event('change', { bubbles: true }));
    });

    // 确认已选中
    await expect(page.locator('text=已选中 1 项')).toBeVisible();

    // 2. 点击底部工具栏的"重新处理"按钮（小按钮）
    const reprocessBtn = page.locator('.el-button--small').filter({ hasText: '重新处理' });
    await expect(reprocessBtn).toBeVisible();
    await expect(reprocessBtn).toBeEnabled();
    await reprocessBtn.click();

    // 3. 等待确认对话框
    const confirmDialog = page.locator('.el-message-box');
    await expect(confirmDialog).toBeVisible();

    // 4. 点击确定
    await page.getByRole('button', { name: '确定' }).click();

    // 5. 等待结果：成功提示或错误提示
    const successMsg = page.locator('.el-message--success');
    const errorMsg = page.locator('.el-message--error');

    await Promise.race([
      expect(successMsg).toBeVisible({ timeout: 10000 }),
      expect(errorMsg).toBeVisible({ timeout: 10000 }),
    ]);

    // 6. 检查结果
    const errorVisible = await errorMsg.isVisible().catch(() => false);
    if (errorVisible) {
      const errorText = await errorMsg.textContent();
      console.log('错误提示内容:', errorText);
      expect(errorVisible, `重新处理失败: ${errorText}`).toBe(false);
    } else {
      const successVisible = await successMsg.isVisible();
      const successText = await successMsg.textContent();
      console.log('成功提示内容:', successText);
      expect(successVisible).toBeTruthy();
    }
  });
});
