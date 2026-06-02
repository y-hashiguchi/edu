import { defineStore } from 'pinia';
import { api } from '@/lib/api';
import type {
  ChatMessage,
  PhaseSummary,
  ProgressCompleteResponse,
  ProgressOut,
} from '@/types/curriculum';

interface State {
  phases: PhaseSummary[];
  progress: Record<number, ProgressOut>;
  chatLogs: Record<number, ChatMessage[]>;
  loading: boolean;
  error: string | null;
}

export const useCurriculumStore = defineStore('curriculum', {
  state: (): State => ({
    phases: [],
    progress: {},
    chatLogs: {},
    loading: false,
    error: null,
  }),
  getters: {
    completedCount: (s) =>
      Object.values(s.progress).filter((p) => p.status === 'completed').length,
  },
  actions: {
    async fetchPhasesWithProgress() {
      this.loading = true;
      this.error = null;
      try {
        const [phases, progress] = await Promise.all([
          api.listPhases(),
          api.listProgress(),
        ]);
        this.phases = phases;
        this.progress = Object.fromEntries(progress.map((p) => [p.phase, p]));
      } catch (e) {
        this.error = e instanceof Error ? e.message : 'unknown error';
      } finally {
        this.loading = false;
      }
    },

    async completePhase(phase: number): Promise<ProgressCompleteResponse> {
      const result = await api.completePhase(phase);

      this.progress[phase] = {
        phase: result.phase,
        status: result.status,
        started_at: result.started_at,
        completed_at: result.completed_at,
      };
      if (result.next_unlocked) {
        const n = result.next_unlocked;
        this.progress[n.phase] = n;
      }

      this.phases = this.phases.map((p) => {
        const prog = this.progress[p.phase];
        if (!prog) return p;
        return { ...p, locked: prog.status === 'locked', status: prog.status };
      });
      return result;
    },

    async loadHistory(phase: number) {
      const history = await api.getChatHistory(phase);
      this.chatLogs[phase] = history.map((m) => ({
        role: m.role,
        content: m.content,
      }));
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
