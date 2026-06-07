import { describe, expect, it } from 'vitest';
import { mount } from '@vue/test-utils';

import CommentThread from '@/components/CommentThread.vue';

const sample = [
  {
    id: 'c1',
    author_name: '講師',
    body: 'よくできました',
    created_at: '2026-06-06T03:00:00Z',
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
