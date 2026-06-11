/**
 * Sprint 7 course store.
 *
 * Holds:
 *   - activeSlug: the course the learner is currently looking at, persisted
 *     in localStorage so a hard reload of /courses/:slug/* survives.
 *   - myCourses: the learner's enrolled courses (status=active/paused/...)
 *     used to render /courses.
 *   - catalog: the full public course catalog used by /login (register)
 *     and the "additional courses" hint on /courses.
 *
 * Pinia's persist plugin is intentionally NOT used here — only the active
 * slug round-trips through localStorage, and the slug needs to be readable
 * during router guard execution (synchronous, before stores hydrate from
 * persisted state). Reading/writing localStorage by hand keeps the access
 * pattern explicit.
 */

import { defineStore } from 'pinia';

import { api } from '@/lib/api';
import type {
  CourseCatalogItem,
  MyCourseItem,
} from '@/types/course';

const STORAGE_KEY = 'ai-tutor.activeCourse';

interface State {
  activeSlug: string | null;
  myCourses: MyCourseItem[];
  catalog: CourseCatalogItem[];
  /** True once fetchMyCourses has completed at least once. */
  loaded: boolean;
}

export const useCourseStore = defineStore('course', {
  state: (): State => ({
    activeSlug: null,
    myCourses: [],
    catalog: [],
    loaded: false,
  }),
  getters: {
    isEnrolled: (s) => (slug: string) =>
      s.myCourses.some((c) => c.slug === slug),
  },
  actions: {
    setActiveCourse(slug: string) {
      this.activeSlug = slug;
      try {
        localStorage.setItem(STORAGE_KEY, slug);
      } catch {
        // localStorage may be unavailable (private mode / SSR). Failing
        // to persist is non-fatal — the active slug still lives in
        // store state for the rest of the session.
      }
    },

    hydrateActiveFromStorage() {
      try {
        const slug = localStorage.getItem(STORAGE_KEY);
        if (slug) this.activeSlug = slug;
      } catch {
        // ignore
      }
    },

    async fetchMyCourses() {
      const res = await api.listMyCourses();
      this.myCourses = res.items;
      this.loaded = true;
      // If no course is active yet but the learner is enrolled in
      // exactly one course (or multiple), default to the first one
      // sorted by the backend. The router still allows explicit
      // navigation to override this.
      if (!this.activeSlug && res.items.length > 0) {
        this.setActiveCourse(res.items[0].slug);
      }
    },

    async fetchCatalog() {
      const res = await api.listCourseCatalog();
      this.catalog = [...res.items].sort(
        (a, b) => a.sort_order - b.sort_order,
      );
    },

    /**
     * On logout we should clear everything so the next user doesn't
     * inherit the previous learner's active course slug.
     */
    reset() {
      this.activeSlug = null;
      this.myCourses = [];
      this.catalog = [];
      this.loaded = false;
      try {
        localStorage.removeItem(STORAGE_KEY);
      } catch {
        // ignore
      }
    },
  },
});
