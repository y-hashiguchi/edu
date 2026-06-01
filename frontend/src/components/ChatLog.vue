<script setup lang="ts">
import type { ChatMessage } from '@/types/curriculum';
import ChatMessageComponent from '@/components/ChatMessage.vue';

defineProps<{ messages: ChatMessage[] }>();
</script>

<template>
  <div class="chat-log">
    <p v-if="messages.length === 0" class="empty">
      まだ会話がありません。下の入力欄から質問してみましょう。
    </p>
    <ChatMessageComponent
      v-for="(m, i) in messages"
      :key="i"
      :message="m"
    />
  </div>
</template>

<style scoped>
.chat-log {
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
  background: var(--color-surface);
  padding: 1.25rem;
  border-radius: var(--radius);
  min-height: 340px;
}
.empty {
  color: #6b7280;
  font-size: 0.9rem;
  text-align: center;
  padding: 1.5rem 0;
}
</style>
