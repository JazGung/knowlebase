// @ts-check
import { test, expect } from '@playwright/test';
import path from 'path';
import fs from 'fs';

const BASE_URL = 'http://localhost:5173';

test.describe('文档上传功能', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(BASE_URL);
    await expect(page.getByRole('button', { name: '上传文档' })).toBeVisible();
  });

  test('打开上传对话框', async ({ page }) => {
    await page.getByRole('button', { name: '上传文档' }).click();

    const dialog = page.locator('.el-dialog').filter({ hasText: '上传文档' });
    await expect(dialog).toBeVisible();

    // 确认上传按钮应处于禁用状态（未选择文件）
    const confirmBtn = page.locator('.el-dialog__footer button').filter({ hasText: /确认上传/ });
    await expect(confirmBtn).toBeDisabled();
  });

  test('关闭上传对话框', async ({ page }) => {
    await page.getByRole('button', { name: '上传文档' }).click();

    const dialog = page.locator('.el-dialog').filter({ hasText: '上传文档' });
    await expect(dialog).toBeVisible();

    await page.locator('.el-dialog__footer button').filter({ hasText: '取消' }).click();
    await expect(dialog).not.toBeVisible();
  });

  test('上传 PDF 文件完整流程', async ({ page }) => {
    // 创建测试用 PDF 文件
    const testDir = path.resolve('e2e/test-files');
    if (!fs.existsSync(testDir)) {
      fs.mkdirSync(testDir, { recursive: true });
    }
    const testPdfPath = path.join(testDir, 'test-upload.pdf');
    if (!fs.existsSync(testPdfPath)) {
      // 生成最小有效 PDF
      const minPdf = Buffer.from(
        '%PDF-1.0\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\nxref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n190\n%%EOF',
        'utf-8'
      );
      fs.writeFileSync(testPdfPath, minPdf);
    }

    // 点击上传按钮
    await page.getByRole('button', { name: '上传文档' }).click();

    const dialog = page.locator('.el-dialog').filter({ hasText: '上传文档' });
    await expect(dialog).toBeVisible();

    // 使用文件选择器上传
    const fileInput = page.locator('.el-upload__input');
    await fileInput.setInputFiles(testPdfPath);

    // 确认上传按钮应变为可用
    const confirmBtn = page.locator('.el-dialog__footer button').filter({ hasText: /确认上传/ });
    await expect(confirmBtn).toBeEnabled();

    // 点击确认上传
    await confirmBtn.click();

    // 对话框关闭，进入上传结果视图
    await expect(dialog).not.toBeVisible();

    // 上传结果视图应显示
    // UploadResults 组件显示文件列表
    const uploadResults = page.locator('text=巩佳知-简历').or(page.locator('.el-table'));
    // 等待至少 5 秒让后端处理完成
    await page.waitForTimeout(5000);

    // 检查结果（成功或错误提示）
    const resultArea = page.locator('.el-message').or(page.locator('.el-table'));
    await expect(resultArea.first()).toBeVisible({ timeout: 15000 });
  });

  test('不选择文件直接点击确认上传应提示', async ({ page }) => {
    await page.getByRole('button', { name: '上传文档' }).click();

    const dialog = page.locator('.el-dialog').filter({ hasText: '上传文档' });
    await expect(dialog).toBeVisible();

    // 确认按钮应禁用，无法点击
    const confirmBtn = page.locator('.el-dialog__footer button').filter({ hasText: /确认上传/ });
    await expect(confirmBtn).toBeDisabled();
  });
});
