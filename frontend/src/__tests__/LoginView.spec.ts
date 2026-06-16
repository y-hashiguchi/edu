import { beforeEach, describe, expect, it, vi } from 'vitest';
import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { createMemoryHistory, createRouter, type Router } from 'vue-router';

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return {
    ...actual,
    api: {
      ...actual.api,
      listCourseCatalog: vi.fn(),
      listMyCourses: vi.fn(),
    },
    rawRequest: vi.fn(),
  };
});

import { api, rawRequest } from '@/lib/api';
import LoginView from '@/views/LoginView.vue';

const mockedApi = api as unknown as Record<string, ReturnType<typeof vi.fn>>;
const mockedRawRequest = rawRequest as unknown as ReturnType<typeof vi.fn>;

const CATALOG = {
  items: [
    {
      slug: 'ai-driven-dev',
      title: 'AI駆動型開発',
      description: 'desc',
      sort_order: 10,
    },
    {
      slug: 'ai-era-se',
      title: 'AI時代SE育成',
      description: 'desc2',
      sort_order: 20,
    },
  ],
};

function buildRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/login', name: 'login', component: LoginView },
      {
        path: '/courses',
        name: 'courses',
        component: { template: '<div>list</div>' },
      },
      {
        path: '/courses/:courseSlug',
        name: 'course-home',
        component: { template: '<div>home</div>' },
      },
    ],
  });
}

describe('LoginView (Sprint 7 course selection)', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    localStorage.removeItem('ai-tutor.activeCourse');
    mockedApi.listCourseCatalog.mockResolvedValue(CATALOG);
  });

  it('shows the course <select> only in register mode', async () => {
    const router = buildRouter();
    await router.push('/login');
    const w = mount(LoginView, { global: { plugins: [router] } });
    await flushPromises();
    // Default tab is login → no selector
    expect(w.find('[data-test="course-select"]').exists()).toBe(false);
    // Flip to register tab
    const tabs = w.findAll('[role="tab"]');
    await tabs[1].trigger('click');
    await flushPromises();
    expect(w.find('[data-test="course-select"]').exists()).toBe(true);
  });

  it('populates the course select with sorted catalog options', async () => {
    const router = buildRouter();
    await router.push('/login');
    const w = mount(LoginView, { global: { plugins: [router] } });
    await flushPromises();
    const tabs = w.findAll('[role="tab"]');
    await tabs[1].trigger('click');
    await flushPromises();
    const sel = w.find('[data-test="course-select"]');
    const options = sel.findAll('option');
    // First option is the disabled placeholder.
    expect(options[0].attributes('disabled')).toBeDefined();
    expect(options[1].attributes('value')).toBe('ai-driven-dev');
    expect(options[2].attributes('value')).toBe('ai-era-se');
  });

  it('disables the submit button until a course is selected in register mode', async () => {
    const router = buildRouter();
    await router.push('/login');
    const w = mount(LoginView, { global: { plugins: [router] } });
    await flushPromises();
    const tabs = w.findAll('[role="tab"]');
    await tabs[1].trigger('click');
    await flushPromises();
    const submit = w.find('button[type="submit"]');
    expect(submit.attributes('disabled')).toBeDefined();
    // Pick a course
    await w.find('[data-test="course-select"]').setValue('ai-era-se');
    await flushPromises();
    expect(submit.attributes('disabled')).toBeUndefined();
  });

  it('shows selected course description in register mode', async () => {
    const router = buildRouter();
    await router.push('/login');
    const w = mount(LoginView, { global: { plugins: [router] } });
    await flushPromises();
    const tabs = w.findAll('[role="tab"]');
    await tabs[1].trigger('click');
    await flushPromises();
    await w.find('[data-test="course-select"]').setValue('ai-driven-dev');
    await flushPromises();
    const desc = w.find('[data-test="selected-course-description"]');
    expect(desc.exists()).toBe(true);
    expect(desc.text()).toBe('desc');
  });

  it('routes to /courses/{slug} on login when the user has exactly one course', async () => {
    mockedRawRequest.mockImplementation(async (path: string) => {
      if (path === '/api/auth/login') {
        return { access_token: 't', token_type: 'bearer' };
      }
      if (path === '/api/auth/me') {
        return {
          id: 'u1', email: 'a@e.com', name: 'A',
          created_at: '2026-06-09T00:00:00Z', is_admin: false,
        };
      }
      throw new Error(`unexpected ${path}`);
    });
    mockedApi.listMyCourses.mockResolvedValue({
      items: [
        {
          slug: 'ai-era-se',
          title: 'AI時代SE育成',
          description: null,
          status: 'active',
        },
      ],
    });
    const router = buildRouter();
    const pushSpy = vi.spyOn(router, 'push');
    await router.push('/login');
    const w = mount(LoginView, { global: { plugins: [router] } });
    await flushPromises();
    await w.find('input[type="email"]').setValue('a@e.com');
    await w.find('input[type="password"]').setValue('password1');
    await w.find('form').trigger('submit.prevent');
    await flushPromises();
    expect(pushSpy).toHaveBeenCalledWith('/courses/ai-era-se');
  });

  it('routes to /courses when the user has multiple courses', async () => {
    mockedRawRequest.mockImplementation(async (path: string) => {
      if (path === '/api/auth/login') {
        return { access_token: 't', token_type: 'bearer' };
      }
      if (path === '/api/auth/me') {
        return {
          id: 'u1', email: 'a@e.com', name: 'A',
          created_at: '2026-06-09T00:00:00Z', is_admin: false,
        };
      }
      throw new Error(`unexpected ${path}`);
    });
    mockedApi.listMyCourses.mockResolvedValue({
      items: [
        { slug: 'a', title: 'A', description: null, status: 'active' },
        { slug: 'b', title: 'B', description: null, status: 'active' },
      ],
    });
    const router = buildRouter();
    const pushSpy = vi.spyOn(router, 'push');
    await router.push('/login');
    const w = mount(LoginView, { global: { plugins: [router] } });
    await flushPromises();
    await w.find('input[type="email"]').setValue('a@e.com');
    await w.find('input[type="password"]').setValue('password1');
    await w.find('form').trigger('submit.prevent');
    await flushPromises();
    expect(pushSpy).toHaveBeenCalledWith('/courses');
  });
});
