# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: reprocess.spec.js >> 文档重新处理功能 >> 重新处理文档应显示成功提示或错误提示
- Location: e2e\reprocess.spec.js:12:3

# Error details

```
Error: 重新处理失败: 重新处理失败：文档重新处理失败

expect(received).toBe(expected) // Object.is equality

Expected: false
Received: true
```

# Page snapshot

```yaml
- generic [ref=e1]:
  - generic [ref=e3]:
    - generic [ref=e4]:
      - img [ref=e6]
      - generic [ref=e8]: 知识库管理系统
    - main [ref=e9]:
      - generic [ref=e10]:
        - generic [ref=e11]:
          - button "上传文档" [ref=e12] [cursor=pointer]:
            - generic [ref=e13]:
              - img [ref=e15]
              - text: 上传文档
          - button "批量启用" [ref=e17] [cursor=pointer]:
            - generic [ref=e18]:
              - img [ref=e20]
              - text: 批量启用
          - button "批量停用" [ref=e22] [cursor=pointer]:
            - generic [ref=e23]:
              - img [ref=e25]
              - text: 批量停用
          - button "重新处理" [ref=e27] [cursor=pointer]:
            - generic [ref=e28]:
              - img [ref=e30]
              - text: 重新处理
        - generic [ref=e33]:
          - textbox "搜索文件名、标题..." [ref=e35]
          - button "搜索" [ref=e37] [cursor=pointer]:
            - generic [ref=e38]:
              - img [ref=e40]
              - text: 搜索
        - generic [ref=e43]:
          - table [ref=e45]:
            - rowgroup [ref=e54]:
              - row "选择所有行 文件名 标题 处理状态 启用 大小 创建时间" [ref=e55]:
                - columnheader "选择所有行" [ref=e56]:
                  - generic "选择所有行" [ref=e58] [cursor=pointer]:
                    - generic [ref=e59]:
                      - checkbox "选择所有行" [checked=mixed]
                - columnheader "文件名" [ref=e61]:
                  - generic [ref=e62]: 文件名
                - columnheader "标题" [ref=e63]:
                  - generic [ref=e64]: 标题
                - columnheader "处理状态" [ref=e65]:
                  - generic [ref=e66]: 处理状态
                - columnheader "启用" [ref=e67]:
                  - generic [ref=e68]: 启用
                - columnheader "大小" [ref=e69]:
                  - generic [ref=e70]: 大小
                - columnheader "创建时间" [ref=e71]:
                  - generic [ref=e72]: 创建时间
          - table [ref=e77]:
            - rowgroup [ref=e86]:
              - row "选择当前行 GB_T 8566-2022：系统与软件工程 软件生存周期过程.pdf GB_T 8566-2022：系统与软件工程 软件生存周期过程.pdf 成功 是 547.8 KB 2026/4/12 14:49:57" [ref=e87]:
                - cell "选择当前行" [ref=e88]:
                  - generic "选择当前行" [ref=e90] [cursor=pointer]:
                    - generic [ref=e91]:
                      - checkbox "选择当前行"
                - cell "GB_T 8566-2022：系统与软件工程 软件生存周期过程.pdf" [ref=e93]:
                  - generic [ref=e94]: GB_T 8566-2022：系统与软件工程 软件生存周期过程.pdf
                - cell "GB_T 8566-2022：系统与软件工程 软件生存周期过程.pdf" [ref=e95]:
                  - generic [ref=e96]: GB_T 8566-2022：系统与软件工程 软件生存周期过程.pdf
                - cell "成功" [ref=e97]:
                  - generic [ref=e100]: 成功
                - cell "是" [ref=e101]:
                  - generic [ref=e104]: 是
                - cell "547.8 KB" [ref=e105]:
                  - generic [ref=e106]: 547.8 KB
                - cell "2026/4/12 14:49:57" [ref=e107]:
                  - generic [ref=e108]: 2026/4/12 14:49:57
              - row "选择当前行 巩佳知-简历 - 副本.pdf 巩佳知-简历 - 副本.pdf 成功 是 333.5 KB 2026/4/12 14:49:57" [ref=e109]:
                - cell "选择当前行" [ref=e110]:
                  - generic "选择当前行" [ref=e112] [cursor=pointer]:
                    - generic [ref=e113]:
                      - checkbox "选择当前行" [checked]
                - cell "巩佳知-简历 - 副本.pdf" [ref=e115]:
                  - generic [ref=e116]: 巩佳知-简历 - 副本.pdf
                - cell "巩佳知-简历 - 副本.pdf" [ref=e117]:
                  - generic [ref=e118]: 巩佳知-简历 - 副本.pdf
                - cell "成功" [ref=e119]:
                  - generic [ref=e122]: 成功
                - cell "是" [ref=e123]:
                  - generic [ref=e126]: 是
                - cell "333.5 KB" [ref=e127]:
                  - generic [ref=e128]: 333.5 KB
                - cell "2026/4/12 14:49:57" [ref=e129]:
                  - generic [ref=e130]: 2026/4/12 14:49:57
              - row "选择当前行 fresh-doc.pdf fresh-doc.pdf 待处理 是 598 B 2026/4/12 14:45:44" [ref=e131]:
                - cell "选择当前行" [ref=e132]:
                  - generic "选择当前行" [ref=e134] [cursor=pointer]:
                    - generic [ref=e135]:
                      - checkbox "选择当前行"
                - cell "fresh-doc.pdf" [ref=e137]:
                  - generic [ref=e138]: fresh-doc.pdf
                - cell "fresh-doc.pdf" [ref=e139]:
                  - generic [ref=e140]: fresh-doc.pdf
                - cell "待处理" [ref=e141]:
                  - generic [ref=e144]: 待处理
                - cell "是" [ref=e145]:
                  - generic [ref=e148]: 是
                - cell "598 B" [ref=e149]:
                  - generic [ref=e150]: 598 B
                - cell "2026/4/12 14:45:44" [ref=e151]:
                  - generic [ref=e152]: 2026/4/12 14:45:44
              - row "选择当前行 test-doc.pdf ²âÊÔÎÄµµ 待处理 是 588 B 2026/4/12 14:33:54" [ref=e153]:
                - cell "选择当前行" [ref=e154]:
                  - generic "选择当前行" [ref=e156] [cursor=pointer]:
                    - generic [ref=e157]:
                      - checkbox "选择当前行"
                - cell "test-doc.pdf" [ref=e159]:
                  - generic [ref=e160]: test-doc.pdf
                - cell "²âÊÔÎÄµµ" [ref=e161]:
                  - generic [ref=e162]: ²âÊÔÎÄµµ
                - cell "待处理" [ref=e163]:
                  - generic [ref=e166]: 待处理
                - cell "是" [ref=e167]:
                  - generic [ref=e170]: 是
                - cell "588 B" [ref=e171]:
                  - generic [ref=e172]: 588 B
                - cell "2026/4/12 14:33:54" [ref=e173]:
                  - generic [ref=e174]: 2026/4/12 14:33:54
        - generic [ref=e176]:
          - button "查看详情" [ref=e177] [cursor=pointer]:
            - generic [ref=e178]: 查看详情
          - button "停用" [ref=e180] [cursor=pointer]:
            - generic [ref=e181]:
              - img [ref=e183]
              - text: 停用
          - button "重新处理" [active] [ref=e185] [cursor=pointer]:
            - generic [ref=e186]:
              - img [ref=e188]
              - text: 重新处理
          - generic [ref=e190]: 已选中 1 项
        - generic [ref=e192]:
          - generic [ref=e193]: 共 4 条
          - generic [ref=e196] [cursor=pointer]:
            - generic:
              - combobox [ref=e198]
              - generic [ref=e199]: 20条/页
            - img [ref=e202]
          - button "上一页" [disabled] [ref=e204]:
            - generic:
              - img
          - list [ref=e205]:
            - listitem "第 1 页" [ref=e206]: "1"
          - button "下一页" [disabled] [ref=e207]:
            - generic:
              - img
          - generic [ref=e208]:
            - generic [ref=e209]: 前往
            - spinbutton "页" [ref=e212]: "1"
            - generic [ref=e213]: 页
  - alert [ref=e214]:
    - img [ref=e216]
    - paragraph [ref=e218]: 重新处理失败：文档重新处理失败
```

# Test source

```ts
  1  | // @ts-check
  2  | import { test, expect } from '@playwright/test';
  3  | 
  4  | const BASE_URL = 'http://localhost:5173';
  5  | 
  6  | test.describe('文档重新处理功能', () => {
  7  |   test.beforeEach(async ({ page }) => {
  8  |     await page.goto(BASE_URL);
  9  |     await expect(page.getByRole('button', { name: '上传文档' })).toBeVisible();
  10 |   });
  11 | 
  12 |   test('重新处理文档应显示成功提示或错误提示', async ({ page }) => {
  13 |     // 1. 通过 dispatchEvent 选中目标文档行
  14 |     const targetText = '巩佳知-简历';
  15 |     const row = page.locator('tr').filter({ hasText: targetText }).first();
  16 |     await expect(row).toBeVisible();
  17 |     const checkbox = row.locator('input[type="checkbox"]').first();
  18 |     await checkbox.evaluate((el) => {
  19 |       el.checked = true;
  20 |       el.dispatchEvent(new Event('change', { bubbles: true }));
  21 |     });
  22 | 
  23 |     // 确认已选中
  24 |     await expect(page.locator('text=已选中 1 项')).toBeVisible();
  25 | 
  26 |     // 2. 点击底部工具栏的"重新处理"按钮（小按钮）
  27 |     const reprocessBtn = page.locator('.el-button--small').filter({ hasText: '重新处理' });
  28 |     await expect(reprocessBtn).toBeVisible();
  29 |     await expect(reprocessBtn).toBeEnabled();
  30 |     await reprocessBtn.click();
  31 | 
  32 |     // 3. 等待确认对话框
  33 |     const confirmDialog = page.locator('.el-message-box');
  34 |     await expect(confirmDialog).toBeVisible();
  35 | 
  36 |     // 4. 点击确定
  37 |     await page.getByRole('button', { name: '确定' }).click();
  38 | 
  39 |     // 5. 等待结果：成功提示或错误提示
  40 |     const successMsg = page.locator('.el-message--success');
  41 |     const errorMsg = page.locator('.el-message--error');
  42 | 
  43 |     await Promise.race([
  44 |       expect(successMsg).toBeVisible({ timeout: 10000 }),
  45 |       expect(errorMsg).toBeVisible({ timeout: 10000 }),
  46 |     ]);
  47 | 
  48 |     // 6. 检查结果
  49 |     const errorVisible = await errorMsg.isVisible().catch(() => false);
  50 |     if (errorVisible) {
  51 |       const errorText = await errorMsg.textContent();
  52 |       console.log('错误提示内容:', errorText);
> 53 |       expect(errorVisible, `重新处理失败: ${errorText}`).toBe(false);
     |                                                    ^ Error: 重新处理失败: 重新处理失败：文档重新处理失败
  54 |     } else {
  55 |       const successVisible = await successMsg.isVisible();
  56 |       const successText = await successMsg.textContent();
  57 |       console.log('成功提示内容:', successText);
  58 |       expect(successVisible).toBeTruthy();
  59 |     }
  60 |   });
  61 | });
  62 | 
```