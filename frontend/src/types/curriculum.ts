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
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}
