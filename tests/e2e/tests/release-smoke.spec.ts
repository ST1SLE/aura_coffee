import { expect, test, type APIRequestContext, type APIResponse, type BrowserContext, type Page } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, '../../..');
const baseURL = process.env.AURA_E2E_BASE_URL ?? 'http://127.0.0.1:8240';

interface CustomerTokens {
  user_id: string;
  access_token: string;
  refresh_token: string;
}

interface MenuResponse {
  categories: Array<{
    items: Array<{
      id: number;
      name_en: string;
      size_options: Array<{ id: number; label: string; available: boolean }>;
      modifiers: Array<{ id: number; name_en: string; available: boolean }>;
    }>;
  }>;
}

interface OrderDetail {
  id: string;
  status: string;
}

function runDockerPython(source: string): string {
  return execFileSync(
    'docker',
    ['compose', 'exec', '-T', 'core-api', 'python', '-c', source],
    {
      cwd: repoRoot,
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'pipe'],
    },
  ).trim();
}

function resetQaData(): void {
  execFileSync(path.join(repoRoot, 'scripts/reset-qa-data.sh'), {
    cwd: repoRoot,
    stdio: 'inherit',
  });
}

function qaUuid(name: string): string {
  const encoded = Buffer.from(name, 'utf8').toString('base64');
  return runDockerPython(`
import base64
from database.seeds.phase4_manual_test import _qa_uuid
name = base64.b64decode("${encoded}").decode()
print(_qa_uuid(name))
`);
}

function issueCustomerTokens(): CustomerTokens {
  const raw = runDockerPython(`
import json
from redis import Redis
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from core_api.settings import settings
from core_api.services.auth import AuthService
from database.seeds.phase4_manual_test import CUSTOMER_PHONE_HASH
from shared.models import User

engine = create_engine(settings.database_url)
with Session(engine) as db:
    user = db.scalar(select(User).where(User.phone_hash == CUSTOMER_PHONE_HASH))
    if user is None:
        raise SystemExit("QA customer missing; run database.seeds.phase4_manual_test")

redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
tokens = AuthService(redis_client).issue_tokens(user.id)
print(json.dumps({
    "user_id": str(user.id),
    "access_token": tokens.access_token,
    "refresh_token": tokens.refresh_token,
}))
`);
  return JSON.parse(raw) as CustomerTokens;
}

async function requireOk(response: APIResponse): Promise<void> {
  if (!response.ok()) {
    throw new Error(`${response.url()} -> ${response.status()}: ${await response.text()}`);
  }
}

function authHeaders(accessToken: string): Record<string, string> {
  return { Authorization: `Bearer ${accessToken}` };
}

async function authenticateCustomer(context: BrowserContext): Promise<CustomerTokens> {
  const tokens = issueCustomerTokens();
  await context.addCookies([
    {
      name: 'aura_customer_refresh_token',
      value: tokens.refresh_token,
      url: `${baseURL}/api/v1/auth/refresh`,
      httpOnly: true,
      sameSite: 'Strict',
      secure: false,
    },
  ]);
  return tokens;
}

async function seedCustomerCart(request: APIRequestContext, accessToken: string): Promise<void> {
  const menuResponse = await request.get('/api/v1/menu', {
    headers: { 'Accept-Language': 'en' },
  });
  await requireOk(menuResponse);
  const menu = (await menuResponse.json()) as MenuResponse;
  const item = menu.categories
    .flatMap((category) => category.items)
    .find((candidate) => candidate.name_en === 'Cappuccino (QA)');
  if (!item) throw new Error('Cappuccino (QA) missing from QA menu');

  const size = item.size_options.find((candidate) => candidate.label === 'M' && candidate.available)
    ?? item.size_options.find((candidate) => candidate.available);
  if (!size) throw new Error('Cappuccino (QA) has no available size');

  const modifier = item.modifiers.find((candidate) => candidate.name_en === 'Oat milk (QA)' && candidate.available);
  const headers = {
    ...authHeaders(accessToken),
    'Content-Type': 'application/json',
  };

  const clearResponse = await request.delete('/api/v1/cart', { headers });
  await requireOk(clearResponse);
  const addResponse = await request.post('/api/v1/cart/items', {
    headers,
    data: {
      menu_item_id: item.id,
      size_option_id: size.id,
      modifier_ids: modifier ? [modifier.id] : [],
      quantity: 1,
    },
  });
  await requireOk(addResponse);
}

async function createPickupOrderViaApi(request: APIRequestContext): Promise<string> {
  const tokens = issueCustomerTokens();
  await seedCustomerCart(request, tokens.access_token);

  const response = await request.post('/api/v1/orders', {
    headers: {
      ...authHeaders(tokens.access_token),
      'Content-Type': 'application/json',
    },
    data: { type: 'pickup' },
  });
  await requireOk(response);
  const order = (await response.json()) as OrderDetail;
  await expect
    .poll(async () => {
      const detailResponse = await request.get(`/api/v1/orders/${order.id}`, {
        headers: authHeaders(tokens.access_token),
      });
      await requireOk(detailResponse);
      const detail = (await detailResponse.json()) as OrderDetail;
      return detail.status;
    }, { timeout: 15_000 })
    .toBe('paid');
  return order.id;
}

async function staffLogin(page: Page, login: string, password: string): Promise<void> {
  await page.goto('/admin/login');
  await page.getByLabel(/Логин|Login/i).fill(login);
  await page.getByLabel(/Пароль|Password/i).fill(password);
  await page.getByRole('button', { name: /Войти|Sign in/i }).click();
}

async function staffAccessToken(page: Page): Promise<string> {
  const token = await page.evaluate(() => localStorage.getItem('accessToken'));
  if (!token) throw new Error('staff access token missing after login');
  return token;
}

async function staffOrderStatus(page: Page, orderId: string): Promise<string> {
  const token = await staffAccessToken(page);
  const response = await page.request.get(`/api/v1/admin/orders/${orderId}`, {
    headers: authHeaders(token),
  });
  await requireOk(response);
  const detail = (await response.json()) as OrderDetail;
  return detail.status;
}

test.describe.configure({ mode: 'serial' });

test.beforeAll(() => {
  resetQaData();
});

test('customer can submit pickup checkout and land on order detail', async ({ page }) => {
  const tokens = await authenticateCustomer(page.context());
  await seedCustomerCart(page.request, tokens.access_token);

  await page.goto('/checkout');

  await expect(page.getByRole('heading', { name: /Оформление заказа|Checkout/i })).toBeVisible();
  await expect(page.getByRole('heading', { name: /Итог заказа|Order total/i })).toBeVisible();

  await page.getByRole('button', { name: /Оформить заказ|Place order/i }).click();

  await expect(page).toHaveURL(/\/orders\/[0-9a-f-]{36}$/);
  await expect(page.getByRole('heading', { name: /Заказ #|Order #/i })).toBeVisible();
  await expect(page.getByText(/Капучино \(QA\)|Cappuccino \(QA\)/i)).toBeVisible();
});

test('admin logout to barista login switches roles and barista completes pickup flow', async ({ page }) => {
  const pickupPaidOrderId = await createPickupOrderViaApi(page.request);

  await staffLogin(page, 'admin', 'admin123');
  await expect(page).toHaveURL(/\/admin\/?$/);
  await expect(page.getByTestId('nav-users')).toBeVisible();

  await page.getByTestId('logout-sidebar').click();
  await expect(page).toHaveURL(/\/admin\/login/);

  await staffLogin(page, 'barista', 'barista123');
  await expect(page).toHaveURL(/\/admin\/orders/);
  await expect(page.getByTestId('nav-orders')).toBeVisible();
  await expect(page.getByTestId('nav-users')).toHaveCount(0);

  await page.goto('/admin/orders?status=paid&type=pickup');
  await expect(page.getByTestId(`order-row-${pickupPaidOrderId}`)).toBeVisible();

  await page.getByTestId(`order-details-${pickupPaidOrderId}`).click();
  await page.getByTestId('order-action-accept').click();
  await expect.poll(() => staffOrderStatus(page, pickupPaidOrderId)).toBe('preparing');

  await expect(page.getByTestId('order-action-ready')).toBeVisible();
  await page.getByTestId('order-action-ready').click();
  await expect.poll(() => staffOrderStatus(page, pickupPaidOrderId)).toBe('ready');

  await expect(page.getByTestId('order-action-handout')).toBeVisible();
  await page.getByTestId('order-action-handout').click();
  await expect.poll(() => staffOrderStatus(page, pickupPaidOrderId)).toBe('completed');
});

test('courier can take, pick up, and deliver a ready delivery assignment', async ({ page }) => {
  const assignmentId = qaUuid('assignment:delivery-ready-awaiting');

  await staffLogin(page, 'courier', 'courier123');
  await expect(page).toHaveURL(/\/admin\/courier/);

  const availableCard = page.getByTestId(`courier-assignment-${assignmentId}`);
  await expect(availableCard).toBeVisible();
  await expect(availableCard).toContainText(/Адрес будет доступен|Address available/i);
  await availableCard.getByRole('button', { name: /Взять|Take/i }).click();

  await page.getByRole('tab', { name: /Мои|Mine/i }).click();
  const mineCard = page.getByTestId(`courier-assignment-${assignmentId}`);
  await expect(mineCard).toBeVisible();
  await mineCard.getByRole('button', { name: /Забрал|Picked up/i }).click();

  await expect(mineCard.getByRole('button', { name: /Доставлен|Delivered/i })).toBeVisible();
  await mineCard.getByRole('button', { name: /Доставлен|Delivered/i }).click();

  await expect(mineCard).toHaveCount(0);
});
