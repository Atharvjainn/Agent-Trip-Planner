function getBaseUrl() {
  if (typeof window !== 'undefined') {
    const { protocol, hostname } = window.location;
    if (process.env.NEXT_PUBLIC_API_URL && !process.env.NEXT_PUBLIC_API_URL.includes('localhost')) {
      return process.env.NEXT_PUBLIC_API_URL;
    }
    return `${protocol}//${hostname}:5000`;
  }
  return process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5000';
}

export interface ApiResponse<T> {
  status: 'success' | 'error';
  data?: T;
  message?: string;
}

export class ApiError extends Error {
  public readonly status: number;
  public readonly message: string;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.message = message;
  }
}

export async function apiFetch<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${getBaseUrl()}${endpoint}`;
  const headers = new Headers(options.headers || {});
  
  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(url, {
    ...options,
    headers,
    credentials: 'include',
  });

  let json: Record<string, unknown> | null = null;
  try {
    json = (await response.json()) as Record<string, unknown>;
  } catch {
    json = null;
  }

  if (!response.ok) {
    const errorMessage =
      (typeof json?.message === 'string' ? json.message : undefined) ||
      `Request failed with status ${response.status}`;
    throw new ApiError(errorMessage, response.status);
  }

  if (json && json.status === 'success' && 'data' in json) {
    return json.data as T;
  }

  return json as unknown as T;
}
