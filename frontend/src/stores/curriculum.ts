import { defineStore } from 'pinia';
import { api, ApiCooldownError } from '@/lib/api';
import { useDashboardStore } from '@/stores/dashboard';
import type {
  ChatMessage,
  GradingAttempt,
  PhaseSummary,
  ProgressCompleteResponse,
  ProgressOut,
  Submission,
} from '@/types/curriculum';

interface State {
  phases: PhaseSummary[];
  progress: Record<number, ProgressOut>;
  chatLogs: Record<number, ChatMessage[]>;
  submissions: Record<number, Submission[]>;
  cooldownUntil: Record<string, number>;
  loading: boolean;
  error: string | null;
}

export const useCurriculumStore = defineStore('curriculum', {
  state: (): State => ({
    phases: [],
    progress: {},
    chatLogs: {},
    submissions: {},
    cooldownUntil: {},
    loading: false,
    error: null,
  }),
  getters: {
    completedCount: (s) =>
      Object.values(s.progress).filter((p) => p.status === 'completed').length,
    cooldownSecondsRemaining: (s) => (submissionId: string) => {
      const until = s.cooldownUntil[submissionId];
      if (!until) return 0;
      const now = Date.now();
      return until > now ? Math.ceil((until - now) / 1000) : 0;
    },
  },
  actions: {
    async fetchPhasesWithProgress(courseSlug: string) {
      this.loading = true;
      this.error = null;
      try {
        const [phases, progress] = await Promise.all([
          api.listPhases(courseSlug),
          api.listProgress(courseSlug),
        ]);
        this.phases = phases;
        this.progress = Object.fromEntries(progress.map((p) => [p.phase, p]));
      } catch (e) {
        this.error = e instanceof Error ? e.message : 'unknown error';
      } finally {
        this.loading = false;
      }
    },

    async completePhase(
      phase: number,
      courseSlug: string,
    ): Promise<ProgressCompleteResponse> {
      const result = await api.completePhase(phase, courseSlug);
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

    async loadHistory(phase: number, courseSlug: string) {
      const history = await api.getChatHistory(phase, courseSlug);
      this.chatLogs[phase] = history.map((m) => ({
        role: m.role,
        content: m.content,
      }));
    },

    async sendChat(phase: number, message: string, courseSlug: string) {
      const result = await api.sendChat({ phase, message }, courseSlug);
      this.chatLogs[phase] = result.history;
      return result.reply;
    },

    async loadSubmissions(phase: number, courseSlug: string) {
      this.submissions[phase] = await api.listSubmissions(phase, courseSlug);
    },

    async submitTask(
      phase: number,
      task_no: number,
      content: string,
      files: File[],
      courseSlug: string,
    ): Promise<Submission> {
      const submission = await api.submitTask(
        { phase, task_no, content, files },
        courseSlug,
      );
      const list = [...(this.submissions[phase] ?? [])];
      const idx = list.findIndex((s) => s.task_no === task_no);
      if (idx >= 0) list[idx] = submission;
      else list.push(submission);
      this.submissions[phase] = list.sort((a, b) => a.task_no - b.task_no);
      this._noteCooldownIfGraded(submission);
      // Sprint 5: any new submission shifts the dashboard's
      // weakness/recommendation/nudge inputs, so force a re-fetch on next mount.
      useDashboardStore().invalidate();
      await this.fetchPhasesWithProgress(courseSlug);
      // Sprint 8: async grading — poll until graded_at is set.
      if (submission.graded_at == null) {
        void this.pollUntilGraded(phase, task_no, courseSlug);
      }
      return submission;
    },

    async pollUntilGraded(
      phase: number,
      taskNo: number,
      courseSlug: string,
      maxAttempts = 30,
    ): Promise<void> {
      for (let i = 0; i < maxAttempts; i += 1) {
        await new Promise((r) => setTimeout(r, 2000));
        await this.loadSubmissions(phase, courseSlug);
        const current = (this.submissions[phase] ?? []).find(
          (s) => s.task_no === taskNo,
        );
        if (!current || current.graded_at != null) {
          if (current?.score != null) {
            this._noteCooldownIfGraded(current);
            useDashboardStore().invalidate();
            await this.fetchPhasesWithProgress(courseSlug);
          }
          return;
        }
      }
    },

    // Sprint 8 follow-up: poll the single-submission endpoint until the
    // graded_at column is filled. Used by the async regrade flow so the
    // store updates without refetching the whole phase list.
    async pollSubmissionById(
      phase: number,
      submissionId: string,
      courseSlug: string,
      maxAttempts = 30,
    ): Promise<void> {
      for (let i = 0; i < maxAttempts; i += 1) {
        await new Promise((r) => setTimeout(r, 2000));
        let updated: Submission;
        try {
          updated = await api.getMySubmission(submissionId);
        } catch {
          // Network blip: keep polling — the worker may still be running.
          continue;
        }
        this._replaceSubmission(phase, updated);
        if (updated.graded_at != null) {
          if (updated.score != null) {
            this._noteCooldownIfGraded(updated);
            useDashboardStore().invalidate();
            await this.fetchPhasesWithProgress(courseSlug);
          }
          return;
        }
      }
    },

    async regradeSubmission(
      phase: number,
      submissionId: string,
      courseSlug: string,
    ): Promise<GradingAttempt> {
      try {
        const attempt = await api.regradeSubmission(submissionId, courseSlug);
        if (attempt.status === 'pending') {
          // Async path: clear the cached graded_at so the UI shows
          // "採点中" and start polling the single-submission endpoint.
          this._markPending(phase, submissionId);
          void this.pollSubmissionById(phase, submissionId, courseSlug);
          return attempt;
        }
        this._mergeAttempt(phase, submissionId, attempt);
        if (attempt.status === 'graded') {
          this.cooldownUntil[submissionId] = Date.now() + 60_000;
          // LOW-2 (sprint-5 follow-up): a successful regrade shifts
          // the cached graded score, which feeds weakness / average /
          // nudge signature on the dashboard. submitTask already does
          // this; mirror it here so the learner doesn't see stale
          // dashboard state until the next navigation.
          useDashboardStore().invalidate();
        }
        return attempt;
      } catch (e) {
        if (e instanceof ApiCooldownError) {
          this.cooldownUntil[submissionId] =
            Date.now() + e.retryAfterSeconds * 1000;
        }
        throw e;
      }
    },

    _markPending(phase: number, submissionId: string) {
      const list = this.submissions[phase] ?? [];
      const idx = list.findIndex((s) => s.id === submissionId);
      if (idx < 0) return;
      const target = list[idx];
      // Reset graded_at so the UI shows the "採点中" state and
      // pollUntilGraded / pollSubmissionById short-circuits resume the
      // updated cycle.
      const updated: Submission = { ...target, graded_at: null };
      const newList = [...list];
      newList[idx] = updated;
      this.submissions[phase] = newList;
    },

    _replaceSubmission(phase: number, submission: Submission) {
      const list = this.submissions[phase] ?? [];
      const idx = list.findIndex((s) => s.id === submission.id);
      if (idx < 0) {
        this.submissions[phase] = [...list, submission].sort(
          (a, b) => a.task_no - b.task_no,
        );
        return;
      }
      const newList = [...list];
      newList[idx] = submission;
      this.submissions[phase] = newList;
    },

    _mergeAttempt(
      phase: number,
      submissionId: string,
      attempt: GradingAttempt,
    ) {
      const list = this.submissions[phase] ?? [];
      const idx = list.findIndex((s) => s.id === submissionId);
      if (idx < 0) return;
      const target = list[idx];
      const updated: Submission = {
        ...target,
        score: attempt.status === 'graded' ? attempt.score : target.score,
        ai_feedback:
          attempt.status === 'graded'
            ? attempt.feedback
            : `採点エラー: ${attempt.error_message ?? 'unknown'}`,
        graded_at: attempt.created_at,
        grading_history: [attempt, ...target.grading_history],
      };
      const newList = [...list];
      newList[idx] = updated;
      this.submissions[phase] = newList;
    },

    _noteCooldownIfGraded(submission: Submission) {
      const latest = submission.grading_history[0];
      if (latest && latest.status === 'graded') {
        this.cooldownUntil[submission.id] = Date.now() + 60_000;
      }
    },

    getPhase(phaseNo: number): PhaseSummary | undefined {
      return this.phases.find((p) => p.phase === phaseNo);
    },
  },
});
