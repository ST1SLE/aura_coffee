// TODO: wire via staff-auth — replace this stub with the real token getter
function getAccessToken(): string | null {
  return localStorage.getItem('accessToken');
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly body: unknown,
    message: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '';

export async function authenticatedFetch(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const token = getAccessToken();

  const authHeaders: Record<string, string> = token
    ? { Authorization: `Bearer ${token}` }
    : {};

  const merged: RequestInit = {
    ...init,
    headers: {
      ...authHeaders,
      ...(init.headers as Record<string, string> | undefined),
    },
  };

  const response = await fetch(`${BASE_URL}${path}`, merged);

  if (!response.ok) {
    let body: unknown = null;
    try {
      body = await response.clone().json();
    } catch {
      // тело не JSON — оставляем null
    }
    throw new ApiError(
      response.status,
      body,
      `HTTP ${response.status}: ${path}`,
    );
  }

  return response;
}
