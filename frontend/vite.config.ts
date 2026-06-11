/// <reference types="vitest" />
import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import path from 'node:path';

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./vitest.setup.ts'],
    // Playwright E2E specs live under frontend/e2e/ and use the
    // Playwright runner (npm run test:e2e). Exclude them from vitest
    // collection so unit-test runs don't try to load @playwright/test.
    exclude: ['node_modules', 'dist', '.idea', '.git', '.cache', 'e2e/**'],
  },
});
