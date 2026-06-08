import { describe, expect, it } from 'vitest';
import { mount } from '@vue/test-utils';
import RecommendationsCard from '@/components/RecommendationsCard.vue';

const ITEM = {
  phase: 2, task_no: 1, title: '二分探索木の実装',
  skill_tags: ['AI協調', 'API基礎'], match_tag: 'AI協調', rag_score: 0.8,
};

describe('RecommendationsCard', () => {
  it('renders each recommendation with title and match_tag', () => {
    const w = mount(RecommendationsCard, {
      props: { items: [ITEM] },
    });
    expect(w.text()).toContain('二分探索木');
    expect(w.text()).toContain('AI協調');
  });

  it('emits select with phase/task_no on click', async () => {
    const w = mount(RecommendationsCard, { props: { items: [ITEM] } });
    await w.find('button').trigger('click');
    const events = w.emitted('select') ?? [];
    expect(events[0]).toEqual([{ phase: 2, task_no: 1 }]);
  });

  it('shows phase 1 CTA when items is empty', () => {
    const w = mount(RecommendationsCard, { props: { items: [] } });
    expect(w.text()).toContain('Phase 1');
  });
});
