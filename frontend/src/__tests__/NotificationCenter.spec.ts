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
      {
        path: '/admin/users',
        name: 'admin-users',
        component: { template: '<div>admin</div>' },
        meta: { requiresAdmin: true },
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

  it('does not render dangerous link schemes as href', async () => {
    // HIGH-1 defence in depth: even if a notification with a malicious
    // link survives the backend validator (e.g. a stored record from
    // before the validator was added), the component must refuse to
    // render it as a clickable href.
    mocked.listMyNotifications.mockResolvedValue({
      items: [
        makeNote('js', 'javascript:alert(1)'),
        makeNote('data', 'data:text/html,<script>1</script>'),
        makeNote('vb', 'vbscript:msgbox(1)'),
      ],
      unread_count: 3,
    });
    const router = buildRouter();
    const w = mount(NotificationCenter, {
      global: { plugins: [router] },
    });
    await vi.runOnlyPendingTimersAsync();
    await Promise.resolve();
    await w.find('.bell').trigger('click');

    const anchors = w.findAll('a.item');
    expect(anchors).toHaveLength(0);
    // The items still render — they just become inert <button>s with
    // no href. Click does nothing dangerous.
    const buttons = w.findAll('button.item');
    expect(buttons).toHaveLength(3);
    for (const b of buttons) {
      expect(b.attributes('href')).toBeUndefined();
    }
  });

  it('renders safe external https URLs as anchors with noopener', async () => {
    mocked.listMyNotifications.mockResolvedValue({
      items: [makeNote('ok', 'https://example.com/help')],
      unread_count: 1,
    });
    const router = buildRouter();
    const w = mount(NotificationCenter, {
      global: { plugins: [router] },
    });
    await vi.runOnlyPendingTimersAsync();
    await Promise.resolve();
    await w.find('.bell').trigger('click');

    const a = w.find('a.item');
    expect(a.exists()).toBe(true);
    expect(a.attributes('href')).toBe('https://example.com/help');
    expect(a.attributes('target')).toBe('_blank');
    expect(a.attributes('rel')).toBe('noopener noreferrer');
  });

  it('does not navigate to admin-only routes via internal link', async () => {
    // MED-1 (sprint-4 security follow-up): an admin could craft a
    // notification with `link="/admin/users"`. Without this guard the
    // learner would flash the admin layout for a frame before
    // attachAdminGuard kicked them back to home. The component must
    // refuse to push admin routes outright.
    mocked.listMyNotifications.mockResolvedValue({
      items: [makeNote('a', '/admin/users')],
      unread_count: 1,
    });
    mocked.markNotificationRead.mockResolvedValue(
      makeNote('a', '/admin/users', false),
    );
    const router = buildRouter();
    await router.push('/');
    const pushSpy = vi.spyOn(router, 'push');
    const w = mount(NotificationCenter, {
      global: { plugins: [router] },
    });
    await vi.runOnlyPendingTimersAsync();
    await Promise.resolve();

    await w.find('.bell').trigger('click');
    await w.find('.item').trigger('click');
    await flushPromises();

    // mark-read still fires — the learner sees a read receipt.
    expect(mocked.markNotificationRead).toHaveBeenCalledWith('a');
    // ...but the router never sees the admin URL.
    expect(pushSpy).not.toHaveBeenCalled();
    expect(router.currentRoute.value.path).toBe('/');
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
