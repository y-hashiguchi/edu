import { describe, expect, it } from 'vitest';
import { mount } from '@vue/test-utils';

import CommentThread from '@/components/CommentThread.vue';

const sample = [
  {
    id: 'c1',
    author_name: '講師',
    body: 'よくできました',
    created_at: '2026-06-06T03:00:00Z',
    parent_id: null,
    // Sprint 6: LearnerCommentOut now requires is_admin_authored so
    // the UI can show the reply button without leaking author_user_id.
    is_admin_authored: true,
  },
];

describe('CommentThread', () => {
  it('renders existing comments', () => {
    const w = mount(CommentThread, { props: { comments: sample } });
    expect(w.text()).toContain('よくできました');
    expect(w.text()).toContain('講師');
  });

  it('shows empty state when no comments and no composer', () => {
    const w = mount(CommentThread, { props: { comments: [] } });
    expect(w.text()).toContain('まだコメントはありません');
  });

  it('hides the empty state when the composer is enabled', () => {
    const w = mount(CommentThread, { props: { comments: [], canPost: true } });
    expect(w.text()).not.toContain('まだコメントはありません');
    expect(w.find('textarea').exists()).toBe(true);
  });

  it('emits post on submit and clears the draft', async () => {
    const w = mount(CommentThread, {
      props: { comments: [], canPost: true },
    });
    await w.find('textarea').setValue('  hello  ');
    await w.find('button').trigger('click');
    const emitted = w.emitted('post');
    expect(emitted).toBeTruthy();
    expect(emitted![0]).toEqual(['hello']);
    expect((w.find('textarea').element as HTMLTextAreaElement).value).toBe('');
  });

  it('refuses to emit on empty body and shows an inline error', async () => {
    const w = mount(CommentThread, {
      props: { comments: [], canPost: true },
    });
    await w.find('button').trigger('click');
    expect(w.emitted('post')).toBeUndefined();
    expect(w.text()).toContain('本文を入力してください');
  });
});

describe('CommentThread (Sprint 6 ツリー)', () => {
  // Sprint 6 fix: admin nodes carry is_admin_authored=true (matches the
  // new LearnerCommentOut flag); the legacy field-presence fallback also
  // works because they still carry author_user_id (AdminCommentOut shape).
  // The learner reply uses the LearnerCommentOut shape with the flag set
  // to false, exercising the new flag-based code path.
  const treeSample = [
    {
      id: 'a',
      submission_id: 's1',
      author_user_id: 'admin1',
      author_name: '講師A',
      body: 'trunk',
      created_at: '2026-06-09T00:00:00Z',
      updated_at: '2026-06-09T00:00:00Z',
      parent_id: null,
      is_admin_authored: true,
    },
    {
      id: 'b',
      author_name: '学習者',
      body: 'reply 1',
      created_at: '2026-06-09T00:05:00Z',
      parent_id: 'a',
      is_admin_authored: false,
    },
    {
      id: 'c',
      submission_id: 's1',
      author_user_id: 'admin1',
      author_name: '講師A',
      body: 'reply to reply',
      created_at: '2026-06-09T00:10:00Z',
      updated_at: '2026-06-09T00:10:00Z',
      parent_id: 'b',
      is_admin_authored: true,
    },
  ];

  it('renders 1 trunk and nests child replies', () => {
    const w = mount(CommentThread, {
      props: { comments: treeSample, canReply: false, canPost: false },
    });
    expect(w.text()).toContain('trunk');
    expect(w.text()).toContain('reply 1');
    expect(w.text()).toContain('reply to reply');
  });

  it('shows reply button on admin-author comments when canReply=true', () => {
    const w = mount(CommentThread, {
      props: { comments: treeSample, canReply: true, canPost: false },
    });
    const replyBtns = w.findAll('button.reply');
    expect(replyBtns.length).toBeGreaterThan(0);
  });

  it('emits reply event with parent_id when reply form is submitted', async () => {
    const w = mount(CommentThread, {
      props: { comments: treeSample, canReply: true, canPost: false },
    });
    await w.find('button.reply').trigger('click');
    await w.find('textarea.reply-body').setValue('my reply');
    await w.find('button.reply-submit').trigger('click');
    const events = w.emitted('reply') ?? [];
    expect(events.length).toBe(1);
    expect(events[0]).toEqual([{ parentId: 'a', body: 'my reply' }]);
  });

  it('hides reply button on learner-authored comments (is_admin_authored=false)', () => {
    const w = mount(CommentThread, {
      props: { comments: treeSample, canReply: true, canPost: false },
    });
    // learner reply ('b') has is_admin_authored=false → its node should
    // NOT show a reply button. Only the two admin nodes do.
    const replyBtns = w.findAll('button.reply');
    expect(replyBtns.length).toBe(2);
  });
});
