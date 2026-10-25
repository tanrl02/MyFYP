import type { PatientNotification } from "@smart-skin/shared";

export const notificationFilterLabels = { all: "All", unread: "Unread", read: "Read" } as const;
export type NotificationFilter = keyof typeof notificationFilterLabels;
export const notificationTypeLabels = {
  all: "All types",
  appointment_reminder: "Appointment reminders",
  queue_called: "Queue calls",
  review_published: "Doctor reviews",
  follow_up_recommended: "Follow-up recommendations",
  bill_ready: "Bills",
} as const;
export type NotificationType = keyof typeof notificationTypeLabels;

export function filterNotifications(items: PatientNotification[], status: NotificationFilter, type: NotificationType = "all", query = ""): PatientNotification[] {
  const search = query.trim().toLowerCase();
  return items.filter(item => (type === "all" || item.kind === type) && (status === "all" || (status === "unread" ? !item.read_at : !!item.read_at)) && (!search || item.title.toLowerCase().includes(search) || item.message.toLowerCase().includes(search)));
}
