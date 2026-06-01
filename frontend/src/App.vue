<script setup lang="ts">
import { RouterView } from 'vue-router';
</script>

<template>
  <header class="app-header">
    <h1>AI駆動型開発 補足カリキュラム</h1>
    <p>AIチューター — 学習サポートシステム</p>
  </header>
  <main class="app-main">
    <RouterView />
  </main>
</template>

<style>
:root {
  --color-bg: #f6f7fb;
  --color-surface: #ffffff;
  --color-text: #1b1f24;
  --color-accent: #2f6df6;
  --radius: 14px;
}

* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: 'Inter', system-ui, -apple-system, 'Hiragino Kaku Gothic ProN', sans-serif;
  background: var(--color-bg);
  color: var(--color-text);
}

.app-header {
  padding: 1.5rem 2rem;
  background: var(--color-surface);
  border-bottom: 1px solid #e5e7eb;
}
.app-header h1 { margin: 0; font-size: 1.25rem; }
.app-header p { margin: 0.25rem 0 0; color: #6b7280; font-size: 0.875rem; }

.app-main { padding: 2rem; max-width: 960px; margin: 0 auto; }
</style>
