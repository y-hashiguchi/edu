<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useCurriculumStore } from '@/stores/curriculum';
import ChatLog from '@/components/ChatLog.vue';
import ChatInput from '@/components/ChatInput.vue';

const props = defineProps<{ phase: number }>();
const store = useCurriculumStore();
const sending = ref(false);
const sendError = ref<string | null>(null);

const phaseData = computed(() => store.getPhase(props.phase));
const messages = computed(() => store.chatLogs[props.phase] ?? []);
const quickQuestions = computed(() => phaseData.value?.tasks.slice(0, 3) ?? []);

onMounted(async () => {
  if (store.phases.length === 0) {
    await store.fetchPhasesWithProgress();
  }
});

const submit = async (text: string) => {
  sending.value = true;
  sendError.value = null;
  try {
    await store.sendChat(props.phase, text);
  } catch (e) {
    sendError.value = e instanceof Error ? e.message : 'unknown error';
  } finally {
    sending.value = false;
  }
};
</script>

<template>
  <section v-if="!phaseData" class="loading">フェーズ情報を読み込み中…</section>
  <section v-else class="phase-chat">
    <header>
      <RouterLink to="/">← 一覧に戻る</RouterLink>
      <h2>Phase {{ phaseData.phase }} — {{ phaseData.title }}</h2>
      <p>{{ phaseData.goal }}</p>
    </header>

    <aside class="quick" v-if="quickQuestions.length > 0">
      <h3>クイック質問</h3>
      <button
        v-for="q in quickQuestions"
        :key="q"
        type="button"
        :disabled="sending"
        @click="submit(`課題について教えてください: ${q}`)"
      >
        {{ q }}
      </button>
    </aside>

    <ChatLog :messages="messages" />
    <p v-if="sendError" class="error">エラー: {{ sendError }}</p>
    <ChatInput :disabled="sending" @submit="submit" />
  </section>
</template>

<style scoped>
.phase-chat {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
.phase-chat header h2 { margin: 0.5rem 0 0.25rem; font-size: 1.2rem; }
.phase-chat header a { color: var(--color-accent); text-decoration: none; font-size: 0.9rem; }
.quick {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}
.quick h3 {
  margin: 0;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: #6b7280;
}
.quick button {
  background: white;
  border: 1px solid #d1d5db;
  border-radius: 10px;
  padding: 0.6rem 0.9rem;
  text-align: left;
  cursor: pointer;
  font: inherit;
}
.quick button:hover { border-color: var(--color-accent); }
.quick button:disabled { opacity: 0.5; cursor: not-allowed; }
.error {
  background: #fee2e2;
  color: #991b1b;
  padding: 0.6rem 0.9rem;
  border-radius: 10px;
  margin: 0;
}
.loading { color: #6b7280; }
</style>
