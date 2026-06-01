import type { ChatResponse, PhaseSummary } from '@/types/curriculum';

const baseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  if (!response.ok) {
    throw new Error(`API ${response.status}: ${await response.text()}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  listPhases: () => request<PhaseSummary[]>('/api/curriculum/phases'),

  sendChat: (payload: { user_id: string; phase: number; message: string }) =>
    request<ChatResponse>('/api/chat', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
};
