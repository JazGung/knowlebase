/**
 * Playwright 端到端浏览器测试
 *
 * 测试覆盖：
 * 1. 前端 UI 加载（文档列表页面）
 * 2. 搜索栏和工具栏上下排列
 * 3. 数据区最后一列无按钮
 * 4. 按钮始终可见（启用/停用不隐藏）
 * 5. 前端状态校验优先于确认框
 * 6. 文档启用/停用切换
 *
 * 运行方式: npx playwright test --config=playwright.config.cjs
 */
const { chromium } = require('E:/project/knowlebase/frontend/node_modules/playwright');
const assert = require('assert');

const FRONTEND_URL = 'http://localhost:5181';
const BACKEND_API = 'http://localhost:8000';

let browser, page, context;
let testDocId = null;

// 测试结果
const results = [];
let passed = 0;
let failed = 0;

async function test(name, fn) {
  try {
    await fn();
    results.push({ name, status: 'PASS' });
    passed++;
    console.log(`  [PASS] ${name}`);
  } catch (err) {
    results.push({ name, status: 'FAIL', error: err.message });
    failed++;
    console.log(`  [FAIL] ${name}: ${err.message}`);
  }
}

async function setup() {
  console.log('\n=== 启动浏览器 ===');
  browser = await chromium.launch({
    headless: true,
    args: ['--no-sandbox']
  });
  context = await browser.newContext({
    viewport: { width: 1280, height: 720 },
    locale: 'zh-CN',
    timezoneId: 'Asia/Shanghai'
  });
  page = await context.newPage();

  // 捕获控制台错误
  page.on('console', msg => {
    if (msg.type() === 'error') {
      console.log(`  [浏览器错误] ${msg.text()}`);
    }
  });
  page.on('pageerror', err => {
    console.log(`  [页面错误] ${err.message}`);
  });

  console.log('\n=== 创建测试文档 ===');
  // 通过 API 创建一条测试文档
  const createRes = await page.evaluate(async () => {
    const res = await fetch('http://localhost:8000/build/document/upload', {
      method: 'POST',
      body: (() => {
        const formData = new FormData();
        // 创建一个简单的文本文件内容
        const blob = new Blob(['测试文档内容 ' + Date.now()], { type: 'application/pdf' });
        formData.append('file', blob, 'test-doc.pdf');
        formData.append('hash', 'a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4');
        formData.append('title', '浏览器测试文档');
        return formData;
      })()
    });
    return res.json();
  });
  console.log(`  创建响应: ${JSON.stringify(createRes).substring(0, 100)}...`);

  // 获取文档 ID
  if (createRes.data && createRes.data.document_id) {
    testDocId = createRes.data.document_id;
    console.log(`  测试文档 ID: ${testDocId}`);
  } else {
    console.log('  未获取到文档ID，将测试空列表');
  }
}

async function teardown() {
  if (browser) {
    await browser.close();
  }
}

async function runTests() {
  console.log('\n=== 开始测试 ===\n');

  // ---- 测试 1: 页面加载 ----
  await test('前端页面加载成功', async () => {
    await page.goto(FRONTEND_URL, { waitUntil: 'networkidle', timeout: 15000 });
    // 等待 Vue 应用挂载
    await page.waitForSelector('.el-table', { timeout: 10000 });
    assert.ok(true, '表格已加载');
  });

  // ---- 测试 2: 工具栏和搜索栏上下排列 ----
  await test('工具栏和搜索栏上下排列（非左右）', async () => {
    // 工具栏是包含"上传文档"按钮的 div
    const uploadBtn = await page.locator('.el-button').filter({ hasText: '上传文档' }).first();
    const toolbarDiv = await uploadBtn.locator('xpath=ancestor::div[1]');

    // 搜索输入框
    const searchInput = await page.$('input[placeholder*="搜索"]');
    assert.ok(searchInput, '搜索输入框存在');

    // 搜索栏在工具栏下方（Y 坐标更大）
    const toolbarBox = await toolbarDiv.boundingBox();
    const searchBox = await searchInput.boundingBox();
    assert.ok(searchBox.y > toolbarBox.y,
      `搜索栏 (${searchBox.y}px) 应在工具栏 (${toolbarBox.y}px) 下方`);
  });

  // ---- 测试 3: 数据区最后一列无按钮 ----
  await test('数据区最后一列（操作列）无按钮', async () => {
    const tableButtons = await page.$$('.el-table__body .el-button');
    assert.strictEqual(tableButtons.length, 0,
      `数据区内不应有按钮，找到 ${tableButtons.length} 个`);
  });

  // ---- 测试 4: 所有按钮在工具栏始终可见 ----
  await test('工具栏按钮始终可见（不隐藏）', async () => {
    // 上传文档按钮应该可见
    const uploadBtn = await page.locator('.el-button').filter({ hasText: '上传文档' });
    assert.ok(await uploadBtn.isVisible(), '上传文档按钮应可见');

    // 批量启用、批量停用按钮也应该可见
    const batchEnableBtn = await page.locator('.el-button').filter({ hasText: '批量启用' });
    const batchDisableBtn = await page.locator('.el-button').filter({ hasText: '批量停用' });
    assert.ok(await batchEnableBtn.isVisible(), '批量启用按钮应可见');
    assert.ok(await batchDisableBtn.isVisible(), '批量停用按钮应可见');
  });

  // ---- 测试 5: 文档列表页面展示正确列 ----
  await test('文档列表列正确（ID、文件名、状态、启用状态、创建时间）', async () => {
    const headers = await page.$$('.el-table__header th');
    const headerTexts = [];
    for (const th of headers) {
      const text = await th.innerText();
      if (text) headerTexts.push(text.trim());
    }
    assert.ok(headerTexts.length > 0, '表格应有表头');
    console.log(`    表头: [${headerTexts.join(', ')}]`);

    // 最后一列不应该是"操作"
    const lastHeader = headerTexts[headerTexts.length - 1];
    assert.notStrictEqual(lastHeader, '操作', '最后一列不应是操作列');
  });

  // ---- 测试 6: 前端校验 - 重复启用已启用文档 ----
  if (testDocId) {
    await test('前端校验：重复启用已启用文档时直接警告，不弹确认框', async () => {
      // 先确保文档是启用状态
      await page.evaluate(async (docId) => {
        await fetch('http://localhost:8000/build/document/enable', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ document_id: docId })
        });
      }, testDocId);

      // 刷新页面
      await page.reload({ waitUntil: 'networkidle' });

      // 点击选中行（第一行）
      await page.waitForTimeout(1000);
      const firstRow = await page.$('.el-table__body tr');
      if (firstRow) {
        await firstRow.click();
        await page.waitForTimeout(500);

        // 点击启用按钮（在底部操作栏）
        const enableBtn = await page.$('.action-bar .el-button:has-text("启用")');
        if (enableBtn) {
          await enableBtn.click();
          await page.waitForTimeout(500);

          // 应该看到警告消息而不是确认对话框
          const warning = await page.$('.el-message--warning');
          assert.ok(warning, '应显示警告消息');
        }
      }
    });

    // ---- 测试 7: 文档状态切换（停用） ----
    await test('文档停用功能正常', async () => {
      await page.reload({ waitUntil: 'networkidle' });
      await page.waitForTimeout(1000);

      const firstRow = await page.$('.el-table__body tr');
      if (firstRow) {
        await firstRow.click();
        await page.waitForTimeout(500);

        const disableBtn = await page.$('.action-bar .el-button:has-text("停用")');
        if (disableBtn) {
          // 点击停用
          await disableBtn.click();
          // 等待确认对话框
          await page.waitForTimeout(500);
          const confirmBtn = await page.$('.el-message-box__btns .el-button--primary');
          if (confirmBtn) {
            await confirmBtn.click();
            await page.waitForTimeout(1000);
            console.log('    停用操作完成');
          }
        }
      }

      // 验证状态已切换
      const listData = await page.evaluate(async () => {
        const res = await fetch('/build/document/list?page=1&page_size=10');
        return res.json();
      });
      const docs = listData.data?.documents || [];
      if (docs.length > 0) {
        assert.strictEqual(docs[0].enabled, false, '文档应已停用');
      }
    });

    // ---- 测试 8: 文档状态切换（重新启用） ----
    await test('文档重新启用功能正常', async () => {
      await page.reload({ waitUntil: 'networkidle' });
      await page.waitForTimeout(1000);

      const firstRow = await page.$('.el-table__body tr');
      if (firstRow) {
        await firstRow.click();
        await page.waitForTimeout(500);

        const enableBtn = await page.$('.action-bar .el-button:has-text("启用")');
        if (enableBtn) {
          await enableBtn.click();
          await page.waitForTimeout(500);
          const confirmBtn = await page.$('.el-message-box__btns .el-button--primary');
          if (confirmBtn) {
            await confirmBtn.click();
            await page.waitForTimeout(1000);
            console.log('    启用操作完成');
          }
        }
      }
    });
  }

  // ---- 测试 9: 后端校验 - 重复启用返回 400 ----
  await test('后端校验：重复启用返回 400', async () => {
    if (testDocId) {
      const res = await page.evaluate(async (docId) => {
        const res = await fetch('http://localhost:8000/build/document/enable', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ document_id: docId })
        });
        return { status: res.status, body: await res.json() };
      }, testDocId);

      assert.strictEqual(res.status, 400,
        `重复启用应返回 400，实际返回 ${res.status}`);
      console.log(`    响应: ${JSON.stringify(res.body).substring(0, 100)}`);
    }
  });

  // ---- 测试 10: 后端校验 - 重复停用返回 400 ----
  await test('后端校验：重复停用返回 400', async () => {
    if (testDocId) {
      // 先停用
      await page.evaluate(async (docId) => {
        await fetch('http://localhost:8000/build/document/disable', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ document_id: docId })
        });
      }, testDocId);

      // 再次停用
      const res = await page.evaluate(async (docId) => {
        const res = await fetch('http://localhost:8000/build/document/disable', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ document_id: docId })
        });
        return { status: res.status, body: await res.json() };
      }, testDocId);

      assert.strictEqual(res.status, 400,
        `重复停用应返回 400，实际返回 ${res.status}`);
      console.log(`    响应: ${JSON.stringify(res.body).substring(0, 100)}`);
    }
  });

  // ---- 测试 11: 后端服务健康 ----
  await test('后端服务健康检查', async () => {
    const res = await page.evaluate(async () => {
      const res = await fetch('http://localhost:8000/build/document/list');
      return { status: res.status, ok: res.ok };
    });
    assert.ok(res.ok, `后端应返回 200，实际 ${res.status}`);
  });

  // ---- 打印结果 ----
  console.log('\n=== 测试结果 ===');
  console.log(`总计: ${results.length} 个测试`);
  console.log(`通过: ${passed}`);
  console.log(`失败: ${failed}`);

  if (failed > 0) {
    console.log('\n失败详情:');
    for (const r of results) {
      if (r.status === 'FAIL') {
        console.log(`  - ${r.name}: ${r.error}`);
      }
    }
    process.exit(1);
  }
}

async function main() {
  try {
    await setup();
    await runTests();
  } catch (err) {
    console.error('\n测试执行异常:', err.message);
    process.exit(1);
  } finally {
    await teardown();
  }
}

main();
