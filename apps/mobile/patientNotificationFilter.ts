import type { PatientNotification } from "@smart-skin/shared";

export const notificationFilterLabels = { all: "All", unread: "Unread", read: "Read" } as const;
export type NotificationFilter = keyof typeof notificationFilterLabels;

export function filterNotifications(items: PatientNotification[], status: NotificationFilter): PatientNotification[] {
  return items.filter(item => status === "all" || (status === "unread" ? !item.read_at : !!item.read_at));
}
