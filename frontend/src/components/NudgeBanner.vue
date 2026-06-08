<script setup lang="ts">
import type { Nudge } from '@/types/dashboard';

defineProps<{ nudge: Nudge }>();
</script>

<template>
  <section
    class="nudge-banner"
    :class="{ stale: !nudge.is_fresh }"
    role="region"
    aria-labelledby="nudge-heading"
  >
    <h2 id="nudge-heading" class="sr-only">今日のアドバイス</h2>
    <p class="body">{{ nudge.body }}</p>
    <time class="ts" :datetime="nudge.generated_at">
      {{ new Date(nudge.generated_at).toLocaleString('ja-JP') }} 生成
    </time>
  </section>
</template>

<style scoped>
.nudge-banner {
  background: linear-gradient(135deg, #eef2ff 0%, #f5f3ff 100%);
  border: 1px solid #c7d2fe;
  border-radius: 12px;
  padding: 1rem 1.2rem;
  margin: 0 0 1.2rem;
}
.nudge-banner.stale {
  background: #f3f4f6;
  border-color: #e5e7eb;
}
.body {
  margin: 0;
  font-size: 1rem;
  font-weight: 500;
  color: #1f2937;
}
.ts {
  display: block;
  margin-top: 0.4rem;
  font-size: 0.72rem;
  color: #6b7280;
}
.sr-only {
  position: absolute;
  width: 1px; height: 1px;
  padding: 0; margin: -1px;
  overflow: hidden;
  clip: rect(0,0,0,0);
  white-space: nowrap; border: 0;
}
</style>
