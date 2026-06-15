import { describe, expect, it, vi, beforeEach } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';

import { useAdminStore } from '@/stores/admin';

vi.mock('@/lib/api', () => ({
  api: {
    adminScheduleBroadcast: vi.fn(),
    adminListScheduledBroadcasts: vi.fn(),
    adminCancelScheduledBroadcast: vi.fn(),
  },
}));

import { api } from '@/lib/api';

describe('admin scheduled broadcast store', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it('scheduleBroadcast refreshes scheduledBroadcasts from API', async () => {
    const row = {
      id: 'sb-1',
      course_slug: 'ai-driven-dev',
      title: 'T',
      body: 'B',
      link: null,
      scheduled_at: '2026-06-12T00:15:00Z',
      status: 'pending',
      sent_at: null,
      sent_count: null,
      skipped_inbox_full: null,
      skipped_admin: null,
      failure_reason: null,
      created_at: '2026-06-11T00:00:00Z',
    };
    vi.mocked(api.adminScheduleBroadcast).mockResolvedValue(row);
    vi.mocked(api.adminListScheduledBroadcasts).mockResolvedValue({ items: [row] });

    const store = useAdminStore();
    await store.scheduleBroadcast({
      course_slug: 'ai-driven-dev',
      title: 'T',
      body: 'B',
      link: null,
      scheduled_at: row.scheduled_at,
    });

    expect(api.adminListScheduledBroadcasts).toHaveBeenCalledWith('pending');
    expect(store.scheduledBroadcasts[0].id).toBe('sb-1');
  });

  it('fetchScheduledBroadcasts replaces list', async () => {
    vi.mocked(api.adminListScheduledBroadcasts).mockResolvedValue({
      items: [
        {
          id: 'sb-2',
          course_slug: 'ai-era-se',
          title: 'X',
          body: 'Y',
          link: null,
          scheduled_at: '2026-06-13T00:00:00Z',
          status: 'pending',
          sent_at: null,
          sent_count: null,
          skipped_inbox_full: null,
          skipped_admin: null,
          failure_reason: null,
          created_at: '2026-06-11T00:00:00Z',
        },
      ],
    });

    const store = useAdminStore();
    await store.fetchScheduledBroadcasts('pending');
    expect(store.scheduledBroadcasts).toHaveLength(1);
    expect(store.scheduledBroadcasts[0].course_slug).toBe('ai-era-se');
  });
});
