<script setup lang="ts">
// Placeholder — full implementation lands in Sprint 4 Task 19.
import { useRoute } from 'vue-router';
const route = useRoute();
</script>

<template>
  <section class="placeholder">
    <h1>受講者詳細</h1>
    <p>user_id: <code>{{ route.params.id }}</code></p>
    <p>Task 19 で実装します。</p>
  </section>
</template>

<style scoped>
.placeholder {
  background: #fff;
  border-radius: 12px;
  padding: 1.5rem;
}
</style>
