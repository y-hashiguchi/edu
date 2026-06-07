import { defineStore } from 'pinia';
import { rawRequest } from '@/lib/api';
import type { TokenResponse, UserOut } from '@/types/curriculum';

interface State {
  token: string | null;
  user: UserOut | null;
}

export const useAuthStore = defineStore('auth', {
  state: (): State => ({ token: null, user: null }),
  getters: {
    isAuthenticated: (s) => s.token !== null,
    /**
     * Convenience getter used by Vue Router guards (`router/admin.ts`)
     * and by `NotificationCenter` to render admin-only affordances.
     * Server-side endpoints re-check `is_admin` on every admin call —
     * this getter exists purely so the SPA can route, never to grant.
     */
    isAdmin: (s) => s.user?.is_admin === true,
  },
  actions: {
    async login(email: string, password: string) {
      const t = await rawRequest<TokenResponse>('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      });
      this.token = t.access_token;
      await this.fetchMe();
    },

    async register(email: string, name: string, password: string) {
      await rawRequest<UserOut>('/api/auth/register', {
        method: 'POST',
        body: JSON.stringify({ email, name, password }),
      });
    },

    async fetchMe() {
      if (!this.token) return;
      this.user = await rawRequest<UserOut>('/api/auth/me', { method: 'GET' });
    },

    logout() {
      this.token = null;
      this.user = null;
    },
  },
  persist: {
    paths: ['token'],
  },
});
