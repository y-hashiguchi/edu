// Sprint 9 — admin curriculum editing DTOs (mirror backend schemas).

export interface AdminCurriculumCourseSummary {
  slug: string;
  title: string;
  pending_draft_count: number;
}

export interface AdminCurriculumCourseList {
  items: AdminCurriculumCourseSummary[];
}

export interface AdminTaskEditOut {
  task_no: number;
  title: string;
  description: string;
  skill_tags: string[];
  deliverable: string | null;
  week_label: string | null;
  draft_title: string | null;
  draft_description: string | null;
  draft_skill_tags: string[] | null;
  draft_deliverable: string | null;
  draft_week_label: string | null;
  updated_at: string;
}

export interface AdminPhaseEditOut {
  phase_no: number;
  title: string;
  goal: string;
  system_prompt: string;
  draft_title: string | null;
  draft_goal: string | null;
  draft_system_prompt: string | null;
  tasks: AdminTaskEditOut[];
  updated_at: string;
}

export interface AdminCurriculumCourseDetail {
  slug: string;
  title: string;
  phases: AdminPhaseEditOut[];
}

export interface AdminCurriculumPublishOut {
  slug: string;
  published_phase_count: number;
  published_task_count: number;
  published_at: string;
}

// Request bodies — exclude_unset semantics. クライアント側は変更したい field
// だけを payload に含める (省略 = 変更なし、明示 null = draft クリア、値 = draft 設定)。
export interface AdminPhasePatch {
  title?: string | null;
  goal?: string | null;
  system_prompt?: string | null;
}

export interface AdminTaskPatch {
  title?: string | null;
  description?: string | null;
  skill_tags?: string[] | null;
  deliverable?: string | null;
  week_label?: string | null;
}
