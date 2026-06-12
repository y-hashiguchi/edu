export type PhaseStatus = 'locked' | 'in_progress' | 'submitted' | 'completed';

export interface PhaseSummary {
  phase: number;
  title: string;
  goal: string;
  duration: string;
  skills: string[];
  tasks: string[];
  locked: boolean;
  status: PhaseStatus;
}

export interface ProgressOut {
  phase: number;
  status: PhaseStatus;
  started_at: string | null;
  completed_at: string | null;
}

export interface ProgressCompleteResponse extends ProgressOut {
  next_unlocked: ProgressOut | null;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface ChatResponse {
  reply: string;
  history: ChatMessage[];
}

export interface UserOut {
  id: string;
  email: string;
  name: string;
  created_at: string;
  /** Sprint 4: surfaced by /api/auth/me so the SPA can route admin views. */
  is_admin: boolean;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

// Sprint 8 follow-up: 'pending' is an ephemeral wire value returned by
// the async regrade path. The DB never stores it (CHECK constraint
// forbids it); the frontend sees it as a signal that polling should
// begin and there is no real grading_attempt to merge yet.
export type GradingAttemptStatus = 'graded' | 'failed' | 'pending';

export interface GradingAttempt {
  id: string;
  status: GradingAttemptStatus;
  score: number | null;
  feedback: string | null;
  error_message: string | null;
  model_name: string;
  created_at: string;
}

export interface SubmissionFile {
  id: string;
  filename: string;
  mime_type: string;
  size_bytes: number;
  created_at: string;
}

export interface Submission {
  id: string;
  phase: number;
  task_no: number;
  content: string;
  ai_feedback: string | null;
  score: number | null;
  submitted_at: string;
  graded_at: string | null;
  files: SubmissionFile[];
  grading_history: GradingAttempt[];
}
