<script setup lang="ts">
import { ref } from 'vue';

const props = defineProps<{ tags: string[] }>();
const emit = defineEmits<{ change: [tags: string[]] }>();

const draft = ref('');

function addTag() {
  const t = draft.value.trim();
  if (!t || t.length > 50) return;
  if (props.tags.includes(t)) return;
  emit('change', [...props.tags, t]);
  draft.value = '';
}

function removeTag(t: string) {
  emit('change', props.tags.filter((x) => x !== t));
}
</script>

<template>
  <div class="tags">
    <span v-for="t in tags" :key="t" class="chip">
      {{ t }}
      <button
        type="button"
        class="remove"
        :aria-label="`Remove ${t}`"
        @click="removeTag(t)"
      >×</button>
    </span>
    <input
      v-model="draft"
      type="text"
      placeholder="新しいタグ + Enter"
      maxlength="50"
      data-test="skill-tag-input"
      @keydown.enter.prevent="addTag"
      @blur="addTag"
    />
  </div>
</template>

<style scoped>
.tags { display: flex; flex-wrap: wrap; gap: 0.4rem; align-items: center; }
.chip {
  background: #e0e7ff; color: #3730a3;
  padding: 0.2rem 0.6rem; border-radius: 999px; font-size: 0.85rem;
  display: inline-flex; gap: 0.3rem; align-items: center;
}
.remove { background: none; border: 0; color: inherit; cursor: pointer; }
input {
  flex: 1; min-width: 8rem;
  border: 1px solid #d1d5db; border-radius: 6px;
  padding: 0.3rem 0.5rem; font: inherit;
}
</style>
