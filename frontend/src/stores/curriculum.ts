import { defineStore } from 'pinia';
import { api } from '@/lib/api';
import type { ChatMessage, PhaseSummary } from '@/types/curriculum';

interface State {
  phases: PhaseSummary[];
  loading: boolean;
  error: string | null;
  chatLogs: Record<number, ChatMessage[]>;
  userId: string;
}

export const useCurriculumStore = defineStore('curriculum', {
  state: (): State => ({
    phases: [],
    loading: false,
    error: null,
    chatLogs: {},
    userId: 'demo-user',
  }),
  actions: {
    async fetchPhases() {
      this.loading = true;
      this.error = null;
      try {
        this.phases = await api.listPhases();
      } catch (e) {
        this.error = e instanceof Error ? e.message : 'unknown error';
      } finally {
        this.loading = false;
      }
    },

    async sendChat(phase: number, message: string) {
      const result = await api.sendChat({ phase, message });
      this.chatLogs[phase] = result.history;
      return result.reply;
    },

    getPhase(phaseNo: number): PhaseSummary | undefined {
      return this.phases.find((p) => p.phase === phaseNo);
    },
  },
});
