// Full upload flow test
const { chromium } = require('playwright');
const fs = require('fs');

(async () => {
  // Create a simple test PDF file (minimal valid PDF) with unique content for unique hash
  const uniqueContent = `test-file-${Date.now()}-content`;
  const testPdfContent = Buffer.from(`%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[]/Count 0>>endobj\n%% Test: ${uniqueContent}`);
  const testFilePath = `E:/project/knowlebase/frontend/test-file-${Date.now()}.pdf`;
  fs.writeFileSync(testFilePath, testPdfContent);
  console.log('Created test file:', testPdfContent.length, 'bytes');

  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const page = await browser.newPage();

  const apiResponses = [];
  page.on('response', async response => {
    if (response.url().includes('/build/document/')) {
      const status = response.status();
      let body;
      try { body = await response.json(); } catch(e) { body = {}; }
      apiResponses.push({ url: response.url(), status, body });
      console.log(`\nAPI: ${response.url()}`);
      console.log(`  Status: ${status}`);
      console.log(`  Body code:`, body?.code, 'message:', body?.message);
    }
  });

  const pageErrors = [];
  page.on('pageerror', error => {
    pageErrors.push(error.message);
    console.log('\nPage JS Error:', error.message);
  });

  // Step 1: Navigate
  console.log('\n=== Step 1: Navigate to frontend ===');
  await page.goto('http://localhost:5173');
  await page.waitForTimeout(1000);
  console.log('Title:', await page.title());

  // Step 2: Click upload button
  console.log('\n=== Step 2: Click upload button ===');
  const uploadBtn = await page.$('button:has-text("上传文档")');
  if (!uploadBtn) { console.log('ERROR: Upload button not found'); await browser.close(); process.exit(1); }
  await uploadBtn.click();
  await page.waitForTimeout(1000);
  console.log('Dialog opened');

  // Step 3: Select file via file input
  console.log('\n=== Step 3: Select file ===');
  const fileInput = await page.$('input[type="file"]');
  if (!fileInput) { console.log('ERROR: File input not found'); await browser.close(); process.exit(1); }
  await fileInput.setInputFiles(testFilePath);
  await page.waitForTimeout(500);
  console.log('File selected');

  // Step 4: Click confirm
  console.log('\n=== Step 4: Click confirm ===');
  const confirmBtn = await page.$('.el-dialog__footer button.el-button--primary');
  if (!confirmBtn) { console.log('ERROR: Confirm button not found'); await browser.close(); process.exit(1); }
  await confirmBtn.click();
  console.log('Confirm clicked');

  // Wait for upload to complete
  console.log('\n=== Step 5: Wait for upload ===');
  await page.waitForTimeout(8000);

  // Check results
  const bodyText = await page.textContent('body');
  console.log('\nPage content (first 600 chars):');
  console.log(bodyText.substring(0, 600));

  await page.screenshot({ path: 'E:/project/knowlebase/frontend/screenshot-result.png' });

  // Check for success in result table
  const successText = bodyText.includes('成功') || bodyText.includes('success');
  const errorText = bodyText.includes('失败') || bodyText.includes('error') || bodyText.includes('错误');

  console.log('\n===================');
  console.log('TEST RESULT');
  console.log('===================');
  console.log('API calls:', apiResponses.length);
  for (const r of apiResponses) {
    console.log(`  ${r.url.split('/').slice(-3).join('/')} -> code=${r.body?.code}, msg=${r.body?.message}`);
  }
  console.log('Page JS errors:', pageErrors.length);
  pageErrors.forEach(e => console.log('  -', e));
  console.log('Success indicator:', successText);
  console.log('Error indicator:', errorText);

  if (apiResponses.some(r => r.body?.code === 0) && !pageErrors.length) {
    console.log('\n*** UPLOAD TEST PASSED ***');
  } else {
    console.log('\n*** UPLOAD TEST FAILED ***');
    process.exit(1);
  }

  // Cleanup
  fs.unlinkSync(testFilePath);
  await browser.close();
})();
