const { chromium } = require('playwright');

const BASE = 'http://localhost:6000';

async function run() {
  const browser = await chromium.launch();
  const context = await browser.newContext();
  let passed = 0;
  let failed = 0;

  async function test(name, fn) {
    try {
      await fn();
      console.log(`  PASS: ${name}`);
      passed++;
    } catch (err) {
      console.log(`  FAIL: ${name}`);
      console.log(`    Error: ${err.message}`);
      failed++;
    }
  }

  // === Test 1: Homepage loads ===
  await test('Homepage loads', async () => {
    const page = await context.newPage();
    const resp = await page.goto(BASE);
    if (resp.status() !== 200) throw new Error(`Status ${resp.status()}`);
    const h1 = await page.textContent('h1');
    if (!h1.includes('SunoSmart')) throw new Error(`H1 is "${h1}"`);
    console.log(`    H1: "${h1}"`);
    await page.close();
  });

  // === Test 2: Health endpoint ===
  await test('Health endpoint', async () => {
    const page = await context.newPage();
    const resp = await page.goto(`${BASE}/api/health`);
    const body = JSON.parse(await resp.text());
    if (body.status !== 'ok') throw new Error(`Health: ${JSON.stringify(body)}`);
    console.log(`    Health: ${JSON.stringify(body)}`);
    await page.close();
  });

  // === Test 3: Static assets load ===
  await test('CSS and JS load', async () => {
    const page = await context.newPage();
    const failedResources = [];
    page.on('requestfailed', req => failedResources.push(req.url()));
    await page.goto(BASE);
    await page.waitForTimeout(2000);
    if (failedResources.length > 0) throw new Error(`Failed: ${failedResources.join(', ')}`);
    // Verify search.js is loaded by checking if searchForm listener works
    const hasSearchForm = await page.evaluate(() => !!document.getElementById('searchForm'));
    if (!hasSearchForm) throw new Error('searchForm not found');
    console.log('    All static assets loaded, searchForm exists');
    await page.close();
  });

  // === Test 4: Suggest API (non-YouTube rejection) ===
  await test('Suggest rejects non-YouTube URLs', async () => {
    const page = await context.newPage();
    await page.goto(BASE);
    const resp = await page.evaluate(async () => {
      const r = await fetch('/suggest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: 'https://example.com/nope' }),
      });
      return { status: r.status, body: await r.json() };
    });
    console.log(`    Status: ${resp.status}, Body: ${JSON.stringify(resp.body)}`);
    if (resp.status !== 400) throw new Error(`Expected 400, got ${resp.status}`);
    if (!resp.body.error.includes('YouTube')) throw new Error(`Wrong error: ${resp.body.error}`);
    await page.close();
  });

  // === Test 5: Suggest API (YouTube URL accepted) ===
  await test('Suggest accepts YouTube URLs', async () => {
    const page = await context.newPage();
    await page.goto(BASE);
    const resp = await page.evaluate(async () => {
      const r = await fetch('/suggest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: 'https://www.youtube.com/channel/UCplaywright123' }),
      });
      return { status: r.status, body: await r.json() };
    });
    console.log(`    Status: ${resp.status}, Body: ${JSON.stringify(resp.body)}`);
    if (resp.status !== 200) throw new Error(`Expected 200, got ${resp.status}`);
    if (!resp.body.message) throw new Error('No message in response');
    await page.close();
  });

  // === Test 6: Search form in browser ===
  await test('Search form submits and renders results', async () => {
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', err => errors.push(err.message));
    page.on('console', msg => { if (msg.type() === 'error') errors.push(msg.text()); });

    await page.goto(BASE);
    await page.waitForTimeout(500);

    if (errors.length > 0) {
      console.log(`    Page errors on load: ${errors.join('; ')}`);
    }

    await page.fill('#searchInput', 'pitch down octave');

    // Click and wait for response
    const [resp] = await Promise.all([
      page.waitForResponse(r => r.url().includes('/search'), { timeout: 90000 }),
      page.click('#searchBtn'),
    ]);

    console.log(`    Search response status: ${resp.status()}`);
    const body = await resp.json();
    console.log(`    Has answer: ${!!body.answer}`);
    console.log(`    Citations: ${body.citations?.length || 0}`);
    if (body.answer) console.log(`    Answer preview: ${body.answer.substring(0, 150)}...`);

    if (resp.status() !== 200) throw new Error(`Search returned ${resp.status()}`);
    if (!body.answer) throw new Error('No answer in response');

    // Wait for results to render in DOM
    await page.waitForSelector('.result-answer', { timeout: 10000 });
    const rendered = await page.textContent('.result-answer');
    console.log(`    Rendered in DOM: ${!!rendered}`);
    if (!rendered) throw new Error('Results not rendered in DOM');

    if (errors.length > 0) {
      console.log(`    JS errors: ${errors.join('; ')}`);
      throw new Error(`JS errors: ${errors.join('; ')}`);
    }
    await page.close();
  });

  // === Test 7: Suggest form in browser ===
  await test('Suggest form UI works', async () => {
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', err => errors.push(err.message));

    await page.goto(BASE);
    await page.fill('#suggestInput', 'https://www.youtube.com/channel/UCuiTest789');

    const [resp] = await Promise.all([
      page.waitForResponse(r => r.url().includes('/suggest'), { timeout: 10000 }),
      page.click('.suggest-btn'),
    ]);

    console.log(`    Suggest UI status: ${resp.status()}`);
    const msg = await page.textContent('#suggestMsg');
    console.log(`    Message shown: "${msg}"`);
    if (!msg) throw new Error('No message displayed');

    if (errors.length > 0) throw new Error(`JS errors: ${errors.join('; ')}`);
    await page.close();
  });

  // === Test 8: News page ===
  await test('News archive loads', async () => {
    const page = await context.newPage();
    const resp = await page.goto(`${BASE}/news`);
    if (resp.status() !== 200) throw new Error(`Status ${resp.status()}`);
    await page.close();
  });

  await browser.close();

  console.log(`\n  Results: ${passed} passed, ${failed} failed out of ${passed + failed} tests`);
  process.exit(failed > 0 ? 1 : 0);
}

run().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
