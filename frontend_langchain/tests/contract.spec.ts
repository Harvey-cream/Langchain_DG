import { test, expect, Page } from '@playwright/test';

const result = {
  document_type: '采购合同',
  summary: '双方约定采购设备，包含预付款及违约责任。',
  parties: ['采购方', '供应商'],
  amount: '100000元',
  duration: '一年',
  payment_terms: '签署当日全额付款',
  key_obligations: ['供应商按约定交付设备'],
  risks: [
    {
      title: '单方解约风险',
      risk_level: 'high',
      original_text: '乙方可以随时终止合同且无需退款。',
      reason: '预付款无法收回。',
      suggestion: '约定退款期限和解约条件。',
    },
  ],
};
const completed = {
  status: 'completed',
  document_text: '采购合同\n乙方可以随时终止合同且无需退款。',
  result,
};

async function setup(page: Page) {
  await page.route('http://127.0.0.1:5180/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    let data: unknown;
    if (path === '/api/customers')
      data = { customers: [{ id: 1, name: '示例客户', email: 'buyer@example.com' }] };
    else if (path === '/api/contracts')
      data =
        route.request().method() === 'POST'
          ? { id: 'demo', title: '采购合同', customer_id: 1 }
          : { contracts: [{ id: 'demo', title: '采购合同', customer_id: 1 }] };
    else if (path.endsWith('/analysis')) data = completed;
    else if (path.endsWith('/versions/upload')) data = { version_id: 'v1', run_id: 'r1' };
    else if (path.endsWith('/versions'))
      data = {
        versions: [
          {
            id: 'v1',
            number: 1,
            filename: '采购合同.docx',
            contract_id: 'demo',
            status: 'uploaded',
          },
        ],
      };
    else data = { id: 'demo', title: '采购合同' };
    await route.fulfill({ json: { success: true, data } });
  });
}

test.beforeEach(async ({ page }) => {
  await setup(page);
});

test('workbench searches contracts and opens the review', async ({ page }) => {
  await page.goto('/contracts');
  await expect(page.getByRole('heading', { name: '把合同看清楚，再做决定。' })).toBeVisible();
  await page.getByPlaceholder('搜索合同名称').fill('不存在');
  await expect(page.getByText('没有匹配的合同')).toBeVisible();
  await page.getByPlaceholder('搜索合同名称').fill('');
  await page.getByRole('button', { name: /采购合同.*示例客户/ }).click();
  await expect(page.getByText('单方解约风险')).toBeVisible();
  await page.reload();
  await expect(page.getByText('单方解约风险')).toBeVisible();
  await page.screenshot({ path: 'test-results/contract-review.png', fullPage: true });
});

test('upload dialog creates a contract and uploads a file', async ({ page }) => {
  await page.goto('/contracts');
  await page.getByRole('button', { name: '＋ 上传合同' }).click();
  await page.getByLabel('合同名称').fill('演示协议');
  await page.getByText('新建客户', { exact: true }).click();
  await page.getByText('示例客户', { exact: true }).last().click();
  await page.locator('input[type=file]').setInputFiles({
    name: 'demo.docx',
    mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    buffer: Buffer.from('fixture: upload transport tested independently'),
  });
  const uploaded = page.waitForRequest(
    (r) => r.url().endsWith('/versions/upload') && r.method() === 'POST',
  );
  await page.getByRole('button', { name: '开始分析', exact: true }).click();
  await uploaded;
  await expect(page).toHaveURL(/contracts\/demo$/);
  await expect(page.getByText('单方解约风险')).toBeVisible();
});

test('polls running analysis and displays the completed result', async ({ page }) => {
  let calls = 0;
  await page.route('**/analysis', (route) =>
    route.fulfill({
      json: {
        success: true,
        data: ++calls < 2 ? { status: 'analyzing', document_text: '合同文字' } : completed,
      },
    }),
  );
  await page.goto('/contracts/demo');
  await expect(page.getByRole('status')).toContainText('AI 正在审查');
  await expect(page.getByText('单方解约风险')).toBeVisible({ timeout: 10000 });
});

test('failed analysis can be retried', async ({ page }) => {
  let retried = false;
  await page.route('**/analysis', (route) =>
    route.fulfill({
      json: {
        success: true,
        data: retried ? completed : { status: 'failed', document_text: '', error: '服务超时' },
      },
    }),
  );
  await page.route('**/analyze', (route) => {
    retried = true;
    return route.fulfill({ json: { success: true, data: { run_id: 'r2' } } });
  });
  await page.goto('/contracts/demo');
  await expect(page.getByText('服务超时')).toBeVisible();
  await page.getByRole('button', { name: '重新分析' }).click();
  await expect(page.getByText('单方解约风险')).toBeVisible();
});

test('mobile review has no horizontal overflow', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/contracts/demo');
  await expect(page.getByText('← 合同工作台', { exact: true })).toBeVisible();
  await expect(page.getByText('单方解约风险')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
  await page.screenshot({ path: 'test-results/contract-mobile.png', fullPage: true });
});

test('upload errors are shown and the created contract remains reachable', async ({ page }) => {
  await page.route('**/versions/upload', (route) =>
    route.fulfill({ status: 422, json: { success: false, msg: '请上传有效的 PDF 或 DOCX 文件' } }),
  );
  await page.goto('/contracts/demo');
  await page.locator('input[type=file]').setInputFiles({
    name: 'bad.pdf',
    mimeType: 'application/pdf',
    buffer: Buffer.from('invalid'),
  });
  await expect(page.getByText('请上传有效的 PDF 或 DOCX 文件')).toBeVisible();
  await expect(page.getByRole('heading', { name: '采购合同', exact: true })).toBeVisible();
});
