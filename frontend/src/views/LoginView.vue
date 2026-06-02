<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';

const mode = ref<'login' | 'register'>('login');
const email = ref('');
const password = ref('');
const name = ref('');
const error = ref<string | null>(null);
const notice = ref<string | null>(null);
const submitting = ref(false);

const auth = useAuthStore();
const router = useRouter();

const submit = async () => {
  error.value = null;
  notice.value = null;
  submitting.value = true;
  try {
    if (mode.value === 'login') {
      await auth.login(email.value, password.value);
      await router.push('/');
    } else {
      await auth.register(email.value, name.value, password.value);
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

      <button type="submit" :disabled="submitting">
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
.form input {
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
.notice {
  background: #dcfce7;
  color: #166534;
  padding: 0.6rem 0.8rem;
  border-radius: 10px;
  margin: 0;
}
</style>
