import { defineStore } from 'pinia';
import { api } from '@/lib/api';
import type {
  AdminCurriculumCourseDetail,
  AdminCurriculumCourseSummary,
  AdminPhasePatch,
  AdminTaskPatch,
} from '@/types/admin_curriculum';

interface PendingTimer {
  timer: ReturnType<typeof setTimeout>;
  lastPayload: AdminPhasePatch | AdminTaskPatch;
}

const DEBOUNCE_MS = 500;

interface State {
  list: AdminCurriculumCourseSummary[];
  detail: AdminCurriculumCourseDetail | null;
  saveError: string | null;
  pending: Record<string, PendingTimer>;
}

function phaseKey(slug: string, phaseNo: number): string {
  return `phase:${slug}:${phaseNo}`;
}
function taskKey(slug: string, phaseNo: number, taskNo: number): string {
  return `task:${slug}:${phaseNo}:${taskNo}`;
}

export const useAdminCurriculumStore = defineStore('admin_curriculum', {
  state: (): State => ({
    list: [],
    detail: null,
    saveError: null,
    pending: {},
  }),
  actions: {
    async fetchList() {
      const res = await api.adminCurriculumList();
      this.list = res.items;
    },

    async fetchDetail(slug: string) {
      this.detail = await api.adminCurriculumDetail(slug);
    },

    putPhase(slug: string, phaseNo: number, payload: AdminPhasePatch) {
      const key = phaseKey(slug, phaseNo);
      this._scheduleDebounced(key, payload, async (latest) => {
        try {
          await api.adminPutCurriculumPhase(slug, phaseNo, latest as AdminPhasePatch);
          this.saveError = null;
          await this.fetchDetail(slug);
        } catch (e) {
          this.saveError = e instanceof Error ? e.message : String(e);
        }
      });
    },

    putTask(
      slug: string,
      phaseNo: number,
      taskNo: number,
      payload: AdminTaskPatch,
    ) {
      const key = taskKey(slug, phaseNo, taskNo);
      this._scheduleDebounced(key, payload, async (latest) => {
        try {
          await api.adminPutCurriculumTask(
            slug, phaseNo, taskNo, latest as AdminTaskPatch,
          );
          this.saveError = null;
          await this.fetchDetail(slug);
        } catch (e) {
          this.saveError = e instanceof Error ? e.message : String(e);
        }
      });
    },

    // Sprint 9 follow-up LOW-4: publish の戻り値を view に渡せるように
    // PublishOut を返却し、view が「公開件数」message を出せるようにする。
    // 旧実装は void を返していたので view が api を直接叩いていた。
    async publish(slug: string) {
      const result = await api.adminPublishCurriculum(slug);
      await this.fetchDetail(slug);
      return result;
    },

    async discardDrafts(slug: string) {
      await api.adminDiscardCurriculumDrafts(slug);
      await this.fetchDetail(slug);
    },

    async addTask(slug: string, phaseNo: number) {
      try {
        await api.adminAddCurriculumTask(slug, phaseNo);
        this.saveError = null;
        await this.fetchDetail(slug);
      } catch (e) {
        this.saveError = e instanceof Error ? e.message : String(e);
        throw e;
      }
    },

    async deleteTask(slug: string, phaseNo: number, taskNo: number) {
      try {
        await api.adminDeleteCurriculumTask(slug, phaseNo, taskNo);
        this.saveError = null;
        await this.fetchDetail(slug);
      } catch (e) {
        this.saveError = e instanceof Error ? e.message : String(e);
        throw e;
      }
    },

    async moveTask(
      slug: string,
      phaseNo: number,
      taskNo: number,
      toTaskNo: number,
    ) {
      try {
        await api.adminMoveCurriculumTask(slug, phaseNo, taskNo, {
          to_task_no: toTaskNo,
        });
        this.saveError = null;
        await this.fetchDetail(slug);
      } catch (e) {
        this.saveError = e instanceof Error ? e.message : String(e);
        throw e;
      }
    },

    async createCourse(payload: {
      slug: string;
      title: string;
      description?: string | null;
    }) {
      try {
        const result = await api.adminCreateCurriculumCourse(payload);
        this.saveError = null;
        await this.fetchList();
        return result;
      } catch (e) {
        this.saveError = e instanceof Error ? e.message : String(e);
        throw e;
      }
    },

    async deleteCourse(slug: string) {
      try {
        await api.adminDeleteCurriculumCourse(slug);
        this.saveError = null;
        await this.fetchList();
      } catch (e) {
        this.saveError = e instanceof Error ? e.message : String(e);
        throw e;
      }
    },

    async addPhase(slug: string) {
      try {
        await api.adminAddCurriculumPhase(slug);
        this.saveError = null;
        await this.fetchDetail(slug);
      } catch (e) {
        this.saveError = e instanceof Error ? e.message : String(e);
        throw e;
      }
    },

    async deletePhase(slug: string, phaseNo: number) {
      try {
        await api.adminDeleteCurriculumPhase(slug, phaseNo);
        this.saveError = null;
        await this.fetchDetail(slug);
      } catch (e) {
        this.saveError = e instanceof Error ? e.message : String(e);
        throw e;
      }
    },

    async movePhase(slug: string, phaseNo: number, toPhaseNo: number) {
      try {
        await api.adminMoveCurriculumPhase(slug, phaseNo, {
          to_phase_no: toPhaseNo,
        });
        this.saveError = null;
        await this.fetchDetail(slug);
      } catch (e) {
        this.saveError = e instanceof Error ? e.message : String(e);
        throw e;
      }
    },

    _scheduleDebounced(
      key: string,
      payload: AdminPhasePatch | AdminTaskPatch,
      fire: (latest: AdminPhasePatch | AdminTaskPatch) => Promise<void>,
    ) {
      const existing = this.pending[key];
      const merged = { ...(existing?.lastPayload ?? {}), ...payload };
      if (existing) {
        clearTimeout(existing.timer);
      }
      const timer = setTimeout(() => {
        delete this.pending[key];
        void fire(merged);
      }, DEBOUNCE_MS);
      this.pending[key] = { timer, lastPayload: merged };
    },
  },
});
