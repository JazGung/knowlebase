// @ts-check
import { test, expect } from '@playwright/test';

const BASE_URL = 'http://localhost:5173';

test.describe('文档列表管理功能', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(BASE_URL);
    await expect(page.getByRole('button', { name: '上传文档' })).toBeVisible();
  });

  test('页面加载后显示文档列表', async ({ page }) => {
    // 表格应可见
    const table = page.locator('.el-table');
    await expect(table).toBeVisible({ timeout: 10000 });

    // 表格至少渲染了表头
    const tableHeader = page.locator('.el-table__header-wrapper');
    await expect(tableHeader).toBeVisible();
  });

  test('搜索功能', async ({ page }) => {
    await expect(page.locator('.el-table')).toBeVisible({ timeout: 10000 });

    // el-input 组件内部渲染了一个 <input>，placeholder="搜索文件名、标题..."
    const searchInput = page.getByPlaceholder('搜索文件名、标题');
    await expect(searchInput).toBeVisible();

    // 输入搜索关键词
    await searchInput.fill('test');
    await searchInput.press('Enter');

    // 表格应仍然可见（数据可能为空但表格结构不应报错）
    await expect(page.locator('.el-table')).toBeVisible({ timeout: 5000 });

    // 清除搜索
    await searchInput.clear();
    await searchInput.press('Enter');
    await expect(page.locator('.el-table')).toBeVisible({ timeout: 5000 });
  });

  test('未选中记录时操作按钮置灰', async ({ page }) => {
    await expect(page.locator('.el-table')).toBeVisible({ timeout: 10000 });

    // 底部工具栏按钮在无选中时应禁用
    const viewDetailBtn = page.getByRole('button', { name: '查看详情' });
    await expect(viewDetailBtn).toBeDisabled();
  });

  test('选中文档后双击打开详情', async ({ page }) => {
    await expect(page.locator('.el-table')).toBeVisible({ timeout: 10000 });

    // 使用 evaluate 选中第一行（避免 viewport 问题）
    const firstRow = page.locator('.el-table__body-wrapper tr').first();
    const rowCount = await page.locator('.el-table__body-wrapper tr').count();
    if (rowCount > 0) {
      const checkbox = firstRow.locator('input[type="checkbox"]').first();
      await checkbox.evaluate((el) => {
        el.checked = true;
        el.dispatchEvent(new Event('change', { bubbles: true }));
      });

      // 选中指示应显示
      await expect(page.locator('text=已选中 1 项')).toBeVisible();

      // 双击打开详情
      await firstRow.dblclick();

      // 详情对话框应打开
      const detailDialog = page.locator('.el-dialog').filter({ hasText: '文档详情' });
      await expect(detailDialog).toBeVisible({ timeout: 5000 });
    }
  });

  test('选中栏指示正确显示', async ({ page }) => {
    await expect(page.locator('.el-table')).toBeVisible({ timeout: 10000 });

    const rows = page.locator('.el-table__body-wrapper tr');
    const count = await rows.count();

    if (count >= 2) {
      // 选中两个文档（使用 evaluate 避免 viewport 问题）
      const checkbox1 = rows.nth(0).locator('input[type="checkbox"]').first();
      await checkbox1.evaluate((el) => {
        el.checked = true;
        el.dispatchEvent(new Event('change', { bubbles: true }));
      });
      await expect(page.locator('text=已选中 1 项')).toBeVisible();

      const checkbox2 = rows.nth(1).locator('input[type="checkbox"]').first();
      await checkbox2.evaluate((el) => {
        el.checked = true;
        el.dispatchEvent(new Event('change', { bubbles: true }));
      });
      await expect(page.locator('text=已选中 2 项')).toBeVisible();
    }
  });
});
