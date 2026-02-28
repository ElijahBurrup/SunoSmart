// @ts-check
const { test, expect } = require('@playwright/test');

const BASE_URL = 'http://localhost:6000';

test.describe('SunoSmart Homepage', () => {
  test('should load the homepage', async ({ page }) => {
    const response = await page.goto(BASE_URL);
    expect(response.status()).toBe(200);
    await expect(page.locator('h1')).toContainText('SunoSmart');
    await expect(page.locator('#searchInput')).toBeVisible();
    await expect(page.locator('#searchBtn')).toBeVisible();
  });

  test('should load static CSS and JS', async ({ page }) => {
    const failedResources = [];
    page.on('requestfailed', request => {
      failedResources.push({ url: request.url(), error: request.failure().errorText });
    });

    await page.goto(BASE_URL);
    await page.waitForTimeout(2000);

    // Check no resources failed to load
    expect(failedResources).toEqual([]);

    // Verify CSS is loaded (page should have styled elements)
    const bgColor = await page.evaluate(() => {
      return getComputedStyle(document.body).backgroundColor;
    });
    console.log('Body background color:', bgColor);
  });
});

test.describe('Search Feature', () => {
  test('should perform a search and get results', async ({ page }) => {
    // Capture console errors
    const consoleErrors = [];
    page.on('console', msg => {
      if (msg.type() === 'error') consoleErrors.push(msg.text());
    });

    // Capture network requests
    const networkErrors = [];
    page.on('requestfailed', request => {
      networkErrors.push({ url: request.url(), error: request.failure().errorText });
    });

    await page.goto(BASE_URL);

    // Type a search query
    await page.fill('#searchInput', 'pitch down octave');

    // Intercept the search response
    const [searchResponse] = await Promise.all([
      page.waitForResponse(resp => resp.url().includes('/search')),
      page.click('#searchBtn'),
    ]);

    const status = searchResponse.status();
    const body = await searchResponse.json();

    console.log('Search response status:', status);
    console.log('Search response body keys:', Object.keys(body));
    console.log('Has answer:', !!body.answer);
    console.log('Citations count:', body.citations?.length || 0);

    // Should get a 200 response
    expect(status).toBe(200);

    // Should have an answer
    expect(body.answer).toBeTruthy();

    // Check no console errors
    if (consoleErrors.length > 0) {
      console.log('Console errors:', consoleErrors);
    }

    // Wait for results to render
    await page.waitForSelector('.result-answer', { timeout: 30000 });

    // Results should be displayed
    await expect(page.locator('.result-answer')).toBeVisible();

    // Log any network errors
    if (networkErrors.length > 0) {
      console.log('Network errors:', networkErrors);
    }
  });

  test('should reject empty queries', async ({ page }) => {
    await page.goto(BASE_URL);

    // Try submitting empty search
    const searchResponse = page.waitForResponse(resp => resp.url().includes('/search'), { timeout: 3000 }).catch(() => null);
    await page.click('#searchBtn');

    // Should not even make a request (client-side validation)
    const resp = await searchResponse;
    expect(resp).toBeNull();
  });

  test('should show error for short queries', async ({ page }) => {
    await page.goto(BASE_URL);
    await page.fill('#searchInput', 'a');

    // Should not make a request for single char
    const searchResponse = page.waitForResponse(resp => resp.url().includes('/search'), { timeout: 3000 }).catch(() => null);
    await page.click('#searchBtn');
    const resp = await searchResponse;
    expect(resp).toBeNull();
  });
});

test.describe('Suggest Feature', () => {
  test('should submit a YouTube URL suggestion', async ({ page }) => {
    const consoleErrors = [];
    page.on('console', msg => {
      if (msg.type() === 'error') consoleErrors.push(msg.text());
    });

    await page.goto(BASE_URL);

    // Fill in a YouTube URL
    await page.fill('#suggestInput', 'https://www.youtube.com/channel/UCexample123');

    // Submit suggestion
    const [suggestResponse] = await Promise.all([
      page.waitForResponse(resp => resp.url().includes('/suggest')),
      page.click('.suggest-btn'),
    ]);

    const status = suggestResponse.status();
    const body = await suggestResponse.json();

    console.log('Suggest response status:', status);
    console.log('Suggest response body:', body);

    expect(status).toBe(200);
    expect(body.message).toBeTruthy();

    // Check the success message is displayed
    await expect(page.locator('#suggestMsg')).toContainText(/vote|Thanks|already/i);

    if (consoleErrors.length > 0) {
      console.log('Console errors:', consoleErrors);
    }
  });

  test('should reject non-YouTube URLs', async ({ page }) => {
    await page.goto(BASE_URL);

    await page.fill('#suggestInput', 'https://example.com/not-youtube');

    const [suggestResponse] = await Promise.all([
      page.waitForResponse(resp => resp.url().includes('/suggest')),
      page.click('.suggest-btn'),
    ]);

    const status = suggestResponse.status();
    const body = await suggestResponse.json();

    console.log('Non-YouTube suggest status:', status);
    console.log('Non-YouTube suggest body:', body);

    expect(status).toBe(400);
    expect(body.error).toContain('YouTube');
  });
});

test.describe('News Feature', () => {
  test('should load the news archive page', async ({ page }) => {
    const response = await page.goto(`${BASE_URL}/news`);
    expect(response.status()).toBe(200);
  });
});

test.describe('API Health', () => {
  test('health endpoint should return ok', async ({ page }) => {
    const response = await page.goto(`${BASE_URL}/api/health`);
    expect(response.status()).toBe(200);
    const body = await response.json();
    expect(body.status).toBe('ok');
  });
});

test.describe('Debug — Direct API Test', () => {
  test('POST /search directly should work', async ({ request }) => {
    const response = await request.post(`${BASE_URL}/search`, {
      data: { query: 'pitch down octave' },
      headers: { 'Content-Type': 'application/json' },
    });

    const status = response.status();
    const body = await response.json();

    console.log('Direct API search status:', status);
    console.log('Direct API search body keys:', Object.keys(body));
    if (body.error) console.log('Direct API error:', body.error);
    if (body.answer) console.log('Answer preview:', body.answer.substring(0, 200));

    expect(status).toBe(200);
    expect(body.answer).toBeTruthy();
  });

  test('POST /suggest directly should work', async ({ request }) => {
    const response = await request.post(`${BASE_URL}/suggest`, {
      data: { url: 'https://www.youtube.com/channel/UCtest123' },
      headers: { 'Content-Type': 'application/json' },
    });

    const status = response.status();
    const body = await response.json();

    console.log('Direct API suggest status:', status);
    console.log('Direct API suggest body:', body);

    expect(status).toBe(200);
  });
});
