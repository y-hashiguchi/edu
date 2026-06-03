import type {
  ChatMessage,
  ChatResponse,
  PhaseSummary,
  ProgressCompleteResponse,
  ProgressOut,
} from '@/types/curriculum';

const baseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

let _onUnauthorized: (() => void) | null = null;
let _tokenGetter: (() => string | null) | null = null;

export function registerUnauthorizedHandler(cb: () => void) {
  _onUnauthorized = cb;
}

export function registerTokenGetter(getter: () => string | null) {
  _tokenGetter = getter;
}

function getToken(): string | null {
  if (_tokenGetter) return _tokenGetter();
  // Fallback: read from localStorage if the getter hasn't been registered yet
  // (e.g. during early app boot before main.ts runs).
  try {
    const persisted = localStorage.getItem('auth');
    if (!persisted) return null;
    return (JSON.parse(persisted) as { token: string | null }).token;
  } catch {
    return null;
  }
}

export async function rawRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken();
  const headers = new Headers(init?.headers);
  headers.set('Content-Type', 'application/json');
  if (token) headers.set('Authorization', `Bearer ${token}`);

  const response = await fetch(`${baseUrl}${path}`, { ...init, headers });

  if (response.status === 401) {
    if (_onUnauthorized) _onUnauthorized();
    throw new Error('API 401: Unauthorized');
  }
  if (!response.ok) {
    throw new Error(`API ${response.status}: ${await response.text()}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  listPhases: () => rawRequest<PhaseSummary[]>('/api/curriculum/phases'),

  listProgress: () => rawRequest<ProgressOut[]>('/api/progress'),

  completePhase: (phase: number) =>
    rawRequest<ProgressCompleteResponse>(`/api/progress/${phase}/complete`, {
      method: 'POST',
    }),

  getChatHistory: (phase: number) =>
    rawRequest<ChatMessage[]>(`/api/chat/history/${phase}`),

  sendChat: (payload: { phase: number; message: string }) =>
    rawRequest<ChatResponse>('/api/chat', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
};
