import type {
  ChatMessage,
  ChatResponse,
  GradingAttempt,
  PhaseSummary,
  ProgressCompleteResponse,
  ProgressOut,
  Submission,
} from '@/types/curriculum';
import type {
  AdminCommentOut,
  AdminDashboardResponse,
  AdminSubmissionDetail,
  AdminSubmissionListFilters,
  AdminSubmissionListOut,
  AdminUserDetail,
  AdminUserListOut,
  CommentCreatePayload,
  LearnerCommentOut,
} from '@/types/admin';
import type {
  AdminNotificationListOut,
  BroadcastNotificationCreatePayload,
  BroadcastNotificationOut,
  NotificationCreatePayload,
  NotificationListOut,
  NotificationOut,
} from '@/types/notification';
import type { EnrollmentOut } from '@/types/course';
import type { DashboardResponse } from '@/types/dashboard';
import type {
  CourseCatalogResponse,
  MyCoursesResponse,
} from '@/types/course';

const baseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

let _onUnauthorized: (() => void) | null = null;
let _tokenGetter: (() => string | null) | null = null;

export function registerUnauthorizedHandler(cb: () => void) {
  _onUnauthorized = cb;
}

export function registerTokenGetter(getter: () => string | null) {
  _tokenGetter = getter;
}

function getToken(): string | null {
  if (_tokenGetter) return _tokenGetter();
  try {
    const persisted = localStorage.getItem('auth');
    if (!persisted) return null;
    return (JSON.parse(persisted) as { token: string | null }).token;
  } catch {
    return null;
  }
}

export class ApiCooldownError extends Error {
  constructor(public retryAfterSeconds: number) {
    super(`cooldown active; retry in ${retryAfterSeconds}s`);
    this.name = 'ApiCooldownError';
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (response.status === 401) {
    if (_onUnauthorized) _onUnauthorized();
    throw new Error('API 401: Unauthorized');
  }
  if (response.status === 429) {
    const retryAfter = Number(response.headers.get('Retry-After') ?? '60');
    throw new ApiCooldownError(Number.isFinite(retryAfter) ? retryAfter : 60);
  }
  if (!response.ok) {
    throw new Error(`API ${response.status}: ${await response.text()}`);
  }
  return response.json() as Promise<T>;
}

export async function rawRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken();
  const headers = new Headers(init?.headers);
  headers.set('Content-Type', 'application/json');
  if (token) headers.set('Authorization', `Bearer ${token}`);

  const response = await fetch(`${baseUrl}${path}`, { ...init, headers });
  return handleResponse<T>(response);
}

async function multipartRequest<T>(
  path: string,
  formData: FormData,
  method: 'POST' = 'POST',
): Promise<T> {
  const token = getToken();
  const headers = new Headers();
  if (token) headers.set('Authorization', `Bearer ${token}`);
  // Do NOT set Content-Type; the browser sets it with a multipart boundary.

  const response = await fetch(`${baseUrl}${path}`, {
    method,
    headers,
    body: formData,
  });
  return handleResponse<T>(response);
}

export interface SubmitTaskPayload {
  phase: number;
  task_no: number;
  content: string;
  files: File[];
}

/**
 * Sprint 7: every course-scoped endpoint accepts `?course={slug}`.
 * Centralising the encoding here means a single place to audit /
 * change if the backend ever moves the parameter to a header or to
 * a path segment.
 *
 * `extra` lets callers fold this query string into a URL that already
 * has other params (e.g. admin submission filters).
 */
export function withCourse(slug: string, extra?: URLSearchParams): string {
  const params = new URLSearchParams(extra ?? undefined);
  params.set('course', slug);
  return `?${params.toString()}`;
}

export const api = {
  // ---- Sprint 7 course catalog + enrolled-course listing ----

  listCourseCatalog: () =>
    rawRequest<CourseCatalogResponse>('/api/courses/catalog'),

  listMyCourses: () => rawRequest<MyCoursesResponse>('/api/courses'),

  listPhases: (courseSlug: string) =>
    rawRequest<PhaseSummary[]>(`/api/curriculum/phases${withCourse(courseSlug)}`),

  listProgress: (courseSlug: string) =>
    rawRequest<ProgressOut[]>(`/api/progress${withCourse(courseSlug)}`),

  completePhase: (phase: number, courseSlug: string) =>
    rawRequest<ProgressCompleteResponse>(
      `/api/progress/${phase}/complete${withCourse(courseSlug)}`,
      { method: 'POST' },
    ),

  getChatHistory: (phase: number, courseSlug: string) =>
    rawRequest<ChatMessage[]>(
      `/api/chat/history/${phase}${withCourse(courseSlug)}`,
    ),

  sendChat: (payload: { phase: number; message: string }, courseSlug: string) =>
    rawRequest<ChatResponse>(`/api/chat${withCourse(courseSlug)}`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  listSubmissions: (phase: number, courseSlug: string) =>
    rawRequest<Submission[]>(
      `/api/submissions/${phase}${withCourse(courseSlug)}`,
    ),

  submitTask: (
    payload: SubmitTaskPayload,
    courseSlug: string,
  ): Promise<Submission> => {
    const fd = new FormData();
    fd.append('phase', String(payload.phase));
    fd.append('task_no', String(payload.task_no));
    fd.append('content', payload.content);
    for (const file of payload.files) {
      fd.append('files', file, file.name);
    }
    return multipartRequest<Submission>(
      `/api/submissions${withCourse(courseSlug)}`,
      fd,
    );
  },

  regradeSubmission: (
    submissionId: string,
    courseSlug: string,
  ): Promise<GradingAttempt> =>
    rawRequest<GradingAttempt>(
      `/api/submissions/${submissionId}/regrade${withCourse(courseSlug)}`,
      { method: 'POST' },
    ),

  // Downloads the file body via an authenticated fetch and returns a Blob.
  // A bare <a href> cannot carry the Authorization header, so the download
  // endpoint must be reached programmatically.
  //
  // Sprint 7: the backend's CourseContext dependency requires `?course=`
  // even though the file lookup is keyed by submission_id. Threading the
  // slug here keeps the route consistent with the rest of the API
  // surface.
  downloadFile: async (
    submissionId: string,
    fileId: string,
    courseSlug: string,
  ): Promise<Blob> => {
    const token = getToken();
    const headers = new Headers();
    if (token) headers.set('Authorization', `Bearer ${token}`);
    const response = await fetch(
      `${baseUrl}/api/submissions/${submissionId}/files/${fileId}${withCourse(courseSlug)}`,
      { headers },
    );
    if (response.status === 401) {
      if (_onUnauthorized) _onUnauthorized();
      throw new Error('API 401: Unauthorized');
    }
    if (!response.ok) {
      throw new Error(`Download failed: ${response.status}`);
    }
    return response.blob();
  },

  // ---- Sprint 4 admin endpoints (instructor-only) ----

  adminListUsers: (limit = 50, offset = 0): Promise<AdminUserListOut> =>
    rawRequest<AdminUserListOut>(
      `/api/admin/users?limit=${limit}&offset=${offset}`,
    ),

  adminGetUser: (userId: string): Promise<AdminUserDetail> =>
    rawRequest<AdminUserDetail>(`/api/admin/users/${userId}`),

  adminListSubmissions: (
    filters: AdminSubmissionListFilters = {},
  ): Promise<AdminSubmissionListOut> => {
    const params = new URLSearchParams();
    if (filters.user_id) params.set('user_id', filters.user_id);
    if (filters.phase != null) params.set('phase', String(filters.phase));
    params.set('limit', String(filters.limit ?? 50));
    params.set('offset', String(filters.offset ?? 0));
    return rawRequest<AdminSubmissionListOut>(
      `/api/admin/submissions?${params.toString()}`,
    );
  },

  adminGetSubmission: (id: string): Promise<AdminSubmissionDetail> =>
    rawRequest<AdminSubmissionDetail>(`/api/admin/submissions/${id}`),

  adminListComments: (id: string): Promise<AdminCommentOut[]> =>
    rawRequest<AdminCommentOut[]>(`/api/admin/submissions/${id}/comments`),

  adminPostComment: (
    submissionId: string,
    body: string,
  ): Promise<AdminCommentOut> => {
    const payload: CommentCreatePayload = { body };
    return rawRequest<AdminCommentOut>(
      `/api/admin/submissions/${submissionId}/comments`,
      { method: 'POST', body: JSON.stringify(payload) },
    );
  },

  adminSendNotification: (
    payload: NotificationCreatePayload,
  ): Promise<NotificationOut> =>
    rawRequest<NotificationOut>(`/api/admin/notifications`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  adminBroadcastNotification: (
    payload: BroadcastNotificationCreatePayload,
  ): Promise<BroadcastNotificationOut> =>
    rawRequest(`/api/admin/notifications/broadcast`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  adminEnrollUser: (
    userId: string,
    courseSlug: string,
  ): Promise<EnrollmentOut> =>
    rawRequest(`/api/admin/users/${userId}/enrollments`, {
      method: 'POST',
      body: JSON.stringify({ course_slug: courseSlug }),
    }),

  adminListSentNotifications: (): Promise<AdminNotificationListOut> =>
    rawRequest<AdminNotificationListOut>(`/api/admin/notifications`),

  // ---- Sprint 4 learner-side /api/me endpoints ----

  listMyNotifications: (): Promise<NotificationListOut> =>
    rawRequest<NotificationListOut>(`/api/me/notifications`),

  markNotificationRead: (id: string): Promise<NotificationOut> =>
    rawRequest<NotificationOut>(`/api/me/notifications/${id}/read`, {
      method: 'POST',
    }),

  listMySubmissionComments: (
    submissionId: string,
  ): Promise<LearnerCommentOut[]> =>
    rawRequest<LearnerCommentOut[]>(
      `/api/me/submissions/${submissionId}/comments`,
    ),

  // ---- Sprint 5 personalized dashboard ----

  getMyDashboard: (courseSlug: string) =>
    rawRequest<DashboardResponse>(
      `/api/me/dashboard${withCourse(courseSlug)}`,
    ),

  // ---- Sprint 6 bidirectional comm + admin dashboard ----

  postMyReply: (
    submissionId: string,
    parentId: string,
    body: string,
  ): Promise<LearnerCommentOut> =>
    rawRequest<LearnerCommentOut>(
      `/api/me/submissions/${submissionId}/comments`,
      {
        method: 'POST',
        body: JSON.stringify({ parent_id: parentId, body }),
      },
    ),

  getAdminUserDashboard: (
    userId: string,
    courseSlug: string,
  ): Promise<AdminDashboardResponse> =>
    rawRequest<AdminDashboardResponse>(
      `/api/admin/users/${userId}/dashboard${withCourse(courseSlug)}`,
    ),
};
