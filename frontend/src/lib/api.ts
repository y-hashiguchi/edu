import type {
  ChatMessage,
  ChatResponse,
  GradingAttempt,
  PhaseSummary,
  ProgressCompleteResponse,
  ProgressOut,
  Submission,
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
  try {
    const persisted = localStorage.getItem('auth');
    if (!persisted) return null;
    return (JSON.parse(persisted) as { token: string | null }).token;
  } catch {
    return null;
  }
}

export class ApiCooldownError extends Error {
  constructor(public retryAfterSeconds: number) {
    super(`cooldown active; retry in ${retryAfterSeconds}s`);
    this.name = 'ApiCooldownError';
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (response.status === 401) {
    if (_onUnauthorized) _onUnauthorized();
    throw new Error('API 401: Unauthorized');
  }
  if (response.status === 429) {
    const retryAfter = Number(response.headers.get('Retry-After') ?? '60');
    throw new ApiCooldownError(Number.isFinite(retryAfter) ? retryAfter : 60);
  }
  if (!response.ok) {
    throw new Error(`API ${response.status}: ${await response.text()}`);
  }
  return response.json() as Promise<T>;
}

export async function rawRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken();
  const headers = new Headers(init?.headers);
  headers.set('Content-Type', 'application/json');
  if (token) headers.set('Authorization', `Bearer ${token}`);

  const response = await fetch(`${baseUrl}${path}`, { ...init, headers });
  return handleResponse<T>(response);
}

async function multipartRequest<T>(
  path: string,
  formData: FormData,
  method: 'POST' = 'POST',
): Promise<T> {
  const token = getToken();
  const headers = new Headers();
  if (token) headers.set('Authorization', `Bearer ${token}`);
  // Do NOT set Content-Type; the browser sets it with a multipart boundary.

  const response = await fetch(`${baseUrl}${path}`, {
    method,
    headers,
    body: formData,
  });
  return handleResponse<T>(response);
}

export interface SubmitTaskPayload {
  phase: number;
  task_no: number;
  content: string;
  files: File[];
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

  listSubmissions: (phase: number) =>
    rawRequest<Submission[]>(`/api/submissions/${phase}`),

  submitTask: (payload: SubmitTaskPayload): Promise<Submission> => {
    const fd = new FormData();
    fd.append('phase', String(payload.phase));
    fd.append('task_no', String(payload.task_no));
    fd.append('content', payload.content);
    for (const file of payload.files) {
      fd.append('files', file, file.name);
    }
    return multipartRequest<Submission>('/api/submissions', fd);
  },

  regradeSubmission: (submissionId: string): Promise<GradingAttempt> =>
    rawRequest<GradingAttempt>(`/api/submissions/${submissionId}/regrade`, {
      method: 'POST',
    }),

  // Downloads the file body via an authenticated fetch and returns a Blob.
  // A bare <a href> cannot carry the Authorization header, so the download
  // endpoint must be reached programmatically.
  downloadFile: async (
    submissionId: string,
    fileId: string,
  ): Promise<Blob> => {
    const token = getToken();
    const headers = new Headers();
    if (token) headers.set('Authorization', `Bearer ${token}`);
    const response = await fetch(
      `${baseUrl}/api/submissions/${submissionId}/files/${fileId}`,
      { headers },
    );
    if (response.status === 401) {
      if (_onUnauthorized) _onUnauthorized();
      throw new Error('API 401: Unauthorized');
    }
    if (!response.ok) {
      throw new Error(`Download failed: ${response.status}`);
    }
    return response.blob();
  },
};
