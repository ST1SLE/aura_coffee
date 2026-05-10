#!/usr/bin/env node
/*
 * Closed-staging fake/log Stage 9 E2E smoke.
 *
 * Runs from an operator machine with SSH access to the staging deploy user.
 * It exercises the real deployed API through nginx staging auth:
 * health -> log-mode customer OTP -> menu -> cart -> pickup order ->
 * fake YuKassa callback -> staff login -> staff status transitions.
 *
 * The script never prints Basic Auth credentials, admin credentials, OTP,
 * JWTs, staging cookies, or the generated test phone.
 */

import { execFileSync, spawnSync } from 'node:child_process';
import { randomUUID } from 'node:crypto';
import path from 'node:path';

const DEFAULT_DOMAIN = 'https://staging.aura-coffee-bakery.ru';
const DEFAULT_SSH_TARGET = 'deploy@212.8.226.214';

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function usage() {
  console.error(`Usage: scripts/production/check-staging-fake-log-e2e-smoke.mjs [options]

Options:
  --domain URL          Closed-staging origin. Default: ${DEFAULT_DOMAIN}
  --ssh-target TARGET   SSH target that can read staging env/OTP/logs.
                        Default: ${DEFAULT_SSH_TARGET}
  --ssh-key PATH        SSH private key. Default: ~/.ssh/aura-vps
  --phone PHONE         Controlled +7 test phone. Default: generated +7995...
  --otp-wait SECONDS    OTP poll timeout. Default: 30
  --payment-wait MS     Fake payment callback timeout. Default: 60000
  --skip-log-scan       Skip raw phone/OTP log redaction scan.
  -h, --help            Show this help.

The script never prints Basic Auth, admin password, staging cookie, OTP, JWT,
or the test phone value.`);
}

function requiredValue(argv, index, optionName) {
  const value = argv[index];
  if (!value || value.startsWith('--')) {
    throw new Error(`${optionName} requires a value`);
  }
  return value;
}

function positiveInt(value, optionName) {
  if (!/^[1-9][0-9]*$/.test(value)) {
    throw new Error(`${optionName} must be a positive integer`);
  }
  return Number(value);
}

function expandHome(value) {
  if (value === '~') return process.env.HOME;
  if (value.startsWith('~/')) return path.join(process.env.HOME, value.slice(2));
  return value;
}

function parseArgs(argv) {
  const options = {
    domain: DEFAULT_DOMAIN,
    sshTarget: process.env.AURA_STAGING_SSH_TARGET ?? DEFAULT_SSH_TARGET,
    sshKey: process.env.AURA_STAGING_SSH_KEY ?? `${process.env.HOME}/.ssh/aura-vps`,
    phone: process.env.AURA_STAGING_E2E_PHONE ?? null,
    otpWaitSeconds: positiveInt(process.env.AURA_OTP_WAIT_SECONDS ?? '30', 'AURA_OTP_WAIT_SECONDS'),
    paymentWaitMs: positiveInt(process.env.AURA_STAGING_E2E_PAYMENT_WAIT_MS ?? '60000', 'AURA_STAGING_E2E_PAYMENT_WAIT_MS'),
    logScan: true,
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
      case '--phone':
        options.phone = requiredValue(argv, ++i, arg);
        break;
      case '--otp-wait':
        options.otpWaitSeconds = positiveInt(requiredValue(argv, ++i, arg), arg);
        break;
      case '--payment-wait':
        options.paymentWaitMs = positiveInt(requiredValue(argv, ++i, arg), arg);
        break;
      case '--skip-log-scan':
        options.logScan = false;
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
  options.phone ??= `+7995${String(Date.now() % 10000000).padStart(7, '0')}`;
  return options;
}

function parseKeyValues(text) {
  const out = {};
  for (const rawLine of text.split(/\n+/)) {
    const line = rawLine.trim();
    if (!line) continue;
    const index = line.indexOf('=');
    if (index <= 0) continue;
    const key = line.slice(0, index);
    let value = line.slice(index + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    out[key] = value;
  }
  return out;
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

function shellQuote(value) {
  return `'${String(value).replace(/'/g, `'\\''`)}'`;
}

function runSsh(options, remoteScript, env = {}) {
  const assignments = Object.entries(env)
    .map(([key, value]) => `${key}=${shellQuote(value)}`)
    .join(' ');
  const command = `${assignments}${assignments ? ' ' : ''}bash -lc ${shellQuote(remoteScript)}`;
  try {
    return execFileSync('ssh', [...sshBaseArgs(options), command], {
      encoding: 'utf8',
      maxBuffer: 1024 * 1024 * 8,
      stdio: ['ignore', 'pipe', 'pipe'],
    });
  } catch (error) {
    const status = typeof error.status === 'number' ? error.status : 'unknown';
    const stderrLength = Buffer.isBuffer(error.stderr) ? error.stderr.length : 0;
    throw new Error(`ssh command failed: status=${status} stderr_length=${stderrLength}`);
  }
}

function fetchRemoteConfig(options) {
  const script = `
set -euo pipefail
if [ -r /opt/aura-coffee/.env.production ]; then
  awk -F= '
    $0 !~ /^[[:space:]]*#/ && $1 ~ /^(ADMIN_LOGIN|ADMIN_PASSWORD|SMS_BACKEND|YUKASSA_BACKEND|AURA_STAGING_ACCESS_COOKIE)$/ {
      key=$1
      sub(/^[^=]*=/, "")
      print key "=" $0
    }
  ' /opt/aura-coffee/.env.production
fi
if [ -r /opt/aura-coffee/staging-basic-auth.txt ]; then
  awk -F= '
    $1 == "username" {print "BASIC_USERNAME=" $2}
    $1 == "password" {print "BASIC_PASSWORD=" $2}
  ' /opt/aura-coffee/staging-basic-auth.txt
fi
`;
  return parseKeyValues(runSsh(options, script));
}

function basicAuthHeader(config) {
  if (!config.BASIC_USERNAME || !config.BASIC_PASSWORD) return null;
  return `Basic ${Buffer.from(`${config.BASIC_USERNAME}:${config.BASIC_PASSWORD}`).toString('base64')}`;
}

function getSetCookies(headers) {
  if (typeof headers.getSetCookie === 'function') return headers.getSetCookie();
  const single = headers.get('set-cookie');
  return single ? [single] : [];
}

function extractStagingCookie(headers) {
  for (const line of getSetCookies(headers)) {
    const match = line.match(/(?:^|;\s*)aura_staging=([^;]+)/);
    if (match) return `aura_staging=${match[1]}`;
  }
  return null;
}

async function establishCookie(options, config) {
  if (config.AURA_STAGING_ACCESS_COOKIE) {
    return `aura_staging=${config.AURA_STAGING_ACCESS_COOKIE}`;
  }

  const auth = basicAuthHeader(config);
  if (!auth) {
    throw new Error('staging cookie and Basic Auth credentials are unavailable');
  }

  const response = await fetch(`${options.domain}/health`, {
    headers: { Authorization: auth },
  });
  const cookie = extractStagingCookie(response.headers);
  if (!response.ok || !cookie) {
    throw new Error(`could not establish staging cookie: HTTP ${response.status}`);
  }
  return cookie;
}

class HttpClient {
  constructor(domain, cookieHeader) {
    this.domain = domain;
    this.cookieHeader = cookieHeader;
  }

  async request(pathname, { method = 'GET', token, body, expected = [200], headers = {} } = {}) {
    const requestHeaders = {
      Cookie: this.cookieHeader,
      Accept: 'application/json',
      ...headers,
    };
    if (token) requestHeaders.Authorization = `Bearer ${token}`;
    if (body !== undefined) requestHeaders['Content-Type'] = 'application/json';

    const response = await fetch(`${this.domain}${pathname}`, {
      method,
      headers: requestHeaders,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const text = await response.text();
    if (!expected.includes(response.status)) {
      throw new Error(
        `${method} ${pathname} failed: HTTP ${response.status}, body_length=${text.length}`,
      );
    }
    const json = text ? JSON.parse(text) : null;
    return { status: response.status, json, headers: response.headers };
  }
}

function getOtpFromStaging(options) {
  const result = spawnSync('scripts/production/get-staging-otp.sh', [options.phone], {
    encoding: 'utf8',
    timeout: (options.otpWaitSeconds + 25) * 1000,
    cwd: process.cwd(),
    env: {
      ...process.env,
      AURA_STAGING_SSH_TARGET: options.sshTarget,
      AURA_STAGING_SSH_KEY: options.sshKey,
      AURA_OTP_WAIT_SECONDS: String(options.otpWaitSeconds),
    },
  });
  const code = result.stdout.match(/\b\d{6}\b/)?.[0];
  if (!code) {
    throw new Error(
      `OTP helper failed: status=${result.status} stderr_length=${result.stderr.length}`,
    );
  }
  return code;
}

function selectOrderableMenuItem(menu) {
  for (const category of menu.categories ?? []) {
    for (const item of category.items ?? []) {
      if (item.available !== true) continue;
      if (item.inventory_quantity !== null && item.inventory_quantity <= 0) continue;
      const size =
        item.size_options?.find((candidate) => candidate.available && candidate.price > 0) ??
        item.size_options?.find((candidate) => candidate.available) ??
        null;
      const unitPrice = size ? size.price : item.base_price;
      if (unitPrice <= 0) continue;
      return { category, item, size, unitPrice };
    }
  }
  throw new Error('no orderable positive-price menu item found');
}

async function poll(label, fn, { timeoutMs, intervalMs = 1000 }) {
  const deadline = Date.now() + timeoutMs;
  let lastSummary = 'none';
  while (Date.now() < deadline) {
    const result = await fn();
    if (result.done) return result.value;
    lastSummary = result.summary ?? lastSummary;
    await sleep(intervalMs);
  }
  throw new Error(`${label} timed out after ${timeoutMs}ms; last=${lastSummary}`);
}

function assertRequiredConfig(config) {
  if (config.SMS_BACKEND !== 'log') {
    throw new Error(`expected SMS_BACKEND=log on closed staging, got ${config.SMS_BACKEND || 'unset'}`);
  }
  if (config.YUKASSA_BACKEND !== 'fake') {
    throw new Error(
      `expected YUKASSA_BACKEND=fake on closed staging, got ${config.YUKASSA_BACKEND || 'unset'}`,
    );
  }
}

function defaultStaffCandidates(config) {
  const candidates = [];
  if (config.ADMIN_LOGIN && config.ADMIN_PASSWORD) {
    candidates.push({
      source: 'env_admin',
      login: config.ADMIN_LOGIN,
      password: config.ADMIN_PASSWORD,
      allowedRoles: new Set(['admin']),
    });
  }
  return candidates;
}

async function loginStaff(http, candidates) {
  const failures = [];
  for (const candidate of candidates) {
    const response = await http.request('/api/v1/staff/auth/login', {
      method: 'POST',
      expected: [200, 401, 429],
      body: {
        login: candidate.login,
        password: candidate.password,
      },
    });

    if (response.status === 401) {
      failures.push(`${candidate.source}:401`);
      continue;
    }
    if (response.status === 429) {
      failures.push(`${candidate.source}:429`);
      continue;
    }

    const tokens = response.json;
    if (!tokens?.access_token || !candidate.allowedRoles.has(tokens.role)) {
      throw new Error(
        `staff login for ${candidate.source} returned unexpected role=${tokens?.role}`,
      );
    }
    return {
      source: candidate.source,
      role: tokens.role,
      accessToken: tokens.access_token,
    };
  }

  throw new Error(`no usable staff credentials accepted; failures=${failures.join(',')}`);
}

function createTemporaryStaff(options) {
  const login = `smoke_barista_${Date.now()}_${randomUUID().slice(0, 8)}`;
  const password = `${randomUUID()}${randomUUID()}`;
  const script = `
set -euo pipefail
cd /opt/aura-coffee/app
scripts/production/compose.sh --tls --staging-auth /opt/aura-coffee/.env.production exec -T -e STAFF_LOGIN -e STAFF_PASSWORD core-api python - <<'PY'
import os
import uuid

import bcrypt

from core_api.deps.database import SessionLocal
from shared.enums import StaffRole
from shared.models.staff_account import StaffAccount

login = os.environ["STAFF_LOGIN"]
password = os.environ["STAFF_PASSWORD"]

with SessionLocal() as db:
    existing = db.query(StaffAccount).filter(StaffAccount.login == login).first()
    if existing is not None:
        db.delete(existing)
        db.commit()
    db.add(
        StaffAccount(
            id=uuid.uuid4(),
            login=login,
            password_hash=bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8"),
            role=StaffRole.BARISTA,
            display_name="Smoke Barista",
            is_active=True,
        )
    )
    db.commit()
print("temporary_staff_created=1")
PY
`;
  runSsh(options, script, { STAFF_LOGIN: login, STAFF_PASSWORD: password });
  return {
    source: 'temporary_barista',
    login,
    password,
    allowedRoles: new Set(['barista']),
  };
}

function cleanupTemporaryStaff(options, login) {
  const script = `
set -euo pipefail
case "$STAFF_LOGIN" in
  smoke_barista_*) ;;
  *) printf 'temporary_staff_cleanup=refused\\n'; exit 2 ;;
esac
cd /opt/aura-coffee/app
scripts/production/compose.sh --tls --staging-auth /opt/aura-coffee/.env.production exec -T -e STAFF_LOGIN core-api python - <<'PY'
import os

from core_api.deps.database import SessionLocal
from shared.models.staff_account import StaffAccount

login = os.environ["STAFF_LOGIN"]
with SessionLocal() as db:
    deleted = (
        db.query(StaffAccount)
        .filter(StaffAccount.login == login)
        .delete(synchronize_session=False)
    )
    db.commit()
print(f"temporary_staff_deleted={deleted}")
PY
`;
  runSsh(options, script, { STAFF_LOGIN: login });
}

function checkLogRedaction(options, phone, otp) {
  const script = `
set -euo pipefail
cd /opt/aura-coffee/app
logs="$(scripts/production/compose.sh --tls --staging-auth /opt/aura-coffee/.env.production logs --since 15m --tail=1000 --no-color core-api sms-worker payment-worker payment-webhook 2>/dev/null || true)"
hits=""
if printf '%s' "$logs" | grep -F -- "$PHONE" >/dev/null; then
  hits="$hits phone"
fi
if printf '%s' "$logs" | grep -E "(^|[^0-9])$OTP([^0-9]|$)" >/dev/null; then
  hits="$hits otp"
fi
if [ -n "$hits" ]; then
  printf 'sensitive_log_hits=%s\\n' "$hits"
  exit 3
fi
printf 'sensitive_log_hits=none\\n'
`;
  return parseKeyValues(runSsh(options, script, { PHONE: phone, OTP: otp }));
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  let temporaryStaff = null;

  try {
    const config = fetchRemoteConfig(options);
    assertRequiredConfig(config);

    const cookieHeader = await establishCookie(options, config);
    const http = new HttpClient(options.domain, cookieHeader);

    const health = (await http.request('/health')).json;
    if (health?.status !== 'ok') {
      throw new Error(`health check failed: status=${String(health?.status)}`);
    }
    if (health?.yukassa_backend !== 'fake') {
      throw new Error(`health check reported non-fake YuKassa backend: ${health?.yukassa_backend}`);
    }

    await http.request('/api/v1/auth/send-code', {
      method: 'POST',
      body: { phone: options.phone },
    });
    const otp = getOtpFromStaging(options);
    const customerTokens = (
      await http.request('/api/v1/auth/verify-code', {
        method: 'POST',
        body: { phone: options.phone, code: otp },
      })
    ).json;
    if (!customerTokens?.access_token) {
      throw new Error('customer verify-code did not return an access token');
    }
    const customerToken = customerTokens.access_token;

    const menu = (await http.request('/api/v1/menu?available=true')).json;
    const selection = selectOrderableMenuItem(menu);

    await http.request('/api/v1/cart', {
      method: 'DELETE',
      token: customerToken,
    });
    const cart = (
      await http.request('/api/v1/cart/items', {
        method: 'POST',
        token: customerToken,
        expected: [201],
        body: {
          menu_item_id: selection.item.id,
          size_option_id: selection.size?.id ?? null,
          modifier_ids: [],
          quantity: 1,
        },
      })
    ).json;
    if ((cart.items ?? []).length !== 1 || cart.subtotal <= 0) {
      throw new Error('cart did not contain one positive-price line after add');
    }

    const createdOrder = (
      await http.request('/api/v1/orders', {
        method: 'POST',
        token: customerToken,
        expected: [201],
        body: {
          type: 'pickup',
          points_to_use: 0,
        },
      })
    ).json;
    const orderId = createdOrder.id;
    if (!orderId) throw new Error('order creation response did not include id');

    const paidOrder = await poll(
      'fake payment callback',
      async () => {
        const order = (
          await http.request(`/api/v1/orders/${orderId}`, {
            token: customerToken,
          })
        ).json;
        return {
          done: order.status === 'paid',
          value: order,
          summary: `order_status=${order.status}`,
        };
      },
      { timeoutMs: options.paymentWaitMs },
    );

    let staffSession;
    try {
      staffSession = await loginStaff(http, defaultStaffCandidates(config));
    } catch (error) {
      if (!String(error.message).startsWith('no usable staff credentials accepted')) {
        throw error;
      }
      temporaryStaff = createTemporaryStaff(options);
      staffSession = await loginStaff(http, [temporaryStaff]);
    }
    const staffToken = staffSession.accessToken;

    const staffFeed = (
      await http.request('/api/v1/admin/orders?status=active&per_page=100', {
        token: staffToken,
      })
    ).json;
    const feedContainsOrder = (staffFeed.orders ?? []).some((order) => order.id === orderId);
    if (!feedContainsOrder) {
      throw new Error('staff active order feed did not include the smoke order');
    }

    await http.request(`/api/v1/admin/orders/${orderId}`, {
      token: staffToken,
    });

    const transitionStatuses = [];
    for (const nextStatus of ['preparing', 'ready', 'completed']) {
      const transitioned = (
        await http.request(`/api/v1/orders/${orderId}/status`, {
          method: 'PATCH',
          token: staffToken,
          body: { new_status: nextStatus },
        })
      ).json;
      transitionStatuses.push(transitioned.status);
      if (transitioned.status !== nextStatus) {
        throw new Error(`expected transition to ${nextStatus}, got ${transitioned.status}`);
      }
    }

    const finalOrder = (
      await http.request(`/api/v1/orders/${orderId}`, {
        token: customerToken,
      })
    ).json;
    if (finalOrder.status !== 'completed') {
      throw new Error(`customer final order status expected completed, got ${finalOrder.status}`);
    }

    await http.request('/api/v1/cart', {
      method: 'DELETE',
      token: customerToken,
    });

    const redaction = options.logScan
      ? checkLogRedaction(options, options.phone, otp)
      : { sensitive_log_hits: 'skipped' };

    const report = {
      ok: true,
      provider_modes: {
        sms_backend: config.SMS_BACKEND,
        yukassa_backend: health.yukassa_backend,
      },
      order: {
        id: orderId,
        type: finalOrder.type,
        initial_status: createdOrder.status,
        paid_status: paidOrder.status,
        transitions: transitionStatuses,
        final_status: finalOrder.status,
        total: finalOrder.total,
      },
      menu_selection: {
        category_id: selection.category.id,
        item_id: selection.item.id,
        size_option_id: selection.size?.id ?? null,
        unit_price: selection.unitPrice,
      },
      staff: {
        credential_source: staffSession.source,
        role: staffSession.role,
      },
      staff_feed: {
        checked: true,
        total_count: staffFeed.total_count,
        contained_smoke_order: feedContainsOrder,
      },
      redaction,
    };

    console.log(JSON.stringify(report, null, 2));
  } finally {
    if (temporaryStaff?.login) {
      cleanupTemporaryStaff(options, temporaryStaff.login);
    }
  }
}

main().catch((error) => {
  console.error(error.stack || error.message);
  process.exit(1);
});
