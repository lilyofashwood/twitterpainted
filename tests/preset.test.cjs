const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
let chromium;
try { ({ chromium } = require('playwright')); } catch {}

test('launcher presets change declared UI controls only; URL secrets and invalid options are ignored',
  { skip: !chromium && 'Install Playwright to run browser preset checks' }, async () => {
    const browser = await chromium.launch({ headless: true,
      ...(process.env.GARDEN_CHROME_BIN ? { executablePath: process.env.GARDEN_CHROME_BIN } : {}) });
    try {
      const page = await browser.newPage();
      const root = path.resolve(__dirname, "../docs");
      const allowed = new Set(["twitterpainted.js","twitterpainted.css","steg-core.js","index.html"]);
      const posts = [], errors = [];
      page.on('request', request => { if (request.method() !== 'GET') posts.push(request.method()); });
      page.on('pageerror', error => errors.push(error.message));
      await page.route('**/*', async route => {
        const url = new URL(route.request().url());
        const file = url.pathname === '/' ? 'index.html' : url.pathname.slice(1);
        if (url.origin !== 'http://garden.test' || !allowed.has(file)) return route.abort();
        const mime = file.endsWith('.js') ? 'text/javascript' : file.endsWith('.css') ? 'text/css' : file.endsWith('.png') ? 'image/png' : 'text/html';
        await route.fulfill({ body: await fs.readFile(path.join(root, file)), contentType: mime });
      });
      for (const [query, panel, selected] of [["?mode=decode&paint=individual","decode-panel","individual"],["?mode=encode&paint=combined","encode-panel","combined"],["?mode=encode&paint=individual","encode-panel","individual"],["?mode=decode&paint=combined","decode-panel","combined"],["?mode=unknown&paint=unknown","encode-panel","combined"],["?mode=__proto__&paint=%F0%9D%93%B5","encode-panel","combined"]]) {
        await page.goto('http://garden.test/' + query + '&key=SECRET&payload=DO_NOT_LOAD&carrier=DO_NOT_FETCH');
        await page.waitForFunction(() => document.querySelector('.mode-btn.active'));
        assert.equal(await page.locator('.panel.active').getAttribute('id'), panel);
        assert.equal(await page.evaluate(() => document.querySelector('input[name="paint-style"]:checked').value), selected);
        assert.deepEqual(await page.locator('textarea').evaluateAll(fields => fields.map(field => field.value)), await page.locator('textarea').evaluateAll(fields => fields.map(() => '')));
        assert.equal(await page.locator('a[download]').count(), 0);
        assert.equal(await page.locator('input[type=file]').evaluateAll(fields => fields.reduce((n, field) => n + field.files.length, 0)), 0);
      }
      assert.deepEqual(posts, []);
      assert.deepEqual(errors, []);
    } finally { await browser.close(); }
  });
