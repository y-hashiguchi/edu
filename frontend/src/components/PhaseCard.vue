<script setup lang="ts">
import type { PhaseSummary } from '@/types/curriculum';

defineProps<{ phase: PhaseSummary }>();
</script>

<template>
  <article class="phase-card">
    <header>
      <span class="phase-no">Phase {{ phase.phase }}</span>
      <h2>{{ phase.title }}</h2>
      <p class="duration">{{ phase.duration }}</p>
    </header>

    <p class="goal">{{ phase.goal }}</p>

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

    <RouterLink :to="{ name: 'phase', params: { phase: phase.phase } }" class="cta">
      AIチューターと対話する →
    </RouterLink>
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
}
.phase-no {
  display: inline-block;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--color-accent);
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
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
</style>
