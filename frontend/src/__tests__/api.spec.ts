import { afterEach, describe, expect, it, vi } from 'vitest';

import { rawRequest } from '@/lib/api';

describe('rawRequest', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('returns undefined for 204 responses without parsing JSON', async () => {
    const json = vi.spyOn(Response.prototype, 'json');
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(null, {
          status: 204,
          statusText: 'No Content',
        }),
      ),
    );

    const result = await rawRequest<void>('/api/admin/curriculum/courses/tmp', {
      method: 'DELETE',
    });

    expect(result).toBeUndefined();
    expect(json).not.toHaveBeenCalled();
  });
});
