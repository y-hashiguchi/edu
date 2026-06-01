<script setup lang="ts">
import { ref } from 'vue';

const props = defineProps<{ disabled?: boolean }>();
const emit = defineEmits<{ submit: [text: string] }>();

const text = ref('');

const send = () => {
  const value = text.value.trim();
  if (!value || props.disabled) return;
  emit('submit', value);
  text.value = '';
};

const onKeydown = (e: KeyboardEvent) => {
  if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
    e.preventDefault();
    send();
  }
};
</script>

<template>
  <form class="chat-input" @submit.prevent="send">
    <textarea
      v-model="text"
      :disabled="disabled"
      rows="3"
      placeholder="質問を入力（Cmd/Ctrl+Enter で送信）"
      @keydown="onKeydown"
    />
    <button type="submit" :disabled="disabled || !text.trim()">
      送信
    </button>
  </form>
</template>

<style scoped>
.chat-input {
  display: flex;
  gap: 0.65rem;
  margin-top: 0.85rem;
}
textarea {
  flex: 1;
  padding: 0.75rem;
  border: 1px solid #d1d5db;
  border-radius: 10px;
  font: inherit;
  resize: vertical;
}
textarea:focus {
  outline: 2px solid var(--color-accent);
  outline-offset: 1px;
}
button {
  background: var(--color-accent);
  color: white;
  border: 0;
  padding: 0 1.25rem;
  border-radius: 10px;
  font-weight: 600;
  cursor: pointer;
}
button:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
