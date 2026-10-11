export type Status = "waiting" | "called" | "completed" | "cancelled";
export type DemoPatient = "patient-ava" | "patient-noah";
export type DemoActor = DemoPatient | "staff-demo";
export type Slot = { id: string; doctor_id: string; doctor_name: string; starts_at: string; clinic_date: string; capacity: number; available: number };
export type Booking = { id: string; patient_id: DemoPatient; patient_name: string; slot_id: string; queue_number: number; status: Status; doctor_id: string; doctor_name: string; starts_at: string; clinic_date: string; created_at: string };
export const patientNames: Record<DemoPatient, string> = { "patient-ava": "Ava Demo", "patient-noah": "Noah Demo" };
export const statusLabels: Record<Status, string> = { waiting: "Waiting", called: "Called — please approach the counter", completed: "Completed", cancelled: "Cancelled" };
export const queueToken = (booking: Booking) => `${booking.doctor_id === "doctor-lim" ? "L" : "A"}${String(booking.queue_number).padStart(3, "0")}`;
export const visitTime = (iso: string) => new Date(iso).toLocaleString("en-MY", { timeZone: "Asia/Kuala_Lumpur", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });

export class DemoApi {
  constructor(private baseUrl: string, private actor: DemoActor) {}
  private async request<T>(path: string, body?: object): Promise<T> {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    try {
      const response = await fetch(`${this.baseUrl.replace(/\/$/, "")}${path}`, {
        method: body ? "POST" : "GET", signal: controller.signal,
        headers: { "Content-Type": "application/json", "X-Demo-Actor": this.actor },
        ...(body ? { body: JSON.stringify(body) } : {}),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Please check your inputs and try again.");
      return data as T;
    } catch (error) {
      if (error instanceof Error && error.name === "AbortError") throw new Error("The server took too long. Refresh to check whether your change was saved before retrying.");
      if (error instanceof TypeError) throw new Error("Cannot reach the demo API. Check that it is running and the API address is correct.");
      throw error;
    } finally { clearTimeout(timeout); }
  }
  slots() { return this.request<Slot[]>("/slots"); }
  bookings() { return this.request<Booking[]>("/bookings"); }
  book(slotId: string, requestId: string) { return this.request<Booking>("/bookings", { slot_id: slotId, request_id: requestId }); }
  cancel(id: string) { return this.request<Booking>(`/bookings/${encodeURIComponent(id)}/cancel`, {}); }
  queue(doctor: string, date: string) { return this.request<Booking[]>(`/queue?doctor_id=${encodeURIComponent(doctor)}&clinic_date=${encodeURIComponent(date)}`); }
  callNext(doctor: string, date: string) { return this.request<Booking>("/queue/call-next", { doctor_id: doctor, clinic_date: date }); }
  complete(id: string) { return this.request<Booking>(`/queue/${encodeURIComponent(id)}/complete`, {}); }
}
