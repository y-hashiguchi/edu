import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { api, registerTokenGetter } from '@/lib/api';

describe('api.downloadFile', () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    registerTokenGetter(() => 'test-token');
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    registerTokenGetter(() => null);
    vi.restoreAllMocks();
  });

  it('sends Authorization header and returns the response blob', async () => {
    const expected = new Blob([new Uint8Array([1, 2, 3])], {
      type: 'image/png',
    });
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      blob: () => Promise.resolve(expected),
    } as unknown as Response);
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const blob = await api.downloadFile('sub-1', 'file-1');

    expect(blob).toBe(expected);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [, init] = fetchMock.mock.calls[0];
    const headers = (init as RequestInit).headers as Headers;
    expect(headers.get('Authorization')).toBe('Bearer test-token');
  });

  it('throws on non-OK response', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      blob: () => Promise.resolve(new Blob()),
    } as unknown as Response) as unknown as typeof fetch;

    await expect(api.downloadFile('sub-1', 'file-1')).rejects.toThrow(
      /Download failed: 403/,
    );
  });
});
