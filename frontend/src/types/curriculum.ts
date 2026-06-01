export interface PhaseSummary {
  phase: number;
  title: string;
  goal: string;
  duration: string;
  skills: string[];
  tasks: string[];
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface ChatResponse {
  reply: string;
  history: ChatMessage[];
}
