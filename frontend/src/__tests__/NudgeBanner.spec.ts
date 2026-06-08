import { describe, expect, it } from 'vitest';
import { mount } from '@vue/test-utils';
import NudgeBanner from '@/components/NudgeBanner.vue';

const baseNudge = {
  body: '今日は Phase 2 task 1 に挑戦しよう。',
  generated_at: '2026-06-08T07:00:00Z',
  is_fresh: true,
};

describe('NudgeBanner', () => {
  it('renders body text', () => {
    const w = mount(NudgeBanner, { props: { nudge: baseNudge } });
    expect(w.text()).toContain('Phase 2 task 1 に挑戦');
  });

  it('shows generated_at in a relative format', () => {
    const w = mount(NudgeBanner, { props: { nudge: baseNudge } });
    expect(w.find('time').exists()).toBe(true);
    expect(w.find('time').attributes('datetime')).toBe('2026-06-08T07:00:00Z');
  });

  it('marks stale nudge visually', () => {
    const w = mount(NudgeBanner, {
      props: { nudge: { ...baseNudge, is_fresh: false } },
    });
    expect(w.classes()).toContain('stale');
  });
});
