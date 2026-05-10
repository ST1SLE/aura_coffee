#!/usr/bin/env node
/*
 * Closed-staging customer video smoke.
 *
 * This intentionally runs from an operator machine, not inside Docker:
 * it drives a fresh local Chromium profile through the real closed-staging
 * login flow, obtains the log-mode OTP through get-staging-otp.sh, disables
 * browser cache, and asserts that menu videos stay bounded while scrolling.
 */

import { execFileSync, spawn, spawnSync } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';

const DEFAULT_DOMAIN = 'https://staging.aura-coffee-bakery.ru';
const DEFAULT_SSH_TARGET = 'deploy@212.8.226.214';
const DEFAULT_BROWSER = '/snap/bin/chromium';

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function usage() {
  console.error(`Usage: scripts/production/check-staging-customer-video-smoke.mjs [options]

Options:
  --domain URL          Closed-staging origin. Default: ${DEFAULT_DOMAIN}
  --ssh-target TARGET   SSH target that can read staging auth and Redis OTP.
                        Default: ${DEFAULT_SSH_TARGET}
  --ssh-key PATH        SSH private key. Default: ~/.ssh/aura-vps
  --browser PATH        Chromium/Chrome executable. Default: ${DEFAULT_BROWSER}
  --phone PHONE         Controlled test phone. Default: generated +7996...
  --no-headless         Run Chromium visibly for debugging.
  -h, --help            Show this help.

The script never prints Basic Auth, OTP, JWT, or the test phone value.`);
}

function parseArgs(argv) {
  const options = {
    domain: DEFAULT_DOMAIN,
    sshTarget: process.env.AURA_STAGING_SSH_TARGET ?? DEFAULT_SSH_TARGET,
    sshKey: process.env.AURA_STAGING_SSH_KEY ?? `${process.env.HOME}/.ssh/aura-vps`,
    browser: process.env.AURA_STAGING_BROWSER ?? DEFAULT_BROWSER,
    phone: process.env.AURA_STAGING_SMOKE_PHONE ?? null,
    headless: true,
  };

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    switch (arg) {
      case '--domain':
        options.domain = requiredValue(argv, ++i, arg);
        break;
      case '--ssh-target':
        options.sshTarget = requiredValue(argv, ++i, arg);
        break;
      case '--ssh-key':
        options.sshKey = expandHome(requiredValue(argv, ++i, arg));
        break;
      case '--browser':
        options.browser = requiredValue(argv, ++i, arg);
        break;
      case '--phone':
        options.phone = requiredValue(argv, ++i, arg);
        break;
      case '--no-headless':
        options.headless = false;
        break;
      case '-h':
      case '--help':
        usage();
        process.exit(0);
        break;
      default:
        throw new Error(`unknown option: ${arg}`);
    }
  }

  options.domain = options.domain.replace(/\/+$/, '');
  options.phone ??= `+7996${String(Date.now() % 10000000).padStart(7, '0')}`;
  return options;
}

function requiredValue(argv, index, optionName) {
  const value = argv[index];
  if (!value || value.startsWith('--')) {
    throw new Error(`${optionName} requires a value`);
  }
  return value;
}

function expandHome(value) {
  if (value === '~') return process.env.HOME;
  if (value.startsWith('~/')) return path.join(process.env.HOME, value.slice(2));
  return value;
}

function parseStagingAuth(text) {
  const lines = Object.fromEntries(
    text
      .trim()
      .split(/\n+/)
      .map((line) => line.split('=')),
  );
  if (!lines.username || !lines.password) {
    throw new Error('staging auth file missing username/password');
  }
  return lines;
}

function sshBaseArgs(options) {
  return [
    '-i',
    options.sshKey,
    '-o',
    'IdentitiesOnly=yes',
    '-o',
    'BatchMode=yes',
    '-o',
    'ConnectTimeout=8',
    options.sshTarget,
  ];
}

function fetchStagingAuth(options) {
  const authText = execFileSync(
    'ssh',
    [...sshBaseArgs(options), 'cat /opt/aura-coffee/staging-basic-auth.txt'],
    { encoding: 'utf8' },
  );
  return parseStagingAuth(authText);
}

async function waitJson(url, timeoutMs = 15000) {
  const deadline = Date.now() + timeoutMs;
  let lastError;

  while (Date.now() < deadline) {
    try {
      const response = await fetch(url);
      if (response.ok) return response.json();
      lastError = new Error(`HTTP ${response.status}`);
    } catch (error) {
      lastError = error;
    }
    await sleep(150);
  }

  throw lastError ?? new Error(`timeout waiting for ${url}`);
}

function makeCdpClient(wsUrl, onEvent) {
  let sequence = 0;
  const pending = new Map();
  const socket = new WebSocket(wsUrl);

  socket.onmessage = (message) => {
    const payload = JSON.parse(message.data);
    if (payload.id != null) {
      const waiter = pending.get(payload.id);
      if (!waiter) return;
      pending.delete(payload.id);
      if (payload.error) {
        waiter.reject(
          new Error(
            `${payload.error.message}: ${JSON.stringify(payload.error.data ?? '')}`,
          ),
        );
      } else {
        waiter.resolve(payload.result);
      }
      return;
    }
    if (payload.method) onEvent?.(payload.method, payload.params ?? {});
  };

  return new Promise((resolve, reject) => {
    const timer = setTimeout(
      () => reject(new Error('CDP websocket open timeout')),
      10000,
    );
    socket.onopen = () => {
      clearTimeout(timer);
      resolve({
        send(method, params = {}) {
          const id = ++sequence;
          socket.send(JSON.stringify({ id, method, params }));
          return new Promise((resolve, reject) => {
            pending.set(id, { resolve, reject });
          });
        },
        close() {
          socket.close();
        },
      });
    };
    socket.onerror = () => {
      clearTimeout(timer);
      reject(new Error('CDP websocket error'));
    };
  });
}

function createMetrics(label) {
  return {
    label,
    started: 0,
    finished: 0,
    failed: 0,
    canceled: 0,
    active: 0,
    maxActive: 0,
    statuses: {},
    examples: [],
    errors: {},
  };
}

function snapshot(value) {
  return JSON.parse(JSON.stringify(value));
}

function isHeroMp4(url) {
  return (
    typeof url === 'string' &&
    /\/media\/menu\/[^/]+\/hero\.mp4(?:[?#].*)?$/.test(url)
  );
}

function shortMedia(url) {
  return url.match(/\/media\/menu\/([^/]+)\/hero\.mp4/)?.[1] ?? url;
}

function makeNetworkTracker() {
  let metrics = createMetrics('init');
  let requestToMedia = new Map();
  let active = new Set();

  return {
    reset(label) {
      metrics = createMetrics(label);
      requestToMedia = new Map();
      active = new Set();
    },
    snapshot() {
      return snapshot(metrics);
    },
    handle(method, params) {
      if (
        method === 'Network.requestWillBeSent' &&
        isHeroMp4(params.request?.url)
      ) {
        requestToMedia.set(params.requestId, params.request.url);
        active.add(params.requestId);
        metrics.started += 1;
        metrics.active = active.size;
        metrics.maxActive = Math.max(metrics.maxActive, active.size);
        if (metrics.examples.length < 8) {
          metrics.examples.push(shortMedia(params.request.url));
        }
      }
      if (
        method === 'Network.responseReceived' &&
        requestToMedia.has(params.requestId)
      ) {
        const status = String(params.response?.status ?? 'unknown');
        metrics.statuses[status] = (metrics.statuses[status] ?? 0) + 1;
      }
      if (
        method === 'Network.loadingFinished' &&
        requestToMedia.has(params.requestId)
      ) {
        metrics.finished += 1;
        active.delete(params.requestId);
        metrics.active = active.size;
      }
      if (
        method === 'Network.loadingFailed' &&
        requestToMedia.has(params.requestId)
      ) {
        metrics.failed += 1;
        if (params.canceled) metrics.canceled += 1;
        const key = params.errorText || 'unknown';
        metrics.errors[key] = (metrics.errors[key] ?? 0) + 1;
        active.delete(params.requestId);
        metrics.active = active.size;
      }
    },
  };
}

function getOtpFromStaging(phone) {
  const result = spawnSync('scripts/production/get-staging-otp.sh', [phone], {
    encoding: 'utf8',
    timeout: 25000,
    cwd: process.cwd(),
  });
  const code = result.stdout.match(/\b\d{6}\b/)?.[0];
  if (!code) {
    throw new Error(
      `OTP helper failed: status=${result.status} stderr=${result.stderr.slice(0, 220)}`,
    );
  }
  return code;
}

async function main() {
  if (typeof WebSocket !== 'function') {
    throw new Error('this script requires a Node runtime with global WebSocket');
  }

  const options = parseArgs(process.argv.slice(2));
  const { username, password } = fetchStagingAuth(options);
  const basicAuth = `Basic ${Buffer.from(`${username}:${password}`).toString('base64')}`;
  const port = 9700 + Math.floor(Math.random() * 250);
  const profileDir = mkdtempSync(path.join(tmpdir(), 'aura-chrome-'));
  const chromeArgs = [
    ...(options.headless ? ['--headless=new'] : []),
    '--disable-gpu',
    '--disable-dev-shm-usage',
    '--no-sandbox',
    '--autoplay-policy=no-user-gesture-required',
    '--mute-audio',
    '--window-size=390,844',
    '--force-device-scale-factor=1',
    '--disk-cache-size=1',
    `--user-data-dir=${profileDir}`,
    `--remote-debugging-port=${port}`,
    '--remote-debugging-address=127.0.0.1',
    'about:blank',
  ];
  const chrome = spawn(options.browser, chromeArgs, {
    stdio: ['ignore', 'ignore', 'pipe'],
  });
  let chromeStderr = '';
  chrome.stderr.on('data', (chunk) => {
    chromeStderr += chunk.toString();
  });

  const tracker = makeNetworkTracker();
  let client;

  try {
    await waitJson(`http://127.0.0.1:${port}/json/version`, 20000);
    const targetResponse = await fetch(`http://127.0.0.1:${port}/json/new`, {
      method: 'PUT',
    });
    if (!targetResponse.ok) {
      throw new Error(`new browser target failed: HTTP ${targetResponse.status}`);
    }
    const page = await targetResponse.json();
    client = await makeCdpClient(page.webSocketDebuggerUrl, (method, params) =>
      tracker.handle(method, params),
    );

    await client.send('Page.enable');
    await client.send('Network.enable');
    await client.send('Runtime.enable');
    await client.send('Network.setCacheDisabled', { cacheDisabled: true });
    await client.send('Network.clearBrowserCache');
    await client.send('Network.clearBrowserCookies');
    await client.send('Network.setExtraHTTPHeaders', {
      headers: { Authorization: basicAuth },
    });

    const evaluate = async (expression, timeout = 12000) => {
      const result = await client.send('Runtime.evaluate', {
        expression,
        awaitPromise: true,
        returnByValue: true,
        timeout,
      });
      if (result.exceptionDetails) {
        throw new Error(result.exceptionDetails.text || 'Runtime.evaluate failed');
      }
      return result.result.value;
    };

    const waitFor = async (expression, timeout = 15000) => {
      const ok = await evaluate(
        `new Promise((resolve) => {
          const start = Date.now();
          const tick = () => {
            let ok = false;
            try { ok = Boolean(${expression}); } catch (_) {}
            if (ok) return resolve(true);
            if (Date.now() - start > ${timeout}) return resolve(false);
            setTimeout(tick, 100);
          };
          tick();
        })`,
        timeout + 2000,
      );
      if (!ok) throw new Error(`waitFor timeout: ${expression}`);
    };

    const navigate = async (pathname) => {
      await client.send('Page.navigate', { url: `${options.domain}${pathname}` });
      await waitFor('document.readyState === "complete"');
    };

    const domSummary = () =>
      evaluate(`(() => {
        const videos = Array.from(document.querySelectorAll('video'));
        const withSrcAttr = videos.filter((video) => video.getAttribute('src'));
        const withCurrentSrc = videos.filter((video) => video.currentSrc);
        return {
          path: location.pathname,
          finePointer: matchMedia('(hover: hover) and (pointer: fine)').matches,
          anyFinePointer: matchMedia('(any-hover: hover) and (any-pointer: fine)').matches,
          videoTagCount: videos.length,
          srcAttrCount: withSrcAttr.length,
          currentSrcCount: withCurrentSrc.length,
          srcAttrs: withSrcAttr.slice(0, 5).map((video) => video.getAttribute('src')),
          currentSrcs: withCurrentSrc.slice(0, 5).map((video) => video.currentSrc),
          erroredVideos: videos.filter((video) => video.error).length,
          readyStates: withSrcAttr.slice(0, 5).map((video) => video.readyState),
          scrollY: Math.round(scrollY),
          scrollHeight: document.documentElement.scrollHeight,
          viewportHeight: innerHeight,
        };
      })()`);

    tracker.reset('login-warmup');
    await navigate('/login');
    await sleep(1800);
    const loginWarmup = {
      metrics: tracker.snapshot(),
      dom: await domSummary(),
    };

    await client.send('Network.setExtraHTTPHeaders', { headers: {} });
    const sendCodeResult = await evaluate(
      `fetch('/api/v1/auth/send-code', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone: ${JSON.stringify(options.phone)} }),
      }).then(async (response) => ({
        ok: response.ok,
        status: response.status,
        body: await response.text(),
      }))`,
    );
    if (!sendCodeResult.ok) {
      throw new Error(
        `send-code failed: HTTP ${sendCodeResult.status} body_length=${sendCodeResult.body.length}`,
      );
    }

    const otp = getOtpFromStaging(options.phone);
    const verifyResult = await evaluate(
      `fetch('/api/v1/auth/verify-code', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          phone: ${JSON.stringify(options.phone)},
          code: ${JSON.stringify(otp)},
        }),
      }).then(async (response) => ({
        ok: response.ok,
        status: response.status,
        bodyLength: (await response.text()).length,
      }))`,
    );
    if (!verifyResult.ok) {
      throw new Error(`verify-code failed: HTTP ${verifyResult.status}`);
    }

    tracker.reset('menu-scroll-no-cache');
    await navigate('/menu');
    await waitFor(
      'location.pathname === "/menu" && document.querySelectorAll("video").length > 0',
      20000,
    );
    await sleep(1100);
    const beforeScroll = {
      metrics: tracker.snapshot(),
      dom: await domSummary(),
    };

    const samples = [];
    for (let i = 0; i < 10; i += 1) {
      await evaluate(
        `window.scrollBy({ top: Math.max(280, innerHeight * 0.8), left: 0, behavior: 'instant' }); true`,
      );
      await sleep(250);
      samples.push({
        index: i,
        metrics: tracker.snapshot(),
        dom: await domSummary(),
      });
    }
    await sleep(800);
    const afterScroll = {
      metrics: tracker.snapshot(),
      dom: await domSummary(),
    };

    const assertions = {
      loginWarmupMaxActiveOk: loginWarmup.metrics.maxActive <= 1,
      menuMaxActiveOk: afterScroll.metrics.maxActive <= 2,
      activeDrainedOk: afterScroll.metrics.active <= 1,
      attachedBudgetOk: afterScroll.dom.srcAttrCount <= 1,
      noRequestStormOk: afterScroll.metrics.started <= 6,
      onMenuOk: afterScroll.dom.path === '/menu',
    };
    const ok = Object.values(assertions).every(Boolean);

    const report = {
      ok,
      assertions,
      loginWarmup,
      beforeScroll,
      afterScroll,
      sampleTail: samples.slice(-3),
    };
    console.log(JSON.stringify(report, null, 2));

    if (!ok) process.exitCode = 1;
  } finally {
    try {
      client?.close();
    } catch {
      // best effort only
    }
    chrome.kill('SIGTERM');
    await sleep(400);
    if (!chrome.killed) chrome.kill('SIGKILL');
    rmSync(profileDir, { recursive: true, force: true });
    if (process.exitCode && chromeStderr) {
      console.error(chromeStderr.slice(-2000));
    }
  }
}

main().catch((error) => {
  console.error(error.stack || error.message);
  process.exit(1);
});
