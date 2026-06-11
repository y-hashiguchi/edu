/**
 * Sprint 4 notification DTOs.
 *
 * Mirrors `backend/app/schemas/notification.py`. `link` is free-form by
 * design — the frontend decides at click time whether to resolve it as
 * an internal Vue Router path or as an external URL.
 */

export interface NotificationOut {
  id: string;
  recipient_user_id: string;
  sender_user_id: string;
  sender_name: string;
  title: string;
  body: string;
  link: string | null;
  course_id?: string | null;
  /** ISO-8601; null until the learner marks it read. */
  read_at: string | null;
  created_at: string;
}

export interface NotificationListOut {
  /** Capped at server-side `notification_poll_limit` (default 50). */
  items: NotificationOut[];
  /**
   * True total of unread rows for this recipient. Use this for the
   * bell-badge count — it stays accurate even when `items` is truncated.
   */
  unread_count: number;
}

export interface NotificationCreatePayload {
  recipient_user_id: string;
  title: string;
  body: string;
  link: string | null;
}

export interface AdminNotificationListOut {
  items: NotificationOut[];
}

export interface BroadcastNotificationCreatePayload {
  course_slug: string;
  title: string;
  body: string;
  link: string | null;
}

export interface BroadcastNotificationOut {
  course_slug: string;
  sent_count: number;
  skipped_inbox_full: number;
  skipped_admin: number;
}
