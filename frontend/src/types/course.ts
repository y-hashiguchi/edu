/**
 * Sprint 7 course DTOs.
 *
 * Mirrors `backend/app/schemas/course.py`. Field names and casing match
 * the server payload so JSON.parse output is assignable without a
 * mapping layer.
 */

export interface CourseCatalogItem {
  slug: string;
  title: string;
  description: string | null;
  sort_order: number;
}

export interface CourseCatalogResponse {
  items: CourseCatalogItem[];
}

export type EnrollmentStatus = 'active' | 'paused' | 'completed';

export interface MyCourseItem {
  slug: string;
  title: string;
  description: string | null;
  status: EnrollmentStatus;
}

export interface MyCoursesResponse {
  items: MyCourseItem[];
}

/**
 * Admin-facing enrollment projection — matches
 * `backend/app/schemas/course.py::EnrollmentOut`.
 */
export interface EnrollmentOut {
  course_slug: string;
  course_title: string;
  status: EnrollmentStatus;
  enrolled_at: string;
}
