// @ts-check
const { test, expect } = require('@playwright/test');

const BASE_URL = 'http://localhost:6000';

test('homepage loads', async ({ page }) => {
  const response = await page.goto(BASE_URL);
  expect(response.status()).toBe(200);
  const title = await page.textContent('h1');
  console.log('H1:', title);
  expect(title).toContain('SunoSmart');
});

test('health endpoint', async ({ request }) => {
  const resp = await request.get(`${BASE_URL}/api/health`);
  expect(resp.status()).toBe(200);
  const body = await resp.json();
  console.log('Health:', body);
  expect(body.status).toBe('ok');
});

test('search API works', async ({ request }) => {
  const resp = await request.post(`${BASE_URL}/search`, {
    data: { query: 'pitch down octave' },
    headers: { 'Content-Type': 'application/json' },
  });
  expect(resp.status()).toBe(200);
  const body = await resp.json();
  console.log('Search answer (first 200 chars):', body.answer?.substring(0, 200));
  console.log('Citations:', body.citations?.length);
  expect(body.answer).toBeTruthy();
});

test('suggest API works', async ({ request }) => {
  const resp = await request.post(`${BASE_URL}/suggest`, {
    data: { url: 'https://www.youtube.com/channel/UCtest456' },
    headers: { 'Content-Type': 'application/json' },
  });
  expect(resp.status()).toBe(200);
  const body = await resp.json();
  console.log('Suggest:', body);
  expect(body.message).toBeTruthy();
});

test('suggest rejects non-YouTube URLs', async ({ request }) => {
  const resp = await request.post(`${BASE_URL}/suggest`, {
    data: { url: 'https://example.com' },
    headers: { 'Content-Type': 'application/json' },
  });
  expect(resp.status()).toBe(400);
  const body = await resp.json();
  console.log('Reject non-YouTube:', body);
  expect(body.error).toContain('YouTube');
});

test('search form submits in browser', async ({ page }) => {
  const errors = [];
  page.on('console', msg => { if (msg.type() === 'error') errors.push(msg.text()); });
  page.on('pageerror', err => errors.push(err.message));

  await page.goto(BASE_URL);

  // Check JS loaded without errors
  await page.waitForTimeout(1000);
  console.log('Page errors after load:', errors);

  // Fill and submit search
  await page.fill('#searchInput', 'how to use suno');

  const responsePromise = page.waitForResponse(resp => resp.url().includes('/search'), { timeout: 60000 });
  await page.click('#searchBtn');
  const resp = await responsePromise;

  console.log('Browser search response status:', resp.status());
  expect(resp.status()).toBe(200);

  // Wait for results to render
  await page.waitForSelector('.result-answer', { timeout: 60000 });
  const answerText = await page.textContent('.result-answer');
  console.log('Rendered answer (first 150 chars):', answerText?.substring(0, 150));
  expect(answerText).toBeTruthy();

  console.log('All page errors:', errors);
});

test('news archive loads', async ({ page }) => {
  const resp = await page.goto(`${BASE_URL}/news`);
  expect(resp.status()).toBe(200);
});
