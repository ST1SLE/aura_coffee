import { createRequire } from 'node:module';
const require = createRequire(new URL('../../tests/e2e/package.json', import.meta.url));
const { defineConfig, devices } = require('@playwright/test');
import path from 'node:path';
import { fileURLToPath } from 'node:url';

// START_MODULE_CONTRACT
// PURPOSE: Headless customer UI verification against mocked API boundaries.
// SCOPE: Isolated-copy config, separate from the destructive QA reset suite.
// DEPENDS: Playwright, built customer SPA, loopback Vite preview.
// LINKS: docs/ux-metrics-maximization/headless-frontend.md
// ROLE: CONFIG
// MAP_MODE: NONE
// END_MODULE_CONTRACT

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const port = Number(process.env.AURA_FRONTEND_PORT);
if (!root.startsWith('/tmp/aura-coffee-audit-') || !Number.isInteger(port) || port < 1024 || port > 65535) {
  throw new Error('Use bash scripts/verify-frontend-isolated.sh; isolated root and port required');
}
const baseURL = `http://127.0.0.1:${port}`;

export default defineConfig({
  testDir: '../../tests/verification/browser',
  timeout: 30_000,
  expect: { timeout: 8_000 },
  workers: 1,
  retries: 0,
  outputDir: path.join(root, '.verification-results/browser-artifacts'),
  reporter: [
    ['list'],
    ['html', { outputFolder: path.join(root, '.verification-results/browser-html'), open: 'never' }],
    ['json', { outputFile: path.join(root, '.verification-results/browser-results.json') }],
  ],
  use: { baseURL, headless: true, serviceWorkers: 'block', trace: 'retain-on-failure', screenshot: 'only-on-failure' },
  webServer: {
    command: `npm exec -- vite preview --host 127.0.0.1 --port ${port} --strictPort`,
    cwd: path.join(root, 'web/admin'),
    url: baseURL + "/admin/",
    reuseExistingServer: false,
  },
  projects: [
    { name: 'desktop-ru', use: { ...devices['Desktop Chrome'], locale: 'ru-RU' } },
    { name: 'desktop-en', use: { ...devices['Desktop Chrome'], locale: 'en-US' } },
    { name: 'mobile-ru', use: { ...devices['Pixel 7'], locale: 'ru-RU' } },
    { name: 'mobile-en', use: { ...devices['Pixel 7'], locale: 'en-US' } },
  ],
});
