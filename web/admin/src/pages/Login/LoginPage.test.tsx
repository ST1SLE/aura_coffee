import {
  render,
  screen,
  fireEvent,
  waitFor,
  act,
} from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import '@/i18n/config';
import i18n from '@/i18n/config';
import { LoginPage } from './LoginPage';
import * as client from '@/api/client';
import * as auth from '@/lib/auth';

// Мок модуля client — staffLogin и access-token setter
vi.mock('@/api/client', async (importOriginal) => {
  const original = await importOriginal<typeof client>();
  return {
    ...original,
    staffLogin: vi.fn(),
    setAccessToken: vi.fn(),
  };
});

// Мок @/lib/auth — нужно следить за setRole
vi.mock('@/lib/auth', async (importOriginal) => {
  const original = await importOriginal<typeof auth>();
  return {
    ...original,
    setRole: vi.fn(),
  };
});

function renderLoginPage(initialPath = '/login') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<div>dashboard</div>} />
        <Route path="/menu" element={<div>menu-page</div>} />
        <Route path="/courier" element={<div>courier-page</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('LoginPage', () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    localStorage.clear();
    // Фиксируем язык RU чтобы тексты были предсказуемы
    await i18n.changeLanguage('ru');
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // a) Поля есть, кнопка отключена при пустых полях
  it('рендерит поля логина и пароля; кнопка отключена при пустых значениях', () => {
    renderLoginPage();
    expect(screen.getByLabelText(/логин/i)).toBeDefined();
    expect(screen.getByLabelText(/пароль/i)).toBeDefined();
    const submitBtn = screen.getByRole('button', { name: /войти/i });
    expect((submitBtn as HTMLButtonElement).disabled).toBe(true);
  });

  // b) Кнопка активна, когда оба поля заполнены
  it('активирует кнопку когда заполнены оба поля', () => {
    renderLoginPage();
    fireEvent.change(screen.getByLabelText(/логин/i), {
      target: { value: 'admin' },
    });
    fireEvent.change(screen.getByLabelText(/пароль/i), {
      target: { value: 'pass' },
    });
    const submitBtn = screen.getByRole('button', { name: /войти/i });
    expect((submitBtn as HTMLButtonElement).disabled).toBe(false);
  });

  // c) Успешный логин: staffLogin вызван, access token сохранён, навигация на /
  it('при успешном логине вызывает staffLogin, сохраняет access token и переходит на /', async () => {
    vi.mocked(client.staffLogin).mockResolvedValueOnce({
      access_token: 'tok123',
      refresh_token: 'ref123',
      role: 'admin',
    });

    renderLoginPage('/login');
    fireEvent.change(screen.getByLabelText(/логин/i), {
      target: { value: 'admin' },
    });
    fireEvent.change(screen.getByLabelText(/пароль/i), {
      target: { value: 'pass' },
    });
    fireEvent.click(screen.getByRole('button', { name: /войти/i }));

    await waitFor(() => {
      expect(vi.mocked(client.staffLogin)).toHaveBeenCalledWith(
        'admin',
        'pass',
      );
    });
    expect(vi.mocked(client.setAccessToken)).toHaveBeenCalledWith('tok123');
    expect(localStorage.getItem('refreshToken')).toBeNull();
    await waitFor(() => {
      expect(screen.getByText('dashboard')).toBeDefined();
    });
  });

  // d) returnUrl в query param — навигация на /menu
  it('при returnUrl=%2Fmenu переходит на /menu после успешного логина', async () => {
    vi.mocked(client.staffLogin).mockResolvedValueOnce({
      access_token: 'tok',
      refresh_token: 'ref',
      role: 'admin',
    });

    renderLoginPage('/login?returnUrl=%2Fmenu');
    fireEvent.change(screen.getByLabelText(/логин/i), {
      target: { value: 'admin' },
    });
    fireEvent.change(screen.getByLabelText(/пароль/i), {
      target: { value: 'pass' },
    });
    fireEvent.click(screen.getByRole('button', { name: /войти/i }));

    await waitFor(() => {
      expect(screen.getByText('menu-page')).toBeDefined();
    });
  });

  // e) ApiError(401): показывает инлайн-ошибку, access token НЕ сохраняется
  it('при ApiError(401) показывает invalidCredentials и не сохраняет access token', async () => {
    vi.mocked(client.staffLogin).mockRejectedValueOnce(
      new client.ApiError(401, null, 'HTTP 401: /api/v1/staff/auth/login'),
    );

    renderLoginPage();
    fireEvent.change(screen.getByLabelText(/логин/i), {
      target: { value: 'admin' },
    });
    fireEvent.change(screen.getByLabelText(/пароль/i), {
      target: { value: 'wrong' },
    });
    fireEvent.click(screen.getByRole('button', { name: /войти/i }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeDefined();
    });
    expect(screen.getByRole('alert').textContent).toMatch(/неверный логин/i);
    expect(vi.mocked(client.setAccessToken)).not.toHaveBeenCalled();
  });

  // g) Успешный логин курьера: редирект на /courier
  it('при роли courier переходит на /courier', async () => {
    vi.mocked(client.staffLogin).mockResolvedValueOnce({
      access_token: 'tok-c',
      refresh_token: 'ref-c',
      role: 'courier',
    });

    renderLoginPage('/login');
    fireEvent.change(screen.getByLabelText(/логин/i), {
      target: { value: 'crr' },
    });
    fireEvent.change(screen.getByLabelText(/пароль/i), {
      target: { value: 'pass' },
    });
    fireEvent.click(screen.getByRole('button', { name: /войти/i }));

    await waitFor(() => {
      expect(screen.getByText('courier-page')).toBeDefined();
    });
  });

  // h) Курьер игнорирует returnUrl и всё равно попадает на /courier
  it('courier-роль игнорирует returnUrl и идёт на /courier', async () => {
    vi.mocked(client.staffLogin).mockResolvedValueOnce({
      access_token: 'tok-c',
      refresh_token: 'ref-c',
      role: 'courier',
    });

    renderLoginPage('/login?returnUrl=%2Fmenu');
    fireEvent.change(screen.getByLabelText(/логин/i), {
      target: { value: 'crr' },
    });
    fireEvent.change(screen.getByLabelText(/пароль/i), {
      target: { value: 'pass' },
    });
    fireEvent.click(screen.getByRole('button', { name: /войти/i }));

    await waitFor(() => {
      expect(screen.getByText('courier-page')).toBeDefined();
    });
    expect(screen.queryByText('menu-page')).toBeNull();
  });

  // i) setRole вызывается с ролью из ответа
  it('вызывает setRole(result.role) после успешного логина', async () => {
    vi.mocked(client.staffLogin).mockResolvedValueOnce({
      access_token: 'tok',
      refresh_token: 'ref',
      role: 'barista',
    });

    renderLoginPage('/login');
    fireEvent.change(screen.getByLabelText(/логин/i), {
      target: { value: 'b' },
    });
    fireEvent.change(screen.getByLabelText(/пароль/i), {
      target: { value: 'p' },
    });
    fireEvent.click(screen.getByRole('button', { name: /войти/i }));

    await waitFor(() => {
      expect(vi.mocked(auth.setRole)).toHaveBeenCalledWith('barista');
    });
  });

  // f) Кнопка отключена во время запроса
  it('кнопка отключена пока выполняется запрос', async () => {
    let resolveLogin!: (v: {
      access_token: string;
      refresh_token: string;
      role: string;
    }) => void;
    vi.mocked(client.staffLogin).mockReturnValue(
      new Promise((res) => {
        resolveLogin = res;
      }),
    );

    renderLoginPage();
    fireEvent.change(screen.getByLabelText(/логин/i), {
      target: { value: 'admin' },
    });
    fireEvent.change(screen.getByLabelText(/пароль/i), {
      target: { value: 'pass' },
    });
    fireEvent.click(screen.getByRole('button'));

    await waitFor(() => {
      expect(screen.getByRole('button') as HTMLButtonElement).toHaveProperty(
        'disabled',
        true,
      );
    });

    // Завершаем промис, чтобы не было утечек
    await act(async () => {
      resolveLogin({
        access_token: 'tok',
        refresh_token: 'ref',
        role: 'admin',
      });
    });
  });
});
