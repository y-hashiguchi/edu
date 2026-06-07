import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { createMemoryHistory, createRouter } from 'vue-router';

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
import NotificationCenter from '@/components/NotificationCenter.vue';
import { useNotificationStore } from '@/stores/notification';

const mocked = api as unknown as Record<string, ReturnType<typeof vi.fn>>;

function buildRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'home', component: { template: '<div>home</div>' } },
      {
        path: '/phases/:phase',
        name: 'phase',
        component: { template: '<div>phase</div>' },
      },
    ],
  });
}

function makeNote(id: string, link: string | null = null, unread = true) {
  return {
    id,
    recipient_user_id: 'u1',
    sender_user_id: 'admin1',
    sender_name: '講師',
    title: `t-${id}`,
    body: 'b',
    link,
    read_at: unread ? null : '2026-06-06T03:00:00Z',
    created_at: '2026-06-06T02:00:00Z',
  };
}

describe('NotificationCenter', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders unread badge from the store', async () => {
    mocked.listMyNotifications.mockResolvedValue({
      items: [makeNote('a'), makeNote('b', null, false)],
      unread_count: 1,
    });
    const router = buildRouter();
    const w = mount(NotificationCenter, {
      global: { plugins: [router] },
    });
    // startPolling fires refresh once on mount.
    await vi.runOnlyPendingTimersAsync();
    await Promise.resolve();
    expect(w.find('.badge').text()).toBe('1');
  });

  it('toggles the panel open on click and renders items', async () => {
    mocked.listMyNotifications.mockResolvedValue({
      items: [makeNote('a')],
      unread_count: 1,
    });
    const router = buildRouter();
    const w = mount(NotificationCenter, {
      global: { plugins: [router] },
    });
    await vi.runOnlyPendingTimersAsync();
    await Promise.resolve();

    expect(w.find('.panel').exists()).toBe(false);
    await w.find('.bell').trigger('click');
    expect(w.find('.panel').exists()).toBe(true);
    expect(w.text()).toContain('t-a');
  });

  it('marks an item read and navigates when the link is internal', async () => {
    mocked.listMyNotifications.mockResolvedValue({
      items: [makeNote('a', '/phases/2')],
      unread_count: 1,
    });
    mocked.markNotificationRead.mockResolvedValue(
      makeNote('a', '/phases/2', false),
    );
    const router = buildRouter();
    await router.push('/');
    const w = mount(NotificationCenter, {
      global: { plugins: [router] },
    });
    await vi.runOnlyPendingTimersAsync();
    await Promise.resolve();

    await w.find('.bell').trigger('click');
    await w.find('.item').trigger('click');
    // The click handler is async and chains through store.markRead +
    // router.push — flush the microtask queue so both have settled
    // before we assert.
    await flushPromises();

    expect(mocked.markNotificationRead).toHaveBeenCalledWith('a');
    const store = useNotificationStore();
    expect(store.unreadCount).toBe(0);
    expect(router.currentRoute.value.path).toBe('/phases/2');
  });

  it('cleans up polling on unmount (idempotent)', async () => {
    mocked.listMyNotifications.mockResolvedValue({ items: [], unread_count: 0 });
    const router = buildRouter();
    const w = mount(NotificationCenter, {
      global: { plugins: [router] },
    });
    await vi.runOnlyPendingTimersAsync();
    const store = useNotificationStore();
    expect(store.pollHandle).not.toBe(0);
    w.unmount();
    expect(store.pollHandle).toBe(0);
  });
});
