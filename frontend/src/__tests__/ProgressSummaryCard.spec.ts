import { describe, expect, it } from 'vitest';
import { mount } from '@vue/test-utils';
import ProgressSummaryCard from '@/components/ProgressSummaryCard.vue';

describe('ProgressSummaryCard', () => {
  it('shows completed / total', () => {
    const w = mount(ProgressSummaryCard, {
      props: {
        data: {
          completed_tasks: 5, total_tasks: 12,
          submission_count: 5, average_score: 70,
        },
      },
    });
    expect(w.text()).toContain('5 / 12');
    expect(w.text()).toContain('70');
  });

  it('shows em dash when average is null (cold start)', () => {
    const w = mount(ProgressSummaryCard, {
      props: {
        data: {
          completed_tasks: 1, total_tasks: 12,
          submission_count: 1, average_score: null,
        },
      },
    });
    expect(w.text()).toContain('—');
    expect(w.text()).toContain('1 / 12');
  });

  it('shows hint when below threshold', () => {
    const w = mount(ProgressSummaryCard, {
      props: {
        data: {
          completed_tasks: 1, total_tasks: 12,
          submission_count: 1, average_score: null,
        },
      },
    });
    expect(w.text()).toContain('3 件提出');
  });

  it('reactively hides the hint when submission_count rises across the threshold (LOW-1)', async () => {
    // The setup() body captured belowThreshold as a plain boolean
    // before this fix. The component lived behind HomeView's
    // v-if="dashboard.data" so a remount masked the bug. The
    // regression test fixes belowThreshold as a computed by
    // exercising prop reactivity directly.
    const w = mount(ProgressSummaryCard, {
      props: {
        data: {
          completed_tasks: 1, total_tasks: 12,
          submission_count: 1, average_score: null,
        },
      },
    });
    expect(w.text()).toContain('3 件提出');

    await w.setProps({
      data: {
        completed_tasks: 4, total_tasks: 12,
        submission_count: 4, average_score: 70,
      },
    });
    expect(w.text()).not.toContain('3 件提出');
    expect(w.text()).toContain('70');
  });
});
