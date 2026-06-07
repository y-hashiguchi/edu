import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return {
    ...actual,
    api: {
      ...actual.api,
      listMyNotifications: vi.fn(),
      markNotificationRead: vi.fn(),
    },
  };
});

import { api } from '@/lib/api';
import { useNotificationStore } from '@/stores/notification';

const mocked = api as unknown as Record<string, ReturnType<typeof vi.fn>>;

function makeNote(id: string, unread = true) {
  return {
    id,
    recipient_user_id: 'u1',
    sender_user_id: 'admin1',
    sender_name: '講師',
    title: `t-${id}`,
    body: 'b',
    link: null,
    read_at: unread ? null : '2026-06-06T03:00:00Z',
    created_at: '2026-06-06T02:00:00Z',
  };
}

describe('notification store', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('refresh fills items and unreadCount', async () => {
    mocked.listMyNotifications.mockResolvedValue({
      items: [makeNote('a'), makeNote('b', false)],
      unread_count: 1,
    });
    const store = useNotificationStore();
    await store.refresh();
    expect(store.items).toHaveLength(2);
    expect(store.unreadCount).toBe(1);
    expect(store.hasUnread).toBe(true);
  });

  it('refresh keeps last good state on failure', async () => {
    const store = useNotificationStore();
    store.items = [makeNote('a')];
    store.unreadCount = 1;
    mocked.listMyNotifications.mockRejectedValue(new Error('offline'));

    await store.refresh();
    // Items unchanged; error captured.
    expect(store.items).toHaveLength(1);
    expect(store.unreadCount).toBe(1);
    expect(store.error).toContain('offline');
  });

  it('startPolling is idempotent and fires refresh once immediately', async () => {
    mocked.listMyNotifications.mockResolvedValue({ items: [], unread_count: 0 });
    const store = useNotificationStore();

    const handle1 = store.startPolling();
    const handle2 = store.startPolling();
    expect(handle1).toBe(handle2);
    expect(handle1).not.toBe(0);
    // One immediate refresh, no extra calls from the second startPolling.
    expect(mocked.listMyNotifications).toHaveBeenCalledTimes(1);

    store.stopPolling();
    expect(store.pollHandle).toBe(0);
  });

  it('markRead is optimistic and rolls back on failure', async () => {
    mocked.listMyNotifications.mockResolvedValue({
      items: [makeNote('a'), makeNote('b')],
      unread_count: 2,
    });
    const store = useNotificationStore();
    await store.refresh();
    expect(store.unreadCount).toBe(2);

    // Happy path: optimistic decrement to 1, no refetch needed.
    mocked.markNotificationRead.mockResolvedValueOnce(makeNote('a', false));
    await store.markRead('a');
    expect(store.unreadCount).toBe(1);
    expect(store.items[0].read_at).not.toBeNull();
    expect(mocked.listMyNotifications).toHaveBeenCalledTimes(1);

    // Failure path: roll back via refresh, surface the error.
    mocked.markNotificationRead.mockRejectedValueOnce(new Error('boom'));
    mocked.listMyNotifications.mockResolvedValueOnce({
      items: [makeNote('a', false), makeNote('b')],
      unread_count: 1,
    });
    await expect(store.markRead('b')).rejects.toThrow('boom');
    expect(mocked.listMyNotifications).toHaveBeenCalledTimes(2);
  });
});
