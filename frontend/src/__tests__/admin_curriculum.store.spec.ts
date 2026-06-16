import { describe, expect, it, vi, beforeEach } from 'vitest';
import { setActivePinia, createPinia } from 'pinia';

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return {
    ...actual,
    api: {
      ...actual.api,
      adminCurriculumList: vi.fn(),
      adminCurriculumDetail: vi.fn(),
      adminPutCurriculumPhase: vi.fn(),
      adminPutCurriculumTask: vi.fn(),
      adminPublishCurriculum: vi.fn(),
      adminDiscardCurriculumDrafts: vi.fn(),
      adminAddCurriculumTask: vi.fn(),
      adminDeleteCurriculumTask: vi.fn(),
      adminMoveCurriculumTask: vi.fn(),
      adminMoveCurriculumPhase: vi.fn(),
      adminCreateCurriculumCourse: vi.fn(),
      adminDeleteCurriculumCourse: vi.fn(),
    },
  };
});

import { api } from '@/lib/api';
import { useAdminCurriculumStore } from '@/stores/admin_curriculum';

describe('admin_curriculum store', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it('fetchList populates state', async () => {
    (api.adminCurriculumList as unknown as ReturnType<typeof vi.fn>)
      .mockResolvedValue({ items: [{ slug: 'a', title: 'A', pending_draft_count: 2 }] });
    const store = useAdminCurriculumStore();
    await store.fetchList();
    expect(store.list).toHaveLength(1);
    expect(store.list[0].pending_draft_count).toBe(2);
  });

  it('putTask debounce sends only the last value within window', async () => {
    (api.adminPutCurriculumTask as unknown as ReturnType<typeof vi.fn>)
      .mockResolvedValue({} as never);
    const store = useAdminCurriculumStore();
    vi.useFakeTimers();
    try {
      store.putTask('ai-driven-dev', 1, 1, { title: 'a' });
      store.putTask('ai-driven-dev', 1, 1, { title: 'ab' });
      store.putTask('ai-driven-dev', 1, 1, { title: 'abc' });
      await vi.advanceTimersByTimeAsync(600);
      expect(api.adminPutCurriculumTask).toHaveBeenCalledTimes(1);
      expect(api.adminPutCurriculumTask).toHaveBeenCalledWith(
        'ai-driven-dev', 1, 1, { title: 'abc' },
      );
    } finally {
      vi.useRealTimers();
    }
  });

  it('publish then refetches detail', async () => {
    (api.adminPublishCurriculum as unknown as ReturnType<typeof vi.fn>)
      .mockResolvedValue({
        slug: 'a', published_phase_count: 1, published_task_count: 2,
        published_at: '2026-06-13T00:00:00Z',
      });
    (api.adminCurriculumDetail as unknown as ReturnType<typeof vi.fn>)
      .mockResolvedValue({ slug: 'a', title: 'A', phases: [] });
    const store = useAdminCurriculumStore();
    await store.publish('a');
    expect(api.adminCurriculumDetail).toHaveBeenCalledWith('a');
    expect(store.detail?.slug).toBe('a');
  });

  it('addTask refetches detail', async () => {
    (api.adminAddCurriculumTask as unknown as ReturnType<typeof vi.fn>)
      .mockResolvedValue({ task_no: 4 } as never);
    (api.adminCurriculumDetail as unknown as ReturnType<typeof vi.fn>)
      .mockResolvedValue({ slug: 'a', title: 'A', phases: [] });
    const store = useAdminCurriculumStore();
    await store.addTask('a', 1);
    expect(api.adminAddCurriculumTask).toHaveBeenCalledWith('a', 1);
    expect(api.adminCurriculumDetail).toHaveBeenCalledWith('a');
  });

  it('createCourse refetches list', async () => {
    (api.adminCreateCurriculumCourse as unknown as ReturnType<typeof vi.fn>)
      .mockResolvedValue({
        slug: 'new', title: 'New', description: null,
        sort_order: 2, phase_count: 4, created_at: '2026-06-14T00:00:00Z',
      });
    (api.adminCurriculumList as unknown as ReturnType<typeof vi.fn>)
      .mockResolvedValue({ items: [] });
    const store = useAdminCurriculumStore();
    await store.createCourse({ slug: 'new', title: 'New' });
    expect(api.adminCreateCurriculumCourse).toHaveBeenCalledWith({
      slug: 'new', title: 'New',
    });
    expect(api.adminCurriculumList).toHaveBeenCalled();
  });

  it('deleteCourse refetches list', async () => {
    (api.adminDeleteCurriculumCourse as unknown as ReturnType<typeof vi.fn>)
      .mockResolvedValue(undefined);
    (api.adminCurriculumList as unknown as ReturnType<typeof vi.fn>)
      .mockResolvedValue({ items: [] });
    const store = useAdminCurriculumStore();
    await store.deleteCourse('tmp');
    expect(api.adminDeleteCurriculumCourse).toHaveBeenCalledWith('tmp');
    expect(api.adminCurriculumList).toHaveBeenCalled();
  });

  it('movePhase refetches detail', async () => {
    (api.adminMoveCurriculumPhase as unknown as ReturnType<typeof vi.fn>)
      .mockResolvedValue(undefined);
    (api.adminCurriculumDetail as unknown as ReturnType<typeof vi.fn>)
      .mockResolvedValue({ slug: 'a', title: 'A', phases: [] });
    const store = useAdminCurriculumStore();
    await store.movePhase('a', 2, 1);
    expect(api.adminMoveCurriculumPhase).toHaveBeenCalledWith('a', 2, {
      to_phase_no: 1,
    });
    expect(api.adminCurriculumDetail).toHaveBeenCalledWith('a');
  });
});
