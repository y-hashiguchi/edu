<script setup lang="ts">
import { computed, ref } from 'vue';

const props = defineProps<{
  maxFiles?: number;
  maxBytes?: number;
  acceptExtensions?: string[];
  disabled?: boolean;
}>();

const emit = defineEmits<{
  change: [files: File[]];
}>();

const maxFiles = computed(() => props.maxFiles ?? 3);
const maxBytes = computed(() => props.maxBytes ?? 5 * 1024 * 1024);
const acceptExtensions = computed(
  () =>
    props.acceptExtensions ?? [
      'py',
      'java',
      'js',
      'ts',
      'txt',
      'md',
      'png',
      'jpg',
      'jpeg',
      'pdf',
    ],
);
const acceptAttr = computed(() =>
  acceptExtensions.value.map((e) => `.${e}`).join(','),
);

const selected = ref<File[]>([]);
const errors = ref<string[]>([]);
const dragOver = ref(false);
const inputRef = ref<HTMLInputElement | null>(null);

function reset() {
  selected.value = [];
  errors.value = [];
  if (inputRef.value) inputRef.value.value = '';
  emit('change', []);
}

defineExpose({ reset });

function extOf(name: string): string {
  const idx = name.lastIndexOf('.');
  return idx >= 0 ? name.slice(idx + 1).toLowerCase() : '';
}

function validate(file: File): string | null {
  const ext = extOf(file.name);
  if (!acceptExtensions.value.includes(ext)) {
    return `${file.name}: 拡張子 .${ext} は対応していません`;
  }
  if (file.size > maxBytes.value) {
    return `${file.name}: サイズ ${(file.size / 1024 / 1024).toFixed(1)} MB は上限 ${(maxBytes.value / 1024 / 1024).toFixed(0)} MB を超えています`;
  }
  return null;
}

function addFiles(incoming: FileList | File[]) {
  const list = Array.from(incoming);
  const next: File[] = [...selected.value];
  const errs: string[] = [];
  for (const f of list) {
    if (next.length >= maxFiles.value) {
      errs.push(`${maxFiles.value} ファイルが上限です`);
      break;
    }
    const err = validate(f);
    if (err) {
      errs.push(err);
      continue;
    }
    if (next.some((x) => x.name === f.name && x.size === f.size)) continue;
    next.push(f);
  }
  selected.value = next;
  errors.value = errs;
  emit('change', next);
}

function removeAt(index: number) {
  const next = [...selected.value];
  next.splice(index, 1);
  selected.value = next;
  emit('change', next);
}

function onDrop(e: DragEvent) {
  e.preventDefault();
  dragOver.value = false;
  if (props.disabled) return;
  if (e.dataTransfer?.files) addFiles(e.dataTransfer.files);
}

function onPick(e: Event) {
  const target = e.target as HTMLInputElement;
  if (target.files) addFiles(target.files);
}
</script>

<template>
  <div class="upload-wrap">
    <label
      class="dropzone"
      :class="{ over: dragOver, disabled }"
      @dragover.prevent="dragOver = true"
      @dragleave.prevent="dragOver = false"
      @drop="onDrop"
    >
      <input
        ref="inputRef"
        type="file"
        :accept="acceptAttr"
        :disabled="disabled"
        multiple
        hidden
        @change="onPick"
      />
      <span>
        ファイルを選択またはドロップ
        ({{ acceptExtensions.join(', ') }}; 最大 {{ maxFiles }} 件,
        {{ Math.round(maxBytes / 1024 / 1024) }} MB/件)
      </span>
    </label>
    <ul v-if="selected.length" class="picked">
      <li v-for="(f, i) in selected" :key="`${f.name}-${i}`">
        <span class="name">{{ f.name }}</span>
        <span class="size">{{ (f.size / 1024).toFixed(1) }} KB</span>
        <button type="button" :disabled="disabled" @click="removeAt(i)">×</button>
      </li>
    </ul>
    <ul v-if="errors.length" class="errors">
      <li v-for="(err, i) in errors" :key="i">{{ err }}</li>
    </ul>
  </div>
</template>

<style scoped>
.upload-wrap {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}
.dropzone {
  display: block;
  padding: 0.6rem 0.8rem;
  border: 1px dashed #9ca3af;
  border-radius: 10px;
  background: #f9fafb;
  font-size: 0.85rem;
  color: #4b5563;
  cursor: pointer;
  text-align: center;
}
.dropzone.over {
  border-color: var(--color-accent);
  background: #eef2ff;
}
.dropzone.disabled {
  cursor: not-allowed;
  opacity: 0.6;
}
.picked,
.errors {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}
.picked li {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.85rem;
  background: #fff;
  padding: 0.3rem 0.5rem;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
}
.picked .name {
  flex: 1;
}
.picked .size {
  color: #6b7280;
  font-size: 0.75rem;
}
.picked button {
  background: transparent;
  border: 0;
  color: #ef4444;
  cursor: pointer;
  font-size: 1rem;
}
.errors li {
  color: #b91c1c;
  font-size: 0.8rem;
}
</style>
