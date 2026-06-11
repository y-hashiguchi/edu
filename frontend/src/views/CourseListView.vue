<script setup lang="ts">
/**
 * /courses — the post-login landing page.
 *
 * Shows the learner's enrolled courses as link cards. Below that, any
 * catalog course they are NOT yet enrolled in is shown with a help
 * text telling them to ask an admin (Sprint 7 does not ship a learner
 * self-service enroll flow — admin-controlled per the handoff doc).
 */
import { computed, onMounted, ref } from 'vue';
import { useCourseStore } from '@/stores/course';

const course = useCourseStore();
const loading = ref(true);
const error = ref<string | null>(null);

const myCourses = computed(() => course.myCourses);

const additionalCourses = computed(() =>
  course.catalog.filter((c) => !course.isEnrolled(c.slug)),
);

onMounted(async () => {
  loading.value = true;
  error.value = null;
  try {
    await Promise.all([
      course.fetchMyCourses(),
      course.fetchCatalog(),
    ]);
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'unknown error';
  } finally {
    loading.value = false;
  }
});

function statusLabel(status: string): string {
  switch (status) {
    case 'active':
      return '受講中';
    case 'paused':
      return '一時停止';
    case 'completed':
      return '修了';
    default:
      return status;
  }
}
</script>

<template>
  <section class="courses">
    <header>
      <h1>あなたのコース</h1>
    </header>

    <p v-if="loading" class="loading">読み込み中…</p>
    <p v-else-if="error" class="error" role="alert">{{ error }}</p>

    <template v-else>
      <p v-if="myCourses.length === 0" class="empty" data-test="empty">
        受講中のコースはありません
      </p>

      <ul v-else class="course-list" data-test="my-courses">
        <li v-for="c in myCourses" :key="c.slug" class="course-card">
          <RouterLink
            :to="`/courses/${c.slug}`"
            class="card-link"
            :data-test-slug="c.slug"
          >
            <header class="card-head">
              <h2>{{ c.title }}</h2>
              <span class="badge" :data-status="c.status">
                {{ statusLabel(c.status) }}
              </span>
            </header>
            <p v-if="c.description" class="desc">{{ c.description }}</p>
          </RouterLink>
        </li>
      </ul>

      <section
        v-if="additionalCourses.length > 0"
        class="additional"
        data-test="additional-courses"
      >
        <h2>その他のコース</h2>
        <p class="hint">追加受講は管理者へ依頼してください。</p>
        <ul>
          <li v-for="c in additionalCourses" :key="c.slug">
            <strong>{{ c.title }}</strong>
            <p v-if="c.description">{{ c.description }}</p>
          </li>
        </ul>
      </section>
    </template>
  </section>
</template>

<style scoped>
.courses {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}
header h1 { margin: 0; font-size: 1.3rem; }
.loading { color: #6b7280; font-size: 0.9rem; }
.error {
  background: #fee2e2;
  color: #991b1b;
  padding: 0.7rem 1rem;
  border-radius: 10px;
}
.empty {
  background: #f9fafb;
  border-radius: 12px;
  padding: 1.25rem;
  color: #6b7280;
}
.course-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 1rem;
}
.course-card {
  background: white;
  border-radius: 14px;
  box-shadow: 0 2px 12px rgba(15, 23, 42, 0.04);
  transition: transform 0.15s ease;
}
.course-card:hover { transform: translateY(-2px); }
.card-link {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 1.1rem 1.25rem;
  text-decoration: none;
  color: inherit;
}
.card-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.5rem;
}
.card-head h2 { margin: 0; font-size: 1.05rem; }
.badge {
  font-size: 0.7rem;
  padding: 2px 8px;
  border-radius: 999px;
  background: #e5e7eb;
  color: #374151;
  font-weight: 600;
}
.badge[data-status='active'] { background: #dbeafe; color: #1d4ed8; }
.badge[data-status='paused'] { background: #fef3c7; color: #92400e; }
.badge[data-status='completed'] { background: #dcfce7; color: #166534; }
.desc { margin: 0; font-size: 0.9rem; color: #4b5563; }
.additional {
  background: #f9fafb;
  border-radius: 14px;
  padding: 1.1rem 1.25rem;
}
.additional h2 { margin: 0 0 0.4rem; font-size: 1rem; }
.additional .hint {
  margin: 0 0 0.7rem;
  font-size: 0.85rem;
  color: #6b7280;
}
.additional ul {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.additional li {
  background: white;
  padding: 0.7rem 0.9rem;
  border-radius: 10px;
}
.additional li strong { display: block; font-size: 0.95rem; }
.additional li p { margin: 0.2rem 0 0; font-size: 0.85rem; color: #4b5563; }
</style>
