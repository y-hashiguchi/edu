export interface StuckLearner {
  user_id: string;
  display_name: string;
  email_masked: string;
  last_activity_at: string | null;
  current_phase: number;
  submission_count: number;
  reason: 'no_submissions' | 'inactive_7d';
}

export interface TagHeatmapEntry {
  tag: string;
  average_score: number;
  submission_count: number;
}

export interface AdminCohortSummary {
  course_slug: string;
  course_title: string;
  enrolled_count: number;
  average_score: number | null;
  completion_rate: number;
  stuck_learners: StuckLearner[];
  tag_heatmap: TagHeatmapEntry[];
  cohort_label: string | null;
}

export interface AdminCohortLabels {
  items: string[];
}
