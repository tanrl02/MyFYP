export type Status = "waiting" | "called" | "completed" | "cancelled";
export type ConsultationNote = { id: string; booking_id: string; doctor_id: DemoDoctor; findings: string; follow_up: string; created_at: string };
export type PatientBackground = { patient_id: DemoPatient; allergies: string; medicines: string; conditions: string; version: number; updated_at: string | null };
export type Consultation = { visit: Booking; note: ConsultationNote | null; linked_share: AssessmentShare | null; background?: PatientBackground };
export type VisitFeedback = { id: string; booking_id: string; patient_id: DemoPatient; rating: number; comment: string; created_at: string; visit: Booking };
export type DemoPatient = "patient-ava" | "patient-noah";
export type PatientNotification = {id:string;patient_id:DemoPatient;kind:"queue_called"|"review_published";source_id:string;target_id:string;title:string;message:string;created_at:string;read_at:string|null};
export type NotificationInbox = {items:PatientNotification[];unread_count:number};
export type DemoActor = DemoPatient | "staff-demo" | "doctor-lim" | "doctor-anita";
export type Medicine = { id: string; name: string; strength: string; form: string; price_cents: number; stock: number };
export const medicineLabel = (item: Pick<Medicine,"name"|"strength"|"form">) => [item.name,item.strength,item.form].filter(Boolean).join(" · ");
export type StockReceipt = { id: string; medicine_id: string; quantity: number; reason: string; stock_before: number; stock_after: number; actor_id: string; created_at: string; name?: string };
export type StockOverview = { medicines: Medicine[]; receipts: StockReceipt[]; low_stock_threshold: number };
export type DailyReport = { clinic_date: string; timezone: string; generated_at: string; visits: Record<Status | "rescheduled" | "total",number>; billing: { invoice_count: number; billed_cents: number; paid_cents: number; unpaid_cents: number }; stock: { received_units: number; dispensed_units: number; items: { medicine_id: string; name: string; received: number; dispensed: number }[] }; feedback: { count: number; average_rating: number | null } };
export type Assessment = { id: string; patient_id: DemoPatient; width: number; height: number; created_at: string; origin: "simulation"; example_category: string; message: string; photo_uri?: string };
export type DemoDoctor = "doctor-lim" | "doctor-anita";
export const concernLabels = {general:"General skin concerns / not sure",acne:"Acne",eczema:"Eczema",psoriasis:"Psoriasis"};
export type DoctorConcern = keyof typeof concernLabels;
export type DoctorProfile = {doctor_id:DemoDoctor;doctor_name:string;specialty:string;expertise:DoctorConcern[];version:number;updated_at:string|null};
export const doctorNames: Record<DemoDoctor, string> = { "doctor-lim": "Dr. Lim (demo)", "doctor-anita": "Dr. Anita (demo)" };
export type AssessmentReview = { id: string; share_id: string; doctor_id: DemoDoctor; note: string; follow_up: string; created_at: string };
export type AssessmentShare = { id: string; assessment_id: string; patient_id: DemoPatient; patient_name: string; doctor_id: DemoDoctor; doctor_name: string; patient_message: string; request_id: string; created_at: string; revoked_at: string | null; review: AssessmentReview | null; assessment?: Assessment; booking_id: string | null; visit: Booking | null };
export type PrescriptionItem = { medicine_id: string; quantity: number; directions: string };
export type Prescription = { id: string; booking_id: string; doctor_id: string; status: "issued" | "dispensed"; created_at: string; dispensed_at: string | null; items: (PrescriptionItem & Pick<Medicine,"name"|"strength"|"form"|"price_cents">)[] };
export type Invoice = { id: string; booking_id: string; total_cents: number; status: "unpaid" | "paid"; paid_at: string | null; payment_mode: "simulation" | null; lines: { description: string; quantity: number; unit_price_cents: number }[] };
export type Care = { visit: Booking; prescription: Prescription | null; invoice: Invoice | null };
export type VisitDetails = Care & { linked_shares: AssessmentShare[]; note: ConsultationNote | null; feedback: Omit<VisitFeedback,"visit"> | null; replacement: Booking | null };
export const money = (cents: number) => `RM ${(cents / 100).toFixed(2)}`;
export type Slot = { id: string; doctor_id: string; doctor_name: string; starts_at: string; clinic_date: string; capacity: number; available: number };
export type ManagedSlot = Slot & {closed:number;booking_count:number};
export type Booking = { id: string; patient_id: DemoPatient; patient_name: string; slot_id: string; queue_number: number; status: Status; doctor_id: string; doctor_name: string; starts_at: string; clinic_date: string; created_at: string; rescheduled_to_id: string | null };
export const patientNames: Record<DemoPatient, string> = { "patient-ava": "Ava Demo", "patient-noah": "Noah Demo" };
export const statusLabels: Record<Status, string> = { waiting: "Waiting", called: "Called — please approach the counter", completed: "Completed", cancelled: "Cancelled" };
export const queueToken = (booking: Booking) => `${booking.doctor_id === "doctor-lim" ? "L" : "A"}${String(booking.queue_number).padStart(3, "0")}`;
export const visitTime = (iso: string) => new Date(iso).toLocaleString("en-MY", { timeZone: "Asia/Kuala_Lumpur", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });

export class DemoApi {
  doctors() { return this.request<DoctorProfile[]>("/doctors"); }
  saveDoctor(id:DemoDoctor,body:Pick<DoctorProfile,"specialty"|"expertise"|"version">) { return this.request<DoctorProfile>(`/staff/doctors/${encodeURIComponent(id)}`,body); }
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
  managedSlots() { return this.request<ManagedSlot[]>("/staff/slots"); }
  addSlot(body:{doctor_id:DemoDoctor;clinic_date:string;time:string;capacity:number;request_id:string}) { return this.request<ManagedSlot>("/staff/slots",body); }
  closeSlot(id:string) { return this.request<ManagedSlot>(`/staff/slots/${encodeURIComponent(id)}/close`,{}); }
  bookings() { return this.request<Booking[]>("/bookings"); }
  notifications() { return this.request<NotificationInbox>("/notifications"); }
  readNotification(id:string) { return this.request<PatientNotification>(`/notifications/${encodeURIComponent(id)}/read`,{}); }
  visitDetails(id: string) { return this.request<VisitDetails>(`/bookings/${encodeURIComponent(id)}/details`); }
  book(slotId: string, requestId: string) { return this.request<Booking>("/bookings", { slot_id: slotId, request_id: requestId }); }
  counterBook(patient: DemoPatient, slotId: string, requestId: string) { return this.request<Booking>("/counter-bookings", { patient_id: patient, slot_id: slotId, request_id: requestId }); }
  cancel(id: string) { return this.request<Booking>(`/bookings/${encodeURIComponent(id)}/cancel`, {}); }
  reschedule(id: string, slotId: string, requestId: string) { return this.request<Booking>(`/bookings/${encodeURIComponent(id)}/reschedule`, {slot_id:slotId,request_id:requestId}); }
  queue(doctor: string, date: string) { return this.request<Booking[]>(`/queue?doctor_id=${encodeURIComponent(doctor)}&clinic_date=${encodeURIComponent(date)}`); }
  callNext(doctor: string, date: string) { return this.request<Booking>("/queue/call-next", { doctor_id: doctor, clinic_date: date }); }
  complete(id: string) { return this.request<Booking>(`/queue/${encodeURIComponent(id)}/complete`, {}); }
  care() { return this.request<Care[]>("/care"); }
  consultations() { return this.request<Consultation[]>("/consultations"); }
  background() { return this.request<PatientBackground>("/patient-background"); }
  saveBackground(body: Pick<PatientBackground,"allergies"|"medicines"|"conditions"|"version">) { return this.request<PatientBackground>("/patient-background",body); }
  feedback() { return this.request<VisitFeedback[]>("/feedback"); }
  submitFeedback(id: string,rating: number,comment: string) { return this.request<VisitFeedback>(`/visits/${encodeURIComponent(id)}/feedback`,{rating,comment}); }
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
  addMedicine(body: Pick<Medicine,"name"|"strength"|"form"|"price_cents"> & {request_id:string}) { return this.request<Medicine>("/medicines",body); }
  stock() { return this.request<StockOverview>("/stock"); }
  dailyReport(date: string) { return this.request<DailyReport>(`/reports/daily?clinic_date=${encodeURIComponent(date)}`); }
  receiveStock(medicineId: string,quantity: number,reason: string,requestId: string) { return this.request<StockReceipt>("/stock/receive",{medicine_id:medicineId,quantity,reason,request_id:requestId}); }
  prescribe(id: string, items: PrescriptionItem[]) { return this.request<Prescription>(`/visits/${encodeURIComponent(id)}/prescription`, {items}); }
  dispense(id: string) { return this.request<Prescription>(`/prescriptions/${encodeURIComponent(id)}/dispense`, {}); }
  invoice(id: string) { return this.request<Invoice>(`/visits/${encodeURIComponent(id)}/invoice`, {}); }
  paySimulated(id: string) { return this.request<Invoice>(`/invoices/${encodeURIComponent(id)}/pay-simulated`, {}); }
}
