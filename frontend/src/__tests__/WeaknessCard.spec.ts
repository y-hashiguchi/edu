import { describe, expect, it } from 'vitest';
import { mount } from '@vue/test-utils';
import WeaknessCard from '@/components/WeaknessCard.vue';

describe('WeaknessCard', () => {
  it('renders top 3 tags with scores', () => {
    const w = mount(WeaknessCard, {
      props: {
        data: {
          has_enough_data: true,
          top_weaknesses: [
            { tag: 'AI協調', average_score: 60, submission_count: 3 },
            { tag: 'API基礎', average_score: 65, submission_count: 2 },
            { tag: 'テスト', average_score: 70, submission_count: 2 },
          ],
        },
      },
    });
    expect(w.text()).toContain('AI協調');
    expect(w.text()).toContain('60');
    expect(w.findAll('li')).toHaveLength(3);
  });

  it('shows cold-start placeholder when has_enough_data is false', () => {
    const w = mount(WeaknessCard, {
      props: { data: { has_enough_data: false, top_weaknesses: [] } },
    });
    expect(w.text()).toContain('提出 3 件以上');
    expect(w.find('li').exists()).toBe(false);
  });

  it('uses neutral heading wording (not weakness)', () => {
    const w = mount(WeaknessCard, {
      props: { data: { has_enough_data: true, top_weaknesses: [] } },
    });
    expect(w.text()).toContain('もう一押し');
    expect(w.text()).not.toContain('弱点');
  });
});
