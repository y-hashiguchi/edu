export interface ProgressSummary {
  completed_tasks: number;
  total_tasks: number;
  submission_count: number;
  average_score: number | null;
}

export interface TagAverage {
  tag: string;
  average_score: number;
  submission_count: number;
}

export interface Weakness {
  has_enough_data: boolean;
  top_weaknesses: TagAverage[];
}

export interface RecommendationItem {
  phase: number;
  task_no: number;
  title: string;
  skill_tags: string[];
  match_tag: string | null;
  rag_score: number;
}

export interface RecommendationsBlock {
  items: RecommendationItem[];
}

export interface Nudge {
  body: string;
  generated_at: string;
  is_fresh: boolean;
}

export interface DashboardResponse {
  progress_summary: ProgressSummary;
  weakness: Weakness;
  recommendations: RecommendationsBlock;
  nudge: Nudge;
}
