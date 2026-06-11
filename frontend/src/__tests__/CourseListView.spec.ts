import { beforeEach, describe, expect, it, vi } from 'vitest';
import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { createMemoryHistory, createRouter } from 'vue-router';

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return {
    ...actual,
    api: {
      ...actual.api,
      listMyCourses: vi.fn(),
      listCourseCatalog: vi.fn(),
    },
  };
});

import { api } from '@/lib/api';
import CourseListView from '@/views/CourseListView.vue';

const mocked = api as unknown as Record<string, ReturnType<typeof vi.fn>>;

function buildRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/courses', name: 'courses', component: CourseListView },
      {
        path: '/courses/:courseSlug',
        name: 'course-home',
        component: { template: '<div>home</div>' },
      },
    ],
  });
}

describe('CourseListView (Sprint 7)', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    localStorage.removeItem('ai-tutor.activeCourse');
  });

  it('renders enrolled courses as router links', async () => {
    mocked.listMyCourses.mockResolvedValue({
      items: [
        {
          slug: 'ai-driven-dev',
          title: 'AI駆動型開発',
          description: '既存4フェーズ',
          status: 'active',
        },
      ],
    });
    mocked.listCourseCatalog.mockResolvedValue({ items: [] });
    const router = buildRouter();
    await router.push('/courses');
    const w = mount(CourseListView, { global: { plugins: [router] } });
    await flushPromises();
    expect(w.text()).toContain('AI駆動型開発');
    const links = w.findAll('a[data-test-slug]');
    expect(links).toHaveLength(1);
    expect(links[0].attributes('href')).toBe('/courses/ai-driven-dev');
  });

  it('renders the empty-state message when the learner has no courses', async () => {
    mocked.listMyCourses.mockResolvedValue({ items: [] });
    mocked.listCourseCatalog.mockResolvedValue({ items: [] });
    const router = buildRouter();
    await router.push('/courses');
    const w = mount(CourseListView, { global: { plugins: [router] } });
    await flushPromises();
    expect(w.text()).toContain('受講中のコースはありません');
  });

  it('shows the "ask admin" hint when there are un-enrolled catalog courses', async () => {
    mocked.listMyCourses.mockResolvedValue({
      items: [
        {
          slug: 'ai-driven-dev',
          title: 'AI駆動型開発',
          description: null,
          status: 'active',
        },
      ],
    });
    mocked.listCourseCatalog.mockResolvedValue({
      items: [
        {
          slug: 'ai-driven-dev',
          title: 'AI駆動型開発',
          description: null,
          sort_order: 10,
        },
        {
          slug: 'ai-era-se',
          title: 'AI時代SE育成',
          description: 'desc',
          sort_order: 20,
        },
      ],
    });
    const router = buildRouter();
    await router.push('/courses');
    const w = mount(CourseListView, { global: { plugins: [router] } });
    await flushPromises();
    expect(w.text()).toContain('追加受講は管理者へ依頼');
    // The enrolled course must NOT appear in the additional list.
    const additional = w.find('[data-test="additional-courses"]');
    expect(additional.exists()).toBe(true);
    expect(additional.text()).toContain('AI時代SE育成');
    expect(additional.text()).not.toContain('AI駆動型開発');
  });
});
