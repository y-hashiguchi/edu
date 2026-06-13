<script setup lang="ts">
import { onMounted } from 'vue';
import { RouterLink } from 'vue-router';
import { useAdminCurriculumStore } from '@/stores/admin_curriculum';

const store = useAdminCurriculumStore();

onMounted(() => {
  void store.fetchList();
});
</script>

<template>
  <section class="curriculum-list">
    <h1>カリキュラム編集</h1>
    <p class="hint">
      タスク本文・skill_tags・Phase の system_prompt 等を編集できます。
      公開すると受講者の表示が即座に切り替わります。
    </p>

    <ul class="courses">
      <li v-for="c in store.list" :key="c.slug" class="course">
        <RouterLink
          :to="`/admin/curriculum/${c.slug}`"
          class="course-link"
        >
          <span class="title">{{ c.title }}</span>
          <span
            v-if="c.pending_draft_count > 0"
            class="badge"
            data-test="draft-badge"
          >
            {{ c.pending_draft_count }} 件の draft
          </span>
        </RouterLink>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.curriculum-list { max-width: 720px; margin: 2rem auto; }
.hint { color: #6b7280; font-size: 0.9rem; }
.courses { list-style: none; padding: 0; }
.course { margin: 0.75rem 0; }
.course-link {
  display: flex; align-items: center; justify-content: space-between;
  padding: 1rem; border: 1px solid #e5e7eb; border-radius: 12px;
  text-decoration: none; color: inherit;
}
.title { font-weight: 600; }
.badge {
  background: #fef3c7; color: #92400e;
  padding: 0.2rem 0.6rem; border-radius: 999px;
  font-size: 0.8rem;
}
</style>
