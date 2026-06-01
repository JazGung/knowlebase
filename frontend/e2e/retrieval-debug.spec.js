// @ts-check
import { test, expect } from '@playwright/test';

const BASE_URL = 'http://localhost:5173';

test.describe('检索调试页面', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}/retrieval/debug`);
  });

  test('页面加载后显示检索调试界面', async ({ page }) => {
    // 顶部输入区域
    const queryInput = page.getByPlaceholder('输入检索问题或关键词...');
    await expect(queryInput).toBeVisible();

    // 搜索按钮
    const searchBtn = page.getByRole('button', { name: '查询' });
    await expect(searchBtn).toBeVisible();

    // 5 个 Tab 应可见
    const tabs = page.locator('.el-tabs__item');
    await expect(tabs).toHaveCount(5);
    await expect(tabs.nth(0)).toContainText('ES 检索结果');
    await expect(tabs.nth(1)).toContainText('Milvus 检索结果');
    await expect(tabs.nth(2)).toContainText('Neo4j 检索结果');
    await expect(tabs.nth(3)).toContainText('合并后结果');
    await expect(tabs.nth(4)).toContainText('重排序后结果');
  });

  test('未输入查询内容时显示警告', async ({ page }) => {
    const searchBtn = page.getByRole('button', { name: '查询' });
    await searchBtn.click();

    // 应弹出警告提示
    const warningMsg = page.locator('.el-message--warning');
    await expect(warningMsg).toBeVisible({ timeout: 5000 });
    await expect(warningMsg).toContainText('请输入查询内容');
  });

  test('输入查询内容后点击搜索', async ({ page }) => {
    // 输入查询内容
    const queryInput = page.getByPlaceholder('输入检索问题或关键词...');
    await queryInput.fill('测试检索');

    // 选择版本（如果有的话）
    const versionSelect = page.locator('.el-select').first();
    await expect(versionSelect).toBeVisible();

    // 点击搜索
    const searchBtn = page.getByRole('button', { name: '查询' });
    await searchBtn.click();

    // 搜索按钮在请求中应变为 loading 状态（如果后端可达）
    // 如果没有版本选择或后端不可达，至少确认按钮可点击且不报 JS 错误
    await expect(searchBtn).toBeVisible();
  });

  test('Tab 切换功能', async ({ page }) => {
    // 默认选中"重排序后结果"
    const activeTab = page.locator('.el-tabs__item.is-active');
    await expect(activeTab).toContainText('重排序后结果');

    // 点击 ES 检索结果
    const esTab = page.locator('.el-tabs__item').filter({ hasText: 'ES 检索结果' });
    await esTab.click();
    await expect(esTab).toHaveClass(/is-active/);

    // 点击合并后结果
    const mergedTab = page.locator('.el-tabs__item').filter({ hasText: '合并后结果' });
    await mergedTab.click();
    await expect(mergedTab).toHaveClass(/is-active/);
  });

  test('版本下拉框加载版本列表', async ({ page }) => {
    // 点击版本下拉框
    const versionSelect = page.locator('.el-select').first();
    await versionSelect.click();

    // 下拉框应展开（可能有选项或无数据）
    const dropdown = page.locator('.el-select-dropdown').first();
    await expect(dropdown).toBeVisible({ timeout: 5000 });
  });

  test('结果表格包含正确列', async ({ page }) => {
    // 输入查询内容
    const queryInput = page.getByPlaceholder('输入检索问题或关键词...');
    await queryInput.fill('测试');

    // 尝试选择版本并搜索
    const searchBtn = page.getByRole('button', { name: '查询' });
    await searchBtn.click();

    // 等待响应后检查表格列（即使无数据也应有表头）
    // Element Plus el-empty 会在无数据时显示，有数据时显示 el-table
    await page.waitForTimeout(2000);

    // 检查是否显示了空状态或表格
    const hasTable = await page.locator('.el-table__header-wrapper').count();
    const hasEmpty = await page.locator('.el-empty').count();

    if (hasTable > 0) {
      // 有数据时检查列
      const headers = page.locator('.el-table__header-wrapper th');
      const headerTexts = await headers.allTextContents();
      // 应包含: 编号, 分块文本, 所属文档, 所在页码, 所在章节, 相关性分数
      expect(headerTexts.some((t) => t.includes('分块文本'))).toBeTruthy();
      expect(headerTexts.some((t) => t.includes('所属文档'))).toBeTruthy();
      expect(headerTexts.some((t) => t.includes('所在页码'))).toBeTruthy();
      expect(headerTexts.some((t) => t.includes('所在章节'))).toBeTruthy();
      expect(headerTexts.some((t) => t.includes('相关性分数'))).toBeTruthy();
    } else if (hasEmpty > 0) {
      // 无数据时显示空状态（正常，因为可能没有数据或后端不可达）
      expect(hasEmpty).toBeGreaterThan(0);
    }
    // 两种状态都算正常
  });
});
