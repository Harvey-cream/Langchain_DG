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
  let selectedRun = 'r2';
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
    else if (path.endsWith('/analysis'))
      data = {
        ...completed,
        id: 'r2',
        latest_run_id: 'r2',
        selected_run_id: selectedRun,
        is_showing_previous: selectedRun !== 'r2',
      };
    else if (path.endsWith('/analysis-runs'))
      data = {
        selected_run_id: selectedRun,
        runs: [
          {
            id: 'r2',
            status: 'completed',
            current_step: 'review_required',
            attempt: 2,
            prompt_version: 'v1',
            selected: selectedRun === 'r2',
          },
          {
            id: 'r1',
            status: 'completed',
            current_step: 'review_required',
            attempt: 1,
            prompt_version: 'v1',
            selected: selectedRun === 'r1',
          },
        ],
      };
    else if (path.includes('/analysis-runs/') && path.endsWith('/select')) {
      const segments = path.split('/');
      selectedRun = segments[segments.length - 2] || selectedRun;
      data = { ...completed, latest_run_id: 'r2', selected_run_id: selectedRun };
    } else if (path.endsWith('/versions/upload')) data = { version_id: 'v1', run_id: 'r1' };
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

test('expired token clears the session and redirects to login', async ({ page }) => {
  await page.unrouteAll({ behavior: 'wait' });
  await page.goto('/login');
  await page.evaluate(() => localStorage.setItem('token', 'expired-token'));
  await page.route('http://127.0.0.1:5180/api/**', (route) =>
    route.fulfill({ status: 401, json: { success: false, msg: '认证失败，请重新登录' } }),
  );

  const unauthorized = page.waitForResponse((response) => response.status() === 401);
  await page.goto('/contracts');
  await unauthorized;

  await expect(page).toHaveURL(/\/login$/);
  expect(await page.evaluate(() => localStorage.getItem('token'))).toBeNull();
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

test('a previous successful analysis can be selected without deleting history', async ({
  page,
}) => {
  await page.goto('/contracts/demo');
  await page.getByLabel('分析历史').first().click();
  await page.getByText('第 1 次 · 分析成功', { exact: true }).click();
  await expect(page.getByText('当前展示的是历史成功结果')).toBeVisible();
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

const canonicalClauses = [
  {
    id: 'c1',
    sequence: 1,
    title: '付款方式',
    clause_type: 'payment',
    original_text: '甲方在签署当日支付全部价款。',
    source_block_ids: ['b1'],
    pages: [1],
  },
  {
    id: 'c2',
    sequence: 2,
    title: '交付期限',
    clause_type: 'delivery',
    original_text: '乙方可以无限延期交付。',
    source_block_ids: ['b2'],
    pages: [2],
  },
];
const v2Risks = ['预付款风险', '退款条件缺失'].map((riskType, index) => ({
  id: `risk-${index}`,
  clause_id: 'c1',
  risk_type: riskType,
  title: riskType,
  risk_level: 'high',
  evidence: canonicalClauses[0].original_text,
  evidence_text: canonicalClauses[0].original_text,
  reason: '全额付款发生在交付前。',
  recommendation: '增加验收后付款与退款条款。',
  suggestion: '增加验收后付款与退款条款。',
  related_clause_ids: ['c2'],
  review_status: 'pending',
}));
const v2Report = {
  ...completed,
  review_version: 'v2',
  our_party: '甲方',
  result: { risks: v2Risks },
  risks: v2Risks,
  clauses: [],
  canonical_clauses: canonicalClauses,
  facts: {
    metadata: {
      summary: 'P3 版本事实摘要',
      parties: ['采购方', '供应商'],
      amount: '100000元',
      duration: '一年',
      payment_terms: '签署当日全额付款',
    },
    parser_version: 'v2',
    intelligence_version: 'v1',
    coverage: { ratio: 1, warnings: [] },
  },
};

test('quality gate explains source verification and unresolved legal basis on mobile', async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const risk = { ...v2Risks[0], reason: '该合同违法。' };
  await page.route('**/analysis', (route) =>
    route.fulfill({
      json: {
        success: true,
        data: {
          ...v2Report,
          risks: [risk],
          result: { risks: [risk] },
          context_snapshot: {
            quality_gate: {
              version: 'review-quality-v1',
              status: 'passed',
              duplicate_count: 1,
              finding_checks: [
                {
                  ...risk,
                  assessment: 'insufficient_legal_basis',
                  notes: ['法律判断未经核实，仅供法务复核'],
                },
              ],
            },
          },
        },
      },
    }),
  );
  await page.goto('/contracts/demo');
  await expect(page.getByText('当前展示结果已通过来源校验，不代表法律结论正确')).toBeVisible();
  await expect(page.getByText('法律依据未核实 · 仅供复核提示')).toBeVisible();
  await expect(page.getByText(/已移除 1 条确定重复风险/)).toBeVisible();
  await page.getByRole('button', { name: '相关条款：交付期限' }).click();
  await expect(
    page.locator('.ant-drawer').getByText(canonicalClauses[1].original_text),
  ).toBeVisible();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1),
  ).toBeTruthy();
});

test('failed quality gate keeps a previous report without certifying legacy results', async ({
  page,
}) => {
  await page.route('**/analysis', (route) =>
    route.fulfill({
      json: {
        success: true,
        data: {
          ...v2Report,
          status: 'failed',
          error: '证据无法定位到真实原文',
          is_showing_previous: true,
          latest_quality_gate: { status: 'failed', version: 'review-quality-v1' },
        },
      },
    }),
  );
  await page.goto('/contracts/demo');
  await expect(page.getByText('最新审查未通过质量校验，未保存为成功结果')).toBeVisible();
  await expect(page.getByText('历史结果未记录本版质量校验，不能追认为已通过。')).toBeVisible();
  await expect(page.getByText('当前展示结果已通过来源校验，不代表法律结论正确')).toHaveCount(0);
  await expect(page.getByText('预付款风险', { exact: true })).toBeVisible();
});

test('partial retrieval degradation is disclosed without invented references', async ({ page }) => {
  await page.route('**/analysis', (route) =>
    route.fulfill({
      json: {
        success: true,
        data: {
          ...v2Report,
          context_snapshot: {
            retrieval: { enabled: true },
            retrieval_events: [{ reference_count: 0, unavailable_count: 1 }],
            references: [],
          },
        },
      },
    }),
  );
  await page.goto('/contracts/demo');
  await expect(
    page.getByText('部分参考资料在检索期间撤下，已排除；未补写缺失引用。'),
  ).toBeVisible();
  await expect(page.getByRole('button', { name: '查看参考快照' })).toHaveCount(0);
});

test('V2 groups multiple risks under a canonical clause and opens true source text', async ({
  page,
}) => {
  await page.route('**/analysis', (route) =>
    route.fulfill({ json: { success: true, data: v2Report } }),
  );
  await page.goto('/contracts/demo');
  await expect(page.getByText('P3 版本事实摘要')).toBeVisible();
  const clause = page.locator('[data-clause-id="c1"]');
  await expect(clause.getByText('预付款风险')).toBeVisible();
  await expect(clause.getByText('退款条件缺失')).toBeVisible();
  await expect(page.locator('[data-clause-id="c2"] .risk-card')).toHaveCount(0);
  await clause.getByRole('button', { name: '查看关联条款' }).first().click();
  await expect(
    page.locator('.ant-drawer').getByText(canonicalClauses[0].original_text, { exact: true }),
  ).toBeVisible();
});

test('V2 has an empty-risk state and preserves facts after review failure', async ({ page }) => {
  await page.route('**/analysis', (route) =>
    route.fulfill({
      json: { success: true, data: { ...v2Report, risks: [], result: { risks: [] } } },
    }),
  );
  await page.goto('/contracts/demo');
  await expect(page.getByText('本次分析未识别到风险项')).toBeVisible();
  await expect(page.getByText('付款方式', { exact: true })).toBeVisible();
  await page.route('**/analysis', (route) =>
    route.fulfill({
      json: {
        success: true,
        data: { ...v2Report, status: 'failed', result: null, risks: [], error: '风险审查超时' },
      },
    }),
  );
  await page.reload();
  await expect(page.getByText('风险审查超时')).toBeVisible();
  await expect(page.getByText('P3 版本事实摘要')).toBeVisible();
  await expect(page.getByText('付款方式', { exact: true })).toBeVisible();
});

test('switching V1 and V2 history preserves Version clauses and changes risks', async ({
  page,
}) => {
  let old = false;
  const report = () =>
    old
      ? {
          ...v2Report,
          review_version: 'v1',
          our_party: '',
          result,
          risks: [],
          selected_run_id: 'r1',
          is_showing_previous: true,
        }
      : { ...v2Report, selected_run_id: 'r2' };
  await page.route('**/analysis', (route) =>
    route.fulfill({ json: { success: true, data: report() } }),
  );
  await page.route('**/analysis-runs/*/select', (route) => {
    old = route.request().url().includes('/r1/');
    return route.fulfill({ json: { success: true, data: report() } });
  });
  await page.goto('/contracts/demo');
  await expect(page.getByText('预付款风险')).toBeVisible();
  await page.getByLabel('分析历史').first().click();
  await page.getByText('第 1 次 · 分析成功', { exact: true }).click();
  await expect(page.getByText('历史 Review V1')).toBeVisible();
  await expect(page.getByText('单方解约风险')).toBeVisible();
  await expect(page.getByText('预付款风险')).toHaveCount(0);
  await expect(page.locator('[data-clause-id]')).toHaveCount(2);
  await expect(page.getByText('P3 版本事实摘要')).toBeVisible();
});

test('V2 retry sends the explicit reviewing party', async ({ page }) => {
  await page.route('**/analysis', (route) =>
    route.fulfill({ json: { success: true, data: v2Report } }),
  );
  await page.route('**/analyze', (route) =>
    route.fulfill({ json: { success: true, data: { run_id: 'r3' } } }),
  );
  await page.goto('/contracts/demo');
  await expect(page.getByLabel('我方签约方')).toHaveValue('甲方');
  await page.getByLabel('我方签约方').fill('乙方');
  const requested = page.waitForRequest((request) => request.url().endsWith('/analyze'));
  await page.getByRole('button', { name: '重新分析' }).click();
  expect((await requested).postDataJSON()).toEqual({ our_party: '乙方' });
});

test('V2 mobile risk groups have no horizontal overflow', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.route('**/analysis', (route) =>
    route.fulfill({ json: { success: true, data: v2Report } }),
  );
  await page.goto('/contracts/demo');
  await expect(page.getByText('预付款风险')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
});

test('enterprise policies can be created edited disabled and archived', async ({ page }) => {
  let policies: Array<Record<string, unknown>> = [];
  await page.route('**/api/contract-policies**', async (route) => {
    const request = route.request();
    let data: unknown;
    if (request.method() === 'POST') {
      const policy = { ...request.postDataJSON(), id: 'p1', version: 1, archived: false };
      policies.push(policy);
      data = policy;
    } else if (request.method() === 'PATCH') {
      policies[0] = {
        ...policies[0],
        ...request.postDataJSON(),
        version: Number(policies[0].version) + 1,
      };
      data = policies[0];
    } else if (request.method() === 'DELETE') {
      data = { ...policies[0], archived: true };
      policies = [];
    } else data = { policies };
    await route.fulfill({ json: { success: true, data } });
  });
  await page.goto('/contracts/policies');
  await page.getByRole('button', { name: '创建规则' }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByLabel('规则名称').fill('禁止无限赔偿');
  await dialog.getByLabel('审查要求').fill('企业原则上不接受无上限赔偿责任。');
  await dialog.getByLabel('适用我方角色（留空不限）').fill('supplier');
  await dialog.getByRole('button', { name: /确定|OK/ }).click();
  await expect(page.getByRole('heading', { name: '禁止无限赔偿' })).toBeVisible();
  await page.getByRole('switch', { name: '启用 禁止无限赔偿' }).click();
  await expect(page.getByText('v2', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: /^修\s*改$/ }).click();
  await dialog.getByLabel('审查要求').fill('供应商赔偿应约定合理上限。');
  await dialog.getByRole('button', { name: /确定|OK/ }).click();
  await expect(page.getByText('v3', { exact: true })).toBeVisible();
  await expect(
    page.locator('.policy-panel').getByText('供应商赔偿应约定合理上限。', { exact: true }),
  ).toBeVisible();
  await page.getByRole('button', { name: /^归\s*档$/ }).click();
  await page
    .locator('.ant-popconfirm')
    .getByRole('button', { name: /确定|OK/ })
    .click();
  await expect(page.getByText('尚未创建企业规则')).toBeVisible();
});

test('private knowledge upload deduplicates and supports reindex classify and delete recovery', async ({
  page,
}) => {
  let documents = [
    {
      id: 'd1',
      filename: '企业规范.docx',
      document_version: 1,
      category: 'legal_policy',
      status: 'ready',
      generation: 1,
      chunk_count: 2,
      byte_count: 1024,
      embedding_model: 'text-embedding-v3',
      error: '',
    },
  ];
  let indexCalls = 0,
    deleteCalls = 0;
  await page.route('**/api/contract-knowledge/documents**', async (route) => {
    const request = route.request(),
      path = new URL(request.url()).pathname;
    let data: unknown;
    if (path.endsWith('/upload')) {
      const duplicate = documents.some((d) => d.id === 'd2');
      if (!duplicate)
        documents.push({
          ...documents[0],
          id: 'd2',
          filename: '新增模板.docx',
          category: 'template',
        });
      data = { document: documents.find((d) => d.id === 'd2'), duplicate };
    } else if (path.endsWith('/reindex')) {
      indexCalls++;
      documents[0] = {
        ...documents[0],
        generation: documents[0].generation + 1,
        status: indexCalls === 1 ? 'failed' : 'ready',
        error: indexCalls === 1 ? 'Embedding 服务不可用' : '',
      };
      data = documents[0];
    } else if (request.method() === 'PATCH') {
      documents[0] = { ...documents[0], category: request.postDataJSON().category };
      data = documents[0];
    } else if (request.method() === 'DELETE') {
      deleteCalls++;
      if (deleteCalls === 1)
        documents[0] = {
          ...documents[0],
          status: 'deleting',
          error: 'OSS 原件清理失败，请重试删除',
        };
      else documents = documents.filter((d) => d.id !== 'd1');
      data = { status: 'deleting' };
    } else data = { documents };
    await route.fulfill({ json: { success: true, data } });
  });
  await page.goto('/contracts/knowledge');
  await expect(page.getByRole('heading', { name: '企业规范.docx' })).toBeVisible();
  const file = {
    name: '新增模板.docx',
    mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    buffer: Buffer.from('mock browser upload'),
  };
  await page.locator('input[type=file]').setInputFiles(file);
  await expect(page.getByRole('heading', { name: '新增模板.docx' })).toBeVisible();
  await page.locator('input[type=file]').setInputFiles(file);
  await expect(page.getByRole('heading', { name: '新增模板.docx' })).toHaveCount(1);
  const first = page
    .locator('.policy-panel')
    .filter({ has: page.getByRole('heading', { name: '企业规范.docx' }) });
  await first.getByRole('button', { name: '修改分类' }).click();
  await page.getByRole('dialog').getByLabel('文档分类').fill('historical_case');
  await page
    .getByRole('dialog')
    .getByRole('button', { name: /确定|OK/ })
    .click();
  await expect(first.getByText('historical_case')).toBeVisible();
  await first.getByRole('button', { name: '重新索引' }).click();
  await expect(page.getByText('Embedding 服务不可用')).toBeVisible();
  await first.getByRole('button', { name: '重试索引' }).click();
  await expect(first.getByText('可检索')).toBeVisible();
  await first.getByRole('button', { name: /^删\s*除$/ }).click();
  await page
    .locator('.ant-popconfirm')
    .getByRole('button', { name: /确定|OK/ })
    .click();
  await expect(first.getByRole('button', { name: '重试删除' })).toBeVisible();
  await first.getByRole('button', { name: '重试删除' }).click();
  await page
    .locator('.ant-popconfirm')
    .getByRole('button', { name: /确定|OK/ })
    .click();
  await expect(page.getByRole('heading', { name: '企业规范.docx' })).toHaveCount(0);
});

test('risk report distinguishes policy and RAG reference and opens historical source snapshot', async ({
  page,
}) => {
  const reference = {
    chunk_id: 'k1',
    document_id: 'd1',
    document_version: 1,
    index_generation: 2,
    filename: '历史谈判案例.docx',
    document_type: 'historical_case',
    chunk_text: '历史案例完整片段：交付验收后再支付尾款。',
    locator: { block_sequences: [2] },
  };
  await page.route('**/analysis', (route) =>
    route.fulfill({
      json: {
        success: true,
        data: {
          ...v2Report,
          context_snapshot: {
            policies: [{ id: 'p1', version: 1, name: '付款规则', requirement: '尾款须与验收挂钩' }],
            references: [reference],
          },
          risks: [
            {
              ...v2Risks[0],
              policy_ids: ['p1'],
              reference_citations: [{ chunk_id: 'k1', source_excerpt: '交付验收后再支付尾款。' }],
            },
          ],
        },
      },
    }),
  );
  await page.goto('/contracts/demo');
  await expect(page.getByText('企业规则：付款规则 · v1')).toBeVisible();
  await expect(page.getByText('RAG 参考资料（非强制政策）')).toBeVisible();
  await page.getByRole('button', { name: '查看参考快照' }).click();
  await expect(page.locator('.ant-drawer').getByText(reference.chunk_text)).toBeVisible();
  await expect(
    page
      .locator('.ant-drawer')
      .getByText('审查时保存的引用快照；原件删除或重建索引不会覆盖此依据。'),
  ).toBeVisible();
});

test('review retry includes explicit party role and contract type', async ({ page }) => {
  await page.route('**/analysis', (route) =>
    route.fulfill({ json: { success: true, data: v2Report } }),
  );
  await page.route('**/analyze', (route) =>
    route.fulfill({ json: { success: true, data: { run_id: 'r3' } } }),
  );
  await page.goto('/contracts/demo');
  await page.getByLabel('我方业务角色').fill('supplier');
  await page.getByLabel('合同类型', { exact: true }).fill('sales');
  const requested = page.waitForRequest((request) => request.url().endsWith('/analyze'));
  await page.getByRole('button', { name: '重新分析' }).click();
  expect((await requested).postDataJSON()).toEqual({
    our_party: '甲方',
    party_role: 'supplier',
    contract_type: 'sales',
  });
});

test('knowledge mobile layout and authenticated download token expiry', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.route('**/api/contract-knowledge/documents', (route) =>
    route.fulfill({
      json: {
        success: true,
        data: {
          documents: [
            {
              id: 'd1',
              filename: '很长的企业合同参考规范文件名称用于验证移动端自动换行.docx',
              status: 'ready',
              category: 'legal_policy',
              document_version: 1,
              generation: 1,
              chunk_count: 1,
              byte_count: 1000,
            },
          ],
        },
      },
    }),
  );
  await page.route('**/download', (route) =>
    route.fulfill({ status: 401, json: { detail: 'expired' } }),
  );
  await page.goto('/contracts/knowledge');
  await expect(page.getByText('可检索')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
  await page.evaluate(() => localStorage.setItem('token', 'expired-test-token'));
  await page.getByRole('button', { name: '下载原件' }).click();
  await expect(page).toHaveURL(/\/login$/);
  expect(await page.evaluate(() => localStorage.getItem('token'))).toBeNull();
});
