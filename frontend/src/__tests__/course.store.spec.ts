import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return {
    ...actual,
    api: {
      ...actual.api,
      listCourseCatalog: vi.fn(),
      listMyCourses: vi.fn(),
    },
  };
});

import { api } from '@/lib/api';
import { useCourseStore } from '@/stores/course';

const mocked = api as unknown as Record<string, ReturnType<typeof vi.fn>>;

describe('course store (Sprint 7)', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    localStorage.removeItem('ai-tutor.activeCourse');
  });

  it('setActiveCourse persists the slug to localStorage', () => {
    const store = useCourseStore();
    store.setActiveCourse('ai-era-se');
    expect(store.activeSlug).toBe('ai-era-se');
    expect(localStorage.getItem('ai-tutor.activeCourse')).toBe('ai-era-se');
  });

  it('hydrateActiveFromStorage restores the slug from localStorage', () => {
    localStorage.setItem('ai-tutor.activeCourse', 'ai-driven-dev');
    const store = useCourseStore();
    expect(store.activeSlug).toBeNull();
    store.hydrateActiveFromStorage();
    expect(store.activeSlug).toBe('ai-driven-dev');
  });

  it('fetchMyCourses defaults the active slug to the first course when none chosen', async () => {
    mocked.listMyCourses.mockResolvedValue({
      items: [
        {
          slug: 'ai-driven-dev',
          title: 'AI駆動型開発',
          description: null,
          status: 'active',
        },
        {
          slug: 'ai-era-se',
          title: 'AI時代SE育成',
          description: null,
          status: 'active',
        },
      ],
    });
    const store = useCourseStore();
    expect(store.activeSlug).toBeNull();
    await store.fetchMyCourses();
    expect(store.myCourses).toHaveLength(2);
    expect(store.loaded).toBe(true);
    // First in the list becomes the default active slug.
    expect(store.activeSlug).toBe('ai-driven-dev');
  });

  it('fetchMyCourses leaves the active slug alone when one is already set', async () => {
    mocked.listMyCourses.mockResolvedValue({
      items: [
        { slug: 'a', title: 'A', description: null, status: 'active' },
        { slug: 'b', title: 'B', description: null, status: 'active' },
      ],
    });
    const store = useCourseStore();
    store.setActiveCourse('b');
    await store.fetchMyCourses();
    // Should not be overwritten by the first-item heuristic.
    expect(store.activeSlug).toBe('b');
  });

  it('fetchCatalog populates the catalog sorted by sort_order', async () => {
    mocked.listCourseCatalog.mockResolvedValue({
      items: [
        {
          slug: 'b',
          title: 'B',
          description: null,
          sort_order: 20,
        },
        {
          slug: 'a',
          title: 'A',
          description: null,
          sort_order: 10,
        },
      ],
    });
    const store = useCourseStore();
    await store.fetchCatalog();
    expect(store.catalog.map((c) => c.slug)).toEqual(['a', 'b']);
  });

  it('isEnrolled returns true only for courses in myCourses', async () => {
    mocked.listMyCourses.mockResolvedValue({
      items: [
        { slug: 'ai-driven-dev', title: 'A', description: null, status: 'active' },
      ],
    });
    const store = useCourseStore();
    await store.fetchMyCourses();
    expect(store.isEnrolled('ai-driven-dev')).toBe(true);
    expect(store.isEnrolled('ai-era-se')).toBe(false);
  });

  it('reset clears state and localStorage', () => {
    const store = useCourseStore();
    store.setActiveCourse('ai-era-se');
    store.reset();
    expect(store.activeSlug).toBeNull();
    expect(store.myCourses).toEqual([]);
    expect(store.catalog).toEqual([]);
    expect(store.loaded).toBe(false);
    expect(localStorage.getItem('ai-tutor.activeCourse')).toBeNull();
  });
});
