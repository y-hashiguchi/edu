<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import { useCourseStore } from '@/stores/course';
import { api } from '@/lib/api';
import type { CourseCatalogItem } from '@/types/course';

const mode = ref<'login' | 'register'>('login');
const email = ref('');
const password = ref('');
const name = ref('');
const courseSlug = ref('');
const error = ref<string | null>(null);
const notice = ref<string | null>(null);
const submitting = ref(false);
const catalog = ref<CourseCatalogItem[]>([]);
const catalogError = ref<string | null>(null);

const auth = useAuthStore();
const course = useCourseStore();
const router = useRouter();

// Disable submit until a course is picked when registering. Login
// doesn't need a course — the post-login routing picks one.
const canSubmit = computed(() => {
  if (mode.value === 'register' && !courseSlug.value) return false;
  return !submitting.value;
});

onMounted(async () => {
  // Load the catalog regardless of which tab is active — the user
  // may flip to "register" without leaving the page.
  try {
    const res = await api.listCourseCatalog();
    catalog.value = [...res.items].sort(
      (a, b) => a.sort_order - b.sort_order,
    );
  } catch {
    catalogError.value =
      'コース一覧の取得に失敗しました。時間をおいて再試行してください';
  }
});

async function routeAfterLogin() {
  await course.fetchMyCourses();
  const courses = course.myCourses;
  if (courses.length === 1) {
    course.setActiveCourse(courses[0].slug);
    await router.push(`/courses/${courses[0].slug}`);
  } else {
    await router.push('/courses');
  }
}

const submit = async () => {
  error.value = null;
  notice.value = null;
  submitting.value = true;
  try {
    if (mode.value === 'login') {
      await auth.login(email.value, password.value);
      await routeAfterLogin();
    } else {
      // courseSlug.value is guarded by canSubmit / required <select>
      await auth.register(email.value, name.value, password.value, courseSlug.value);
      // Remember the freshly registered course so the next login lands on
      // it immediately (also avoids racing the my-courses fetch).
      course.setActiveCourse(courseSlug.value);
      mode.value = 'login';
      notice.value = '登録できました。続けてログインしてください。';
      password.value = '';
    }
  } catch (e) {
    if (e instanceof Error && e.message.includes('409')) {
      error.value = 'このメールアドレスは既に登録されています';
    } else if (e instanceof Error && e.message.includes('401')) {
      error.value = 'メールアドレスまたはパスワードが正しくありません';
    } else if (e instanceof Error && e.message.includes('422')) {
      error.value = '入力内容を確認してください';
    } else {
      error.value = '通信に失敗しました。時間をおいて再試行してください';
    }
  } finally {
    submitting.value = false;
  }
};
</script>

<template>
  <section class="login">
    <nav class="tabs" role="tablist">
      <button
        :class="{ active: mode === 'login' }"
        role="tab"
        :aria-selected="mode === 'login'"
        @click="mode = 'login'"
      >
        ログイン
      </button>
      <button
        :class="{ active: mode === 'register' }"
        role="tab"
        :aria-selected="mode === 'register'"
        @click="mode = 'register'"
      >
        新規登録
      </button>
    </nav>

    <form class="form" @submit.prevent="submit">
      <label>
        メールアドレス
        <input v-model="email" type="email" autocomplete="email" required />
      </label>

      <label v-if="mode === 'register'">
        お名前
        <input v-model="name" type="text" maxlength="100" required />
      </label>

      <label v-if="mode === 'register'">
        受講コース
        <select
          v-model="courseSlug"
          data-test="course-select"
          required
        >
          <option value="" disabled>選択してください</option>
          <option
            v-for="c in catalog"
            :key="c.slug"
            :value="c.slug"
          >
            {{ c.title }}
          </option>
        </select>
        <small v-if="catalogError" class="course-help error-text">
          {{ catalogError }}
        </small>
      </label>

      <label>
        パスワード
        <input
          v-model="password"
          type="password"
          minlength="8"
          maxlength="128"
          autocomplete="current-password"
          required
        />
      </label>

      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <p v-if="notice" class="notice" role="status">{{ notice }}</p>

      <button type="submit" :disabled="!canSubmit">
        {{ mode === 'login' ? 'ログイン' : '登録する' }}
      </button>
    </form>
  </section>
</template>

<style scoped>
.login {
  max-width: 420px;
  margin: 2rem auto;
  background: var(--color-surface, white);
  border-radius: var(--radius, 14px);
  box-shadow: 0 2px 12px rgba(15, 23, 42, 0.04);
  padding: 1.5rem;
}
.tabs {
  display: flex;
  gap: 0.5rem;
  border-bottom: 1px solid #e5e7eb;
  padding-bottom: 0.5rem;
  margin-bottom: 1rem;
}
.tabs button {
  background: none;
  border: 0;
  padding: 0.5rem 1rem;
  cursor: pointer;
  font: inherit;
  color: #6b7280;
}
.tabs button.active {
  color: var(--color-accent, #2f6df6);
  border-bottom: 2px solid var(--color-accent, #2f6df6);
}
.form { display: flex; flex-direction: column; gap: 1rem; }
.form label { display: flex; flex-direction: column; font-size: 0.9rem; gap: 0.35rem; }
.form input, .form select {
  padding: 0.6rem 0.8rem;
  border: 1px solid #d1d5db;
  border-radius: 10px;
  font: inherit;
}
.form button[type='submit'] {
  background: var(--color-accent, #2f6df6);
  color: white;
  border: 0;
  border-radius: 10px;
  padding: 0.7rem;
  font-weight: 600;
  cursor: pointer;
}
.form button[type='submit']:disabled { opacity: 0.5; cursor: not-allowed; }
.error {
  background: #fee2e2;
  color: #991b1b;
  padding: 0.6rem 0.8rem;
  border-radius: 10px;
  margin: 0;
}
.error-text { color: #b91c1c; font-size: 0.78rem; }
.course-help { margin: 0; }
.notice {
  background: #dcfce7;
  color: #166534;
  padding: 0.6rem 0.8rem;
  border-radius: 10px;
  margin: 0;
}
</style>
