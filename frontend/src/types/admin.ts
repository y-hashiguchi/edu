/**
 * Sprint 4 admin DTOs.
 *
 * Mirrors `backend/app/schemas/admin.py`. Naming and casing match the
 * server payload exactly so JSON.parse output is assignable without a
 * mapping layer.
 */

import type { GradingAttempt, ProgressOut, SubmissionFile } from './curriculum';

export interface AdminUserSummary {
  id: string;
  email: string;
  name: string;
  created_at: string;
  is_admin: boolean;
  completed_phases: number;
  in_progress_phases: number;
}

export interface AdminUserListOut {
  items: AdminUserSummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface AdminUserDetail {
  id: string;
  email: string;
  name: string;
  created_at: string;
  is_admin: boolean;
  progress: ProgressOut[];
  /**
   * Phase number (as string key, since JSON object keys cannot be int)
   * mapped to the latest graded score, or null when the learner has no
   * graded submission on that phase yet. Keys 1..4 are always present.
   */
  latest_scores: Record<string, number | null>;
}

export interface AdminSubmissionSummary {
  id: string;
  user_id: string;
  user_email: string;
  user_name: string;
  phase: number;
  task_no: number;
  score: number | null;
  submitted_at: string;
  graded_at: string | null;
}

export interface AdminSubmissionListOut {
  items: AdminSubmissionSummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface AdminCommentOut {
  id: string;
  submission_id: string;
  author_user_id: string;
  author_name: string;
  body: string;
  created_at: string;
  updated_at: string;
}

export interface AdminSubmissionDetail {
  id: string;
  user_id: string;
  user_email: string;
  user_name: string;
  phase: number;
  task_no: number;
  content: string;
  score: number | null;
  ai_feedback: string | null;
  submitted_at: string;
  graded_at: string | null;
  files: SubmissionFile[];
  grading_history: GradingAttempt[];
  comments: AdminCommentOut[];
}

export interface CommentCreatePayload {
  body: string;
}

/**
 * Learner-facing comment projection. Intentionally omits
 * `author_user_id` to mirror `backend/app/schemas/comment.py`.
 */
export interface LearnerCommentOut {
  id: string;
  author_name: string;
  body: string;
  created_at: string;
}

export interface AdminSubmissionListFilters {
  user_id?: string;
  phase?: number;
  limit?: number;
  offset?: number;
}
