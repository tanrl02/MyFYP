export type Status = "waiting" | "called" | "completed" | "cancelled";
export type ConsultationNote = { id: string; booking_id: string; doctor_id: DemoDoctor; findings: string; follow_up: string; created_at: string };
export type Consultation = { visit: Booking; note: ConsultationNote | null; linked_share: AssessmentShare | null };
export type DemoPatient = "patient-ava" | "patient-noah";
export type DemoActor = DemoPatient | "staff-demo" | "doctor-lim" | "doctor-anita";
export type Medicine = { id: string; name: string; price_cents: number; stock: number };
export type Assessment = { id: string; patient_id: DemoPatient; width: number; height: number; created_at: string; origin: "simulation"; example_category: string; message: string; photo_uri?: string };
export type DemoDoctor = "doctor-lim" | "doctor-anita";
export const doctorNames: Record<DemoDoctor, string> = { "doctor-lim": "Dr. Lim (demo)", "doctor-anita": "Dr. Anita (demo)" };
export type AssessmentReview = { id: string; share_id: string; doctor_id: DemoDoctor; note: string; follow_up: string; created_at: string };
export type AssessmentShare = { id: string; assessment_id: string; patient_id: DemoPatient; patient_name: string; doctor_id: DemoDoctor; doctor_name: string; patient_message: string; request_id: string; created_at: string; revoked_at: string | null; review: AssessmentReview | null; assessment?: Assessment; booking_id: string | null; visit: Booking | null };
export type PrescriptionItem = { medicine_id: string; quantity: number; directions: string };
export type Prescription = { id: string; booking_id: string; doctor_id: string; status: "issued" | "dispensed"; created_at: string; dispensed_at: string | null; items: (PrescriptionItem & { name: string; price_cents: number })[] };
export type Invoice = { id: string; booking_id: string; total_cents: number; status: "unpaid" | "paid"; paid_at: string | null; payment_mode: "simulation" | null; lines: { description: string; quantity: number; unit_price_cents: number }[] };
export type Care = { visit: Booking; prescription: Prescription | null; invoice: Invoice | null };
export const money = (cents: number) => `RM ${(cents / 100).toFixed(2)}`;
export type Slot = { id: string; doctor_id: string; doctor_name: string; starts_at: string; clinic_date: string; capacity: number; available: number };
export type Booking = { id: string; patient_id: DemoPatient; patient_name: string; slot_id: string; queue_number: number; status: Status; doctor_id: string; doctor_name: string; starts_at: string; clinic_date: string; created_at: string };
export const patientNames: Record<DemoPatient, string> = { "patient-ava": "Ava Demo", "patient-noah": "Noah Demo" };
export const statusLabels: Record<Status, string> = { waiting: "Waiting", called: "Called — please approach the counter", completed: "Completed", cancelled: "Cancelled" };
export const queueToken = (booking: Booking) => `${booking.doctor_id === "doctor-lim" ? "L" : "A"}${String(booking.queue_number).padStart(3, "0")}`;
export const visitTime = (iso: string) => new Date(iso).toLocaleString("en-MY", { timeZone: "Asia/Kuala_Lumpur", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });

export class DemoApi {
  constructor(private baseUrl: string, private actor: DemoActor) {}
  private async request<T>(path: string, body?: object | FormData): Promise<T> {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    try {
      const response = await fetch(`${this.baseUrl.replace(/\/$/, "")}${path}`, {
        method: body ? "POST" : "GET", signal: controller.signal,
        headers: { ...(body instanceof FormData ? {} : { "Content-Type": "application/json" }), "X-Demo-Actor": this.actor },
        ...(body ? { body: body instanceof FormData ? body : JSON.stringify(body) } : {}),
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
  care() { return this.request<Care[]>("/care"); }
  consultations() { return this.request<Consultation[]>("/consultations"); }
  consultation(id: string) { return this.request<Consultation>(`/visits/${encodeURIComponent(id)}/consultation`); }
  publishConsultation(id: string, findings: string, followUp: string) { return this.request<Consultation>(`/visits/${encodeURIComponent(id)}/consultation`, { findings, follow_up: followUp }); }
  assessments() { return this.request<Assessment[]>("/assessments"); }
  assessment(id: string) { return this.request<Assessment>(`/assessments/${encodeURIComponent(id)}`); }
  saveAssessment(body: FormData) { return this.request<Assessment>("/assessments", body); }
  shares() { return this.request<AssessmentShare[]>("/assessment-shares"); }
  shareAssessment(id: string, doctor: DemoDoctor, message: string, requestId: string) { return this.request<AssessmentShare>(`/assessments/${encodeURIComponent(id)}/share`, { doctor_id: doctor, patient_message: message, request_id: requestId }); }
  revokeShare(id: string) { return this.request<AssessmentShare>(`/assessment-shares/${encodeURIComponent(id)}/revoke`, {}); }
  linkAssessment(id: string, booking: string, message: string, requestId: string) { return this.request<AssessmentShare>(`/assessments/${encodeURIComponent(id)}/link-appointment`, { booking_id: booking, patient_message: message, request_id: requestId }); }
  sharedAssessment(id: string) { return this.request<AssessmentShare>(`/assessment-shares/${encodeURIComponent(id)}`); }
  publishReview(id: string, note: string, followUp: string) { return this.request<AssessmentShare>(`/assessment-shares/${encodeURIComponent(id)}/review`, { note, follow_up: followUp }); }
  medicines() { return this.request<Medicine[]>("/medicines"); }
  prescribe(id: string, items: PrescriptionItem[]) { return this.request<Prescription>(`/visits/${encodeURIComponent(id)}/prescription`, {items}); }
  dispense(id: string) { return this.request<Prescription>(`/prescriptions/${encodeURIComponent(id)}/dispense`, {}); }
  invoice(id: string) { return this.request<Invoice>(`/visits/${encodeURIComponent(id)}/invoice`, {}); }
  paySimulated(id: string) { return this.request<Invoice>(`/invoices/${encodeURIComponent(id)}/pay-simulated`, {}); }
}
