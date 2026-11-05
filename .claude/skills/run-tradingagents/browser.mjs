// JSON-lines REPL over the real desk UI. No test runner or mocked responses.
import { chromium } from 'playwright';
import { mkdir } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { homedir } from 'node:os';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import readline from 'node:readline';

const root = fileURLToPath(new URL('../../../', import.meta.url));
const output = path.join(root, '.local-workspace/run-skill-generator/screenshots');
const origin = 'http://127.0.0.1:8099';
const developmentIdentity = createHash('sha256').update(
  path.join(homedir(), '.cache/trader/development/application').toLowerCase(),
).digest('hex');
const browser = await chromium.launch({ channel: 'msedge', headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const errors = [], blocked = [];
let failed = false;
try {
  // Fail closed on external BROWSER traffic and sensitive/active APIs. Aborts are not
  // fake successes: no service responses, quotes or account facts are supplied.
  await context.route('**/*', async route => {
    const request = route.request(), url = new URL(request.url());
    const safeRead = request.method() === 'GET' && (
      ['/', '/index.html', '/api/state', '/api/health', '/api/workspace', '/api/workflows',
        '/api/market-history', '/api/discovery', '/api/stock-evidence', '/api/evaluations',
        '/api/investor', '/api/attention', '/api/reporting', '/api/portfolio-model', '/api/commands'].includes(url.pathname)
      || url.pathname.startsWith('/static/')
      || /^\/api\/(runs|instruments)\//.test(url.pathname) && !url.searchParams.has('refresh'));
    const viewSave = request.method() === 'POST' && url.pathname === '/api/workspace';
    if (url.origin === origin && (safeRead || viewSave)) return route.continue();
    blocked.push(`${request.method()} ${url.origin === origin ? url.pathname : '[external]'}`);
    return route.abort('blockedbyclient');
  });
  const page = await context.newPage();
  page.on('pageerror', error => errors.push(error.name));
  page.on('console', message => { if (message.type() === 'error') errors.push('console error'); });
  page.on('response', response => {
    if (response.status() >= 400) errors.push(`HTTP ${response.status()} ${new URL(response.url()).pathname}`);
  });
  const input = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
  console.log(JSON.stringify({ ready: true, origin }));
  for await (const line of input) {
    if (!line.trim()) continue;
    try {
      const command = JSON.parse(line);
      switch (command.action) {
        case 'open': {
          // Attach only to the approved existing development instance. This
          // driver never starts or stops application/native processes.
          // Establish the app's ordinary cookie session before reading identity.
          const landing = await context.request.get(`${origin}/`, { maxRedirects: 0 });
          if (!landing.ok()) throw new Error('The development desk is not ready.');
          const response = await context.request.get(`${origin}/api/health`, { maxRedirects: 0 });
          if (!response.ok()) throw new Error('The development desk health read failed.');
          const health = await response.json();
          if (health.product !== 'TradingAgents' || health.application_identity !== developmentIdentity) {
            throw new Error('The listener does not match the approved development profile.');
          }
          await page.goto(origin, { waitUntil: 'domcontentloaded' });
          await page.locator('#main h1').waitFor();
          console.log(JSON.stringify({ identityVerified: true, engine: health.engine }));
          break;
        }
        case 'click':
          await page.locator(command.selector).click();
          break;
        case 'fill':
          await page.locator(command.selector).fill(command.value);
          break;
        case 'wait':
          await page.locator(command.selector).waitFor({ state: 'visible' });
          break;
        case 'text':
          console.log(JSON.stringify({ text: await page.locator(command.selector).innerText() }));
          break;
        case 'screenshot': {
          if (!/^[a-zA-Z0-9_-]+$/.test(command.name)) throw new Error('Use a simple screenshot name without a path.');
          await mkdir(output, { recursive: true });
          const target = path.join(output, `${command.name}.png`);
          await page.screenshot({ path: target, fullPage: true });
          console.log(JSON.stringify({ screenshot: target }));
          break;
        }
        case 'status':
          console.log(JSON.stringify({ errors, blocked }));
          break;
        case 'quit':
          input.close();
          break;
        default:
          throw new Error('Unknown action. Use open, click, fill, wait, text, screenshot, status or quit.');
      }
      console.log(JSON.stringify({ ok: true, action: command.action }));
      if (command.action === 'quit') break;
    } catch (error) {
      // Do not emit browser headers, session tokens or arbitrary response bodies.
      console.error(JSON.stringify({ ok: false, error: error.name }));
      failed = true;
      break;
    }
  }
} finally {
  await context.close();
  await browser.close();
}
process.exitCode = failed || errors.length || blocked.length ? 1 : 0;
