<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { RouterLink } from 'vue-router';
import { useAdminCurriculumStore } from '@/stores/admin_curriculum';
import { PROTECTED_COURSE_SLUGS } from '@/types/admin_curriculum';

const store = useAdminCurriculumStore();

const showCreate = ref(false);
const newSlug = ref('');
const newTitle = ref('');
const newDescription = ref('');
const creating = ref(false);
const deletingSlug = ref<string | null>(null);

function isProtected(slug: string): boolean {
  return (PROTECTED_COURSE_SLUGS as readonly string[]).includes(slug);
}

onMounted(() => {
  void store.fetchList();
});

async function submitCreate() {
  if (!newSlug.value.trim() || !newTitle.value.trim()) return;
  creating.value = true;
  try {
    await store.createCourse({
      slug: newSlug.value.trim(),
      title: newTitle.value.trim(),
      description: newDescription.value.trim() || null,
    });
    showCreate.value = false;
    newSlug.value = '';
    newTitle.value = '';
    newDescription.value = '';
  } finally {
    creating.value = false;
  }
}

async function confirmDelete(slug: string, title: string) {
  if (isProtected(slug)) return;
  if (!window.confirm(`コース「${title}」を削除しますか？\n受講者・提出がない場合のみ削除できます。`)) {
    return;
  }
  deletingSlug.value = slug;
  try {
    await store.deleteCourse(slug);
  } finally {
    deletingSlug.value = null;
  }
}
</script>

<template>
  <section class="curriculum-list">
    <header class="header">
      <div>
        <h1>カリキュラム編集</h1>
        <p class="hint">
          タスク本文・skill_tags・Phase の system_prompt 等を編集できます。
          公開すると受講者の表示が即座に切り替わります。
        </p>
      </div>
      <button
        type="button"
        class="btn-primary"
        data-test="create-course-btn"
        @click="showCreate = !showCreate"
      >
        + コースを追加
      </button>
    </header>

    <form
      v-if="showCreate"
      class="create-form"
      data-test="create-course-form"
      @submit.prevent="submitCreate"
    >
      <label>
        slug（英小文字・数字・-_ のみ）
        <input
          v-model="newSlug"
          type="text"
          required
          pattern="[a-z0-9_-]+"
          data-test="create-course-slug"
        />
      </label>
      <label>
        タイトル
        <input v-model="newTitle" type="text" required data-test="create-course-title" />
      </label>
      <label>
        説明（任意）
        <input v-model="newDescription" type="text" data-test="create-course-description" />
      </label>
      <div class="form-actions">
        <button type="submit" class="btn-primary" :disabled="creating" data-test="create-course-submit">
          作成
        </button>
        <button type="button" class="btn-ghost" @click="showCreate = false">
          キャンセル
        </button>
      </div>
    </form>

    <p v-if="store.saveError" class="error">{{ store.saveError }}</p>

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
        <button
          v-if="!isProtected(c.slug)"
          type="button"
          class="btn-delete"
          :data-test="`delete-course-${c.slug}`"
          :disabled="deletingSlug === c.slug"
          @click="confirmDelete(c.slug, c.title)"
        >
          削除
        </button>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.curriculum-list { max-width: 720px; margin: 2rem auto; }
.header {
  display: flex; align-items: flex-start; justify-content: space-between;
  gap: 1rem; margin-bottom: 1rem;
}
.hint { color: #6b7280; font-size: 0.9rem; margin: 0.5rem 0 0; }
.courses { list-style: none; padding: 0; }
.course {
  display: flex; align-items: center; gap: 0.5rem;
  margin: 0.75rem 0;
}
.course-link {
  flex: 1;
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
.create-form {
  display: flex; flex-direction: column; gap: 0.75rem;
  padding: 1rem; margin-bottom: 1rem;
  border: 1px solid #e5e7eb; border-radius: 12px; background: #f9fafb;
}
.create-form label {
  display: flex; flex-direction: column; gap: 0.25rem;
  font-size: 0.85rem; font-weight: 500;
}
.create-form input {
  padding: 0.5rem 0.75rem; border: 1px solid #d1d5db;
  border-radius: 8px; font-size: 1rem;
}
.form-actions { display: flex; gap: 0.5rem; }
.btn-primary {
  padding: 0.5rem 1rem; border: none; border-radius: 8px;
  background: #2563eb; color: white; font-weight: 600; cursor: pointer;
}
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-ghost {
  padding: 0.5rem 1rem; border: 1px solid #d1d5db; border-radius: 8px;
  background: white; cursor: pointer;
}
.btn-delete {
  padding: 0.5rem 0.75rem; border: 1px solid #fecaca; border-radius: 8px;
  background: #fef2f2; color: #b91c1c; cursor: pointer; white-space: nowrap;
}
.btn-delete:disabled { opacity: 0.6; cursor: not-allowed; }
.error { color: #b91c1c; font-size: 0.9rem; }
</style>
