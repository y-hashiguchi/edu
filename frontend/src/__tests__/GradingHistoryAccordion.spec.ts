import { describe, expect, it } from 'vitest';
import { mount } from '@vue/test-utils';
import GradingHistoryAccordion from '@/components/GradingHistoryAccordion.vue';
import type { GradingAttempt } from '@/types/curriculum';

function attempt(overrides: Partial<GradingAttempt> = {}): GradingAttempt {
  return {
    id: '00000000-0000-0000-0000-000000000000',
    status: 'graded',
    score: 80,
    feedback: 'good',
    error_message: null,
    model_name: 'claude',
    created_at: '2026-06-04T00:00:00Z',
    ...overrides,
  };
}

describe('GradingHistoryAccordion', () => {
  it('renders count and toggles entries', async () => {
    const wrapper = mount(GradingHistoryAccordion, {
      props: { history: [attempt(), attempt({ id: '1', score: 70 })] },
    });
    expect(wrapper.text()).toContain('採点履歴 (2)');
    expect(wrapper.find('.entries').exists()).toBe(false);
    await wrapper.find('.toggle').trigger('click');
    expect(wrapper.find('.entries').exists()).toBe(true);
  });

  it('renders failed attempts distinctly', async () => {
    const wrapper = mount(GradingHistoryAccordion, {
      props: {
        history: [
          attempt({
            status: 'failed',
            score: null,
            feedback: null,
            error_message: 'timeout',
          }),
        ],
      },
    });
    await wrapper.find('.toggle').trigger('click');
    expect(wrapper.text()).toContain('採点失敗');
    expect(wrapper.text()).toContain('timeout');
  });

  it('shows empty message when no history', async () => {
    const wrapper = mount(GradingHistoryAccordion, { props: { history: [] } });
    await wrapper.find('.toggle').trigger('click');
    expect(wrapper.text()).toContain('採点履歴はまだありません');
  });
});
