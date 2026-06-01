<script setup lang="ts">
import type { ChatMessage } from '@/types/curriculum';

defineProps<{ message: ChatMessage }>();
</script>

<template>
  <div :class="['chat-message', message.role]">
    <span class="role">{{ message.role === 'user' ? 'あなた' : 'AIチューター' }}</span>
    <p>{{ message.content }}</p>
  </div>
</template>

<style scoped>
.chat-message {
  padding: 0.85rem 1rem;
  border-radius: 12px;
  max-width: 78%;
  white-space: pre-wrap;
}
.chat-message.user {
  background: var(--color-accent);
  color: white;
  align-self: flex-end;
}
.chat-message.assistant {
  background: #eef2ff;
  color: #1e1b4b;
  align-self: flex-start;
}
.role {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  opacity: 0.7;
  display: block;
  margin-bottom: 0.25rem;
}
.chat-message p { margin: 0; }
</style>
