import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return {
    ...actual,
    api: {
      ...actual.api,
      adminListUsers: vi.fn(),
      adminGetUser: vi.fn(),
      adminListSubmissions: vi.fn(),
      adminGetSubmission: vi.fn(),
      adminPostComment: vi.fn(),
      adminSendNotification: vi.fn(),
      adminListSentNotifications: vi.fn(),
      getAdminUserDashboard: vi.fn(),
    },
  };
});

import { api } from '@/lib/api';
import { useAdminStore } from '@/stores/admin';

const mocked = api as unknown as Record<string, ReturnType<typeof vi.fn>>;

function makeUserListPayload() {
  return {
    items: [
      {
        id: 'u1', email: 'a@e.com', name: 'A',
        created_at: '2026-06-06T00:00:00Z',
        is_admin: false, completed_phases: 1, in_progress_phases: 1,
      },
    ],
    total: 1, limit: 50, offset: 0,
  };
}

function makeSubmissionDetailPayload() {
  return {
    id: 's1', user_id: 'u1', user_email: 'a@e.com', user_name: 'A',
    phase: 1, task_no: 1, content: 'essay',
    score: 80, ai_feedback: null,
    submitted_at: '2026-06-06T00:00:00Z', graded_at: null,
    files: [], grading_history: [], comments: [],
  };
}

describe('admin store', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it('fetchUsers fills state and clears error', async () => {
    mocked.adminListUsers.mockResolvedValue(makeUserListPayload());
    const store = useAdminStore();
    await store.fetchUsers();
    expect(store.users).toHaveLength(1);
    expect(store.usersTotal).toBe(1);
    expect(store.loading).toBe(false);
    expect(store.error).toBeNull();
  });

  it('fetchUsers captures the error message on failure', async () => {
    mocked.adminListUsers.mockRejectedValue(new Error('500'));
    const store = useAdminStore();
    await store.fetchUsers();
    expect(store.error).toContain('500');
    expect(store.loading).toBe(false);
  });

  it('postComment appends to selectedSubmission.comments without refetch', async () => {
    const detail = makeSubmissionDetailPayload();
    mocked.adminGetSubmission.mockResolvedValue(detail);
    const newComment = {
      id: 'c1', submission_id: 's1', author_user_id: 'admin1',
      author_name: '講師', body: 'よくできました',
      created_at: '2026-06-06T01:00:00Z', updated_at: '2026-06-06T01:00:00Z',
    };
    mocked.adminPostComment.mockResolvedValue(newComment);

    const store = useAdminStore();
    await store.fetchSubmissionDetail('s1');
    expect(store.selectedSubmission?.comments).toEqual([]);

    await store.postComment('s1', 'よくできました');
    expect(store.selectedSubmission?.comments).toEqual([newComment]);
    // The store must not refetch — that would defeat the optimistic path.
    expect(mocked.adminGetSubmission).toHaveBeenCalledTimes(1);
  });

  it('sendNotification prepends to sentNotifications', async () => {
    mocked.adminSendNotification.mockResolvedValue({
      id: 'n1', recipient_user_id: 'u1', sender_user_id: 'admin1',
      sender_name: '講師', title: 't', body: 'b', link: null,
      read_at: null, created_at: '2026-06-06T02:00:00Z',
    });

    const store = useAdminStore();
    store.sentNotifications = [
      {
        id: 'n0', recipient_user_id: 'u1', sender_user_id: 'admin1',
        sender_name: '講師', title: 'old', body: 'b', link: null,
        read_at: null, created_at: '2026-06-06T00:00:00Z',
      },
    ];

    await store.sendNotification({
      recipient_user_id: 'u1', title: 't', body: 'b', link: null,
    });
    expect(store.sentNotifications.map((n) => n.id)).toEqual(['n1', 'n0']);
  });

  it('fetchUserDashboard returns null on api failure (Sprint 6)', async () => {
    mocked.getAdminUserDashboard.mockRejectedValue(new Error('boom'));
    const store = useAdminStore();
    const out = await store.fetchUserDashboard('u1', 'ai-driven-dev');
    expect(out).toBeNull();
  });
});
