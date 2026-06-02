<script setup lang="ts">
import { computed } from 'vue';
import type { PhaseSummary } from '@/types/curriculum';

const props = defineProps<{ phase: PhaseSummary }>();

const badgeLabel = computed(() => {
  switch (props.phase.status) {
    case 'in_progress':
      return '進行中';
    case 'submitted':
      return '提出済み';
    case 'completed':
      return '完了';
    default:
      return 'ロック';
  }
});

const lockReason = computed(() => {
  if (!props.phase.locked) return '';
  if (props.phase.phase === 1) return '';
  return `Phase ${props.phase.phase - 1} を完了すると解放されます`;
});
</script>

<template>
  <article class="phase-card" :class="{ locked: phase.locked }">
    <header>
      <span class="phase-no">Phase {{ phase.phase }}</span>
      <span class="badge" :data-status="phase.status">{{ badgeLabel }}</span>
      <h2>{{ phase.title }}</h2>
      <p class="duration">{{ phase.duration }}</p>
    </header>

    <p class="goal">{{ phase.goal }}</p>

    <template v-if="!phase.locked">
      <section>
        <h3>学習スキル</h3>
        <ul>
          <li v-for="s in phase.skills" :key="s">{{ s }}</li>
        </ul>
      </section>

      <section>
        <h3>課題</h3>
        <ol>
          <li v-for="t in phase.tasks" :key="t">{{ t }}</li>
        </ol>
      </section>

      <RouterLink
        :to="{ name: 'phase', params: { phase: phase.phase } }"
        class="cta"
      >
        AIチューターと対話する →
      </RouterLink>
    </template>

    <template v-else>
      <p class="lock-msg" aria-live="polite">🔒 {{ lockReason }}</p>
    </template>
  </article>
</template>

<style scoped>
.phase-card {
  background: var(--color-surface);
  border-radius: var(--radius);
  padding: 1.5rem;
  box-shadow: 0 2px 12px rgba(15, 23, 42, 0.04);
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  position: relative;
}
.phase-card.locked { filter: grayscale(0.4); opacity: 0.78; }

.phase-no {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--color-accent);
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.badge {
  display: inline-block;
  margin-left: 0.5rem;
  font-size: 0.7rem;
  padding: 2px 8px;
  border-radius: 999px;
  font-weight: 600;
  background: #e5e7eb;
  color: #374151;
}
.badge[data-status='in_progress'] { background: #dbeafe; color: #1d4ed8; }
.badge[data-status='completed']   { background: #dcfce7; color: #166534; }
.badge[data-status='submitted']   { background: #fef3c7; color: #92400e; }
.badge[data-status='locked']      { background: #f3f4f6; color: #6b7280; }

.phase-card h2 { margin: 0.25rem 0 0; font-size: 1.15rem; }
.duration { margin: 0; color: #6b7280; font-size: 0.85rem; }
.goal { margin: 0; font-size: 0.95rem; }
section h3 {
  margin: 0 0 0.35rem;
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: #6b7280;
}
section ul, section ol { margin: 0; padding-left: 1.25rem; font-size: 0.9rem; }
.cta {
  margin-top: auto;
  align-self: flex-start;
  color: var(--color-accent);
  font-weight: 600;
  text-decoration: none;
}
.cta:hover { text-decoration: underline; }
.lock-msg { color: #6b7280; font-size: 0.9rem; margin: 0; }
</style>
