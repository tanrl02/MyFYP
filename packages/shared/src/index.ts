export type Status = "waiting" | "called" | "completed" | "cancelled" | "missed";
export type ConsultationNote = { id: string; booking_id: string; doctor_id: DemoDoctor; findings: string; follow_up: string; created_at: string };
export type ConsultationDraft = {booking_id:string;doctor_id:DemoDoctor;findings:string;follow_up:string;version:number;updated_at:string|null};
export type PatientBackground = { patient_id: DemoPatient; allergies: string; medicines: string; conditions: string; version: number; updated_at: string | null };
export type FollowUp = {source_booking_id:string;doctor_id:DemoDoctor;recommended_date:string;reason:string;created_at:string;booked_visit:Booking|null};
export type Consultation = { visit: Booking; note: ConsultationNote | null; linked_share: AssessmentShare | null; background?: PatientBackground;follow_up?:FollowUp|null };
export type VisitFeedback = { id: string; booking_id: string; patient_id: DemoPatient; rating: number; comment: string; created_at: string; version:number; edited_at:string|null;edit_deadline:string;visit: Booking };
export type DemoPatient = "patient-ava" | "patient-noah";
export type PatientNotification = {id:string;patient_id:DemoPatient;kind:"queue_called"|"review_published"|"appointment_reminder"|"follow_up_recommended";source_id:string;target_id:string;title:string;message:string;created_at:string;read_at:string|null};
export type NotificationInbox = {items:PatientNotification[];unread_count:number;next_cursor:string|null};
export type DemoActor = DemoPatient | "staff-demo" | "doctor-lim" | "doctor-anita";
export type Medicine = { id: string; name: string; strength: string; form: string; price_cents: number; stock: number; version:number; updated_at:string|null; active:boolean; low_stock_threshold:number; target_stock:number|null };
export const medicineLabel = (item: Pick<Medicine,"name"|"strength"|"form">) => [item.name,item.strength,item.form].filter(Boolean).join(" · ");
export type StockReceipt = { id: string; medicine_id: string; quantity: number; reason: string; stock_before: number; stock_after: number; actor_id: string; created_at: string; name?: string; batch_number?:string|null; expiry_date?:string|null };
export type DispensingAllocation={medicine_id:string;receipt_id:string|null;quantity:number};
export type BatchHoldState={receipt_id:string;held:boolean;hold_reason:string|null;hold_version:number;hold_updated_at:string|null};
export type DispensingStock={status:"issued"|"dispensed";items:{medicine_id:string;stock:number;untracked_units:number;batches:({receipt_id:string;batch_number:string;expiry_date:string;remaining_units:number;expired:boolean} & BatchHoldState)[]}[];allocations:(DispensingAllocation & {batch_number:string|null;expiry_date:string|null;actor_id:string;created_at:string})[]};
export type BatchMovementHistory={medicine_id:string;receipt_id:string;batch_number:string;expiry_date:string;remaining_units:number;totals:Record<"received"|"dispensed"|"damaged"|"lost",number>;calculated_remaining:number;reconciled:boolean;movements:{id:string;kind:"received"|"dispensed"|"damaged"|"lost";quantity:number;change:number;created_at:string;actor_id:string;reason:string|null;balance_after:number}[]};
export type BatchStockOverview=DispensingStock["items"][number] & {medicine:Medicine;as_of:string};
export type ReceiptBatch={receipt_id:string;batch_number:string;expiry_date:string;quantity:number;created_at:string;loss_units:number;loss_allowance:number;remaining_units:number|null};
export type StockLoss=StockReceipt & {kind:"damaged"|"lost";item_label:string;receipt_id:string|null};
export type StockMovement = {source_id:string;kind:"received"|"dispensed"|"damaged"|"lost";change:number;created_at:string;reason:string|null;stock_before:number|null;stock_after:number|null;actor_id:string|null;item_label:string|null};
export type StockMovementHistory = {medicine:Medicine;movements:StockMovement[];has_more:boolean;next_cursor:string|null};
export type StockExpiry = {as_of:string;through_date:string;timezone:string;expired_receipts:number;due_soon_receipts:number;untracked_receipts:number;has_more:boolean;items:{id:string;medicine_id:string;batch_number:string;expiry_date:string;quantity:number;created_at:string;name:string;strength:string;form:string;active:boolean;remaining_units:number|null;days_to_expiry:number}[]};
export type UsableStockAlerts={as_of:string;active_items:number;no_usable_items:number;low_usable_items:number;untracked_review_items:number;alerts:{medicine_id:string;name:string;strength:string;form:string;stock:number;low_stock_threshold:number;tracked_units:number;usable_units:number;untracked_units:number;blocked_tracked_units:number}[]};
export type StockOverview = { medicines: Medicine[]; receipts: StockReceipt[]; losses:StockLoss[]; low_stock_threshold: number };
export type VisitCounts = Record<Status | "rescheduled" | "total",number>;
export type WeeklyVisitReport = {week_start:string;week_end:string;timezone:string;generated_at:string;visits:VisitCounts;days:{clinic_date:string;visits:VisitCounts}[]};
export type VisitSummaryFilter={period:"month";year:number;month:number}|{period:"quarter";year:number;quarter:number}|{period:"year";year:number};
export type ReportPeriodFilter=VisitSummaryFilter;
export type BillingTotals={invoice_count:number;paid_invoice_count:number;unpaid_invoice_count:number;billed_cents:number;paid_cents:number;unpaid_cents:number};
export type BillingSummary={period:ReportPeriodFilter["period"];start_date:string;end_date:string;timezone:string;generated_at:string;granularity:"day"|"month";billing:BillingTotals;buckets:{start_date:string;end_date:string;billing:BillingTotals}[]};
export type FeedbackSummary={period:ReportPeriodFilter["period"];start_date:string;end_date:string;timezone:string;generated_at:string;count:number;average_rating:number|null;ratings:{rating:number;count:number}[]};
export type InventoryUnits=Record<"received"|"dispensed"|"damaged"|"lost"|"net_change",number>;
export type InventorySummary={period:ReportPeriodFilter["period"];start_date:string;end_date:string;timezone:string;generated_at:string;granularity:"day"|"month";units:InventoryUnits;buckets:{start_date:string;end_date:string;units:InventoryUnits}[];top_dispensed:{medicine_id:string;name:string;strength:string;form:string;active:boolean;units:number}[];current_stock:{active_items:number;inactive_items:number;active_units:number;low_stock_items:number;out_of_stock_items:number;low_stock_threshold:number;alerts:{medicine_id:string;name:string;strength:string;form:string;stock:number;low_stock_threshold:number}[]}};
export type VisitSummary={period:VisitSummaryFilter["period"];start_date:string;end_date:string;timezone:string;generated_at:string;granularity:"day"|"month";visits:VisitCounts;buckets:{start_date:string;end_date:string;visits:VisitCounts}[];previous:{start_date:string;end_date:string;visits:VisitCounts}};
export type DailyReport = { clinic_date: string; timezone: string; generated_at: string; visits: VisitCounts; visits_by_doctor: {doctor_id: DemoDoctor; doctor_name: string; visits: VisitCounts}[]; billing: { invoice_count: number; billed_cents: number; paid_cents: number; unpaid_cents: number }; stock: { received_units: number; dispensed_units: number; lost_units:number; items: { medicine_id: string; name: string; received: number; dispensed: number; lost:number }[] }; feedback: { count: number; average_rating: number | null } };
export type DiseasePrediction = {model_id:string;checkpoint_sha256:string;preprocessing:string;dataset_version:string;validation_accuracy:number;validation_macro_f1:number;validation_cases:number;test_evaluated:boolean;input_sha256:string;created_at:string;top_predictions:{condition:string;label:string;score:number}[]};
export type AssessmentSymptoms={body_area:string;onset:string;itching:"yes"|"no"|"not_sure";pain:"yes"|"no"|"not_sure";description:string};
export type Assessment = { id: string; patient_id: DemoPatient; width: number; height: number; created_at: string; origin: "simulation"|"experimental_ai"; example_category: string|null; prediction?:DiseasePrediction; symptoms:AssessmentSymptoms|null; message: string; photo_uri?: string };
export const assessmentCategory=(assessment:Assessment)=>assessment.prediction?.top_predictions[0]?.label??assessment.example_category??"No suggestion";
export const assessmentOrigin=(assessment:Assessment)=>assessment.origin==="experimental_ai"?"Experimental AI":"Simulation";
export type DemoDoctor = "doctor-lim" | "doctor-anita";
export const concernLabels = {general:"General skin concerns / not sure",acne:"Acne",eczema:"Eczema",psoriasis:"Psoriasis"};
export type DoctorConcern = keyof typeof concernLabels;
export type DoctorProfile = {doctor_id:DemoDoctor;doctor_name:string;specialty:string;expertise:DoctorConcern[];version:number;updated_at:string|null};
export type DoctorMatchSource = {concern:DoctorConcern;assessmentId?:string};
export type DoctorMatches = {concern:DoctorConcern;source:"manual"|"simulation"|"experimental_ai";assessment_id:string|null;message:string;doctors:(DoctorProfile & {match_level:"concern"|"general"|"none";match_reason:string})[]};
export const doctorNames: Record<DemoDoctor, string> = { "doctor-lim": "Dr. Lim (demo)", "doctor-anita": "Dr. Anita (demo)" };
export type AssessmentReview = { id: string; share_id: string; doctor_id: DemoDoctor; doctor_assessment:string; note: string; follow_up: string; created_at: string };
export type ReviewDraft = {share_id:string;doctor_id:DemoDoctor;doctor_assessment:string;note:string;follow_up:string;version:number;updated_at:string|null};
export type AssessmentShare = { id: string; assessment_id: string; patient_id: DemoPatient; patient_name: string; doctor_id: DemoDoctor; doctor_name: string; patient_message: string; request_id: string; created_at: string; revoked_at: string | null; review: AssessmentReview | null; assessment?: Assessment; booking_id: string | null; visit: Booking | null };
export type PrescriptionItem = { medicine_id: string; quantity: number; directions: string };
export type Prescription = { id: string; booking_id: string; doctor_id: string; status: "issued" | "dispensed"; created_at: string; dispensed_at: string | null; items: (PrescriptionItem & Pick<Medicine,"name"|"strength"|"form"|"price_cents">)[] };
export type ClinicalPrescription = Omit<Prescription,"items"> & {items:(PrescriptionItem & Pick<Medicine,"name"|"strength"|"form">)[]};
export type ConsultationHistory = {current_visit_id:string;limit:number;items:{visit:Booking;note:ConsultationNote|null;prescription:ClinicalPrescription|null}[]};
export type Invoice = { id: string; booking_id: string; total_cents: number; status: "unpaid" | "paid"; paid_at: string | null; payment_mode: "simulation" | null; lines: { description: string; quantity: number; unit_price_cents: number }[] };
export type Care = { visit: Booking; prescription: Prescription | null; invoice: Invoice | null };
export type VisitDetails = Care & { linked_shares: AssessmentShare[]; note: ConsultationNote | null; feedback: Omit<VisitFeedback,"visit"> | null; replacement: Booking | null;follow_up:FollowUp|null;follow_up_of:Booking|null };
export const money = (cents: number) => `RM ${(cents / 100).toFixed(2)}`;
export type Slot = { id: string; doctor_id: string; doctor_name: string; starts_at: string;ends_at:string;duration_minutes:number; clinic_date: string; capacity: number; available: number };
export type ManagedSlot = Slot & {closed:number;booking_count:number;unavailable?:boolean};
export type DaySession={weekday:number;start_time:string;end_time:string;second_start_time:string|null;second_end_time:string|null};
export type SchedulePattern = {doctor_id:DemoDoctor;doctor_name:string;weekdays:number[];day_sessions:DaySession[];start_time:string;end_time:string;second_start_time:string|null;second_end_time:string|null;duration_minutes:number;capacity:number;version:number;updated_at:string|null};
export type SchedulePatternInput=Pick<SchedulePattern,"day_sessions"|"weekdays"|"start_time"|"end_time"|"second_start_time"|"second_end_time"|"duration_minutes"|"capacity"|"version">;
export type SchedulePreview={doctor_id:DemoDoctor;doctor_name:string;week_start:string;pattern_version:number;new_count:number;existing_count:number;conflict_count:number;unavailable_count:number;preview_token:string;slots:{starts_at:string;ends_at:string;clinic_date:string;duration_minutes:number;capacity:number;status:"new"|"existing"|"conflict"|"unavailable";reason:string;slot_id?:string}[]};
export type ScheduleGeneration={id:string;doctor_id:DemoDoctor;week_start:string;pattern_version:number;created_count:number;existing_count:number;unavailable_count?:number;slot_ids:string[];created_at:string};
export type DoctorUnavailability={id:string;doctor_id:DemoDoctor;clinic_date:string;reason:string;created_at:string;cancelled_at:string|null;start_time:string|null;end_time:string|null};
export type DoctorSchedule={pattern:SchedulePattern;week_start:string;unavailability:DoctorUnavailability[];slots:(ManagedSlot & {visits:{id:string;queue_number:number;status:Status;patient_name:string}[]})[]};
export type Booking = { id: string; patient_id: DemoPatient; patient_name: string; slot_id: string; queue_number: number; status: Status; missed_event_id?:string|null; doctor_id: string; doctor_name: string; starts_at: string;ends_at?:string;duration_minutes?:number; clinic_date: string; created_at: string; rescheduled_to_id: string | null;follow_up_source_id?:string|null;follow_up_date?:string|null };
export const patientNames: Record<DemoPatient, string> = { "patient-ava": "Ava Demo", "patient-noah": "Noah Demo" };
export const statusLabels: Record<Status, string> = { waiting: "Waiting", called: "Called — please approach the counter", completed: "Completed", cancelled: "Cancelled", missed: "Missed" };
export const queueToken = (booking: Booking) => `${booking.doctor_id === "doctor-lim" ? "L" : "A"}${String(booking.queue_number).padStart(3, "0")}`;
export const visitTime = (iso: string) => new Date(iso).toLocaleString("en-MY", { timeZone: "Asia/Kuala_Lumpur", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
export const visitWindow = (slot:{starts_at:string;ends_at?:string}) => {
  if(!slot.ends_at)return visitTime(slot.starts_at);
  const day=(iso:string)=>new Date(Date.parse(iso)+8*3600000).toISOString().slice(0,10);
  const end=day(slot.starts_at)===day(slot.ends_at)?new Date(slot.ends_at).toLocaleTimeString("en-MY",{timeZone:"Asia/Kuala_Lumpur",hour:"numeric",minute:"2-digit"}):visitTime(slot.ends_at);
  return `${visitTime(slot.starts_at)} – ${end}`;
};

export type PhotoCheck = {accepted:boolean;version:string;skin_content:"likely_skin"|"not_skin"|"uncertain"|"not_checked";reasons:string[];message:string};
export class DemoApi {
  doctorMatches(source:DoctorMatchSource) { return this.request<DoctorMatches>(source.assessmentId?`/doctor-matches?assessment_id=${encodeURIComponent(source.assessmentId)}`:`/doctor-matches?concern=${encodeURIComponent(source.concern)}`); }
  doctors() { return this.request<DoctorProfile[]>("/doctors"); }
  saveDoctor(id:DemoDoctor,body:Pick<DoctorProfile,"specialty"|"expertise"|"version">) { return this.request<DoctorProfile>(`/staff/doctors/${encodeURIComponent(id)}`,body); }
  constructor(private baseUrl: string, private actor: DemoActor) {}
  private async request<T>(path: string, body?: object | FormData, timeoutMs=10000): Promise<T> {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), timeoutMs);
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
  schedulePatterns() { return this.request<SchedulePattern[]>("/staff/schedules"); }
  unavailability(doctor:DemoDoctor) { return this.request<DoctorUnavailability[]>(`/staff/schedules/${doctor}/unavailability`); }
  addUnavailability(doctor:DemoDoctor,clinicDate:string,reason:string,requestId:string,startTime:string|null=null,endTime:string|null=null) { return this.request<DoctorUnavailability>(`/staff/schedules/${doctor}/unavailability`,{clinic_date:clinicDate,reason,request_id:requestId,start_time:startTime,end_time:endTime}); }
  cancelUnavailability(doctor:DemoDoctor,id:string) { return this.request<DoctorUnavailability>(`/staff/schedules/${doctor}/unavailability/${encodeURIComponent(id)}/cancel`,{}); }
  saveSchedulePattern(doctor:DemoDoctor,body:SchedulePatternInput) { return this.request<SchedulePattern>(`/staff/schedules/${doctor}`,body); }
  previewSchedule(doctor:DemoDoctor,weekStart:string,version:number) { return this.request<SchedulePreview>(`/staff/schedules/${doctor}/preview`,{week_start:weekStart,version}); }
  generateSchedule(doctor:DemoDoctor,weekStart:string,version:number,previewToken:string,requestId:string) { return this.request<ScheduleGeneration>(`/staff/schedules/${doctor}/generate`,{week_start:weekStart,version,preview_token:previewToken,request_id:requestId}); }
  doctorSchedule(weekStart:string) { return this.request<DoctorSchedule>(`/doctor/schedule?week_start=${encodeURIComponent(weekStart)}`); }
  addSlot(body:{doctor_id:DemoDoctor;clinic_date:string;time:string;capacity:number;request_id:string;duration_minutes?:number}) { return this.request<ManagedSlot>("/staff/slots",body); }
  closeSlot(id:string) { return this.request<ManagedSlot>(`/staff/slots/${encodeURIComponent(id)}/close`,{}); }
  bookings() { return this.request<Booking[]>("/bookings"); }
  notifications(cursor?:string) { return this.request<NotificationInbox>(`/notifications${cursor?`?cursor=${encodeURIComponent(cursor)}`:""}`); }
  readNotification(id:string) { return this.request<PatientNotification>(`/notifications/${encodeURIComponent(id)}/read`,{}); }
  readDisplayedNotifications(ids:string[]) { return this.request<{items:PatientNotification[];marked_count:number;unread_count:number}>("/notifications/read-displayed",{notification_ids:ids}); }
  visitDetails(id: string) { return this.request<VisitDetails>(`/bookings/${encodeURIComponent(id)}/details`); }
  book(slotId: string, requestId: string) { return this.request<Booking>("/bookings", { slot_id: slotId, request_id: requestId }); }
  counterBook(patient: DemoPatient, slotId: string, requestId: string) { return this.request<Booking>("/counter-bookings", { patient_id: patient, slot_id: slotId, request_id: requestId }); }
  cancel(id: string) { return this.request<Booking>(`/bookings/${encodeURIComponent(id)}/cancel`, {}); }
  reschedule(id: string, slotId: string, requestId: string) { return this.request<Booking>(`/bookings/${encodeURIComponent(id)}/reschedule`, {slot_id:slotId,request_id:requestId}); }
  queue(doctor: string, date: string) { return this.request<Booking[]>(`/queue?doctor_id=${encodeURIComponent(doctor)}&clinic_date=${encodeURIComponent(date)}`); }
  callNext(doctor: string, date: string) { return this.request<Booking>("/queue/call-next", { doctor_id: doctor, clinic_date: date }); }
  restoreWaiting(id:string,missedEventId:string) { return this.request<Booking>(`/queue/${encodeURIComponent(id)}/restore-waiting`,{missed_event_id:missedEventId}); }
  markMissed(id: string) { return this.request<Booking>(`/queue/${encodeURIComponent(id)}/missed`, {}); }
  complete(id: string) { return this.request<Booking>(`/queue/${encodeURIComponent(id)}/complete`, {}); }
  care() { return this.request<Care[]>("/care"); }
  consultations() { return this.request<Consultation[]>("/consultations"); }
  background() { return this.request<PatientBackground>("/patient-background"); }
  saveBackground(body: Pick<PatientBackground,"allergies"|"medicines"|"conditions"|"version">) { return this.request<PatientBackground>("/patient-background",body); }
  feedback() { return this.request<VisitFeedback[]>("/feedback"); }
  billingSummary(filter:ReportPeriodFilter) { return this.request<BillingSummary>(`/reports/billing?${new URLSearchParams(Object.entries(filter).map(([key,value])=>[key,String(value)]))}`); }
  feedbackSummary(filter:ReportPeriodFilter) { return this.request<FeedbackSummary>(`/reports/feedback?${new URLSearchParams(Object.entries(filter).map(([key,value])=>[key,String(value)]))}`); }
  submitFeedback(id: string,rating: number,comment: string) { return this.request<VisitFeedback>(`/visits/${encodeURIComponent(id)}/feedback`,{rating,comment}); }
  editFeedback(id:string,rating:number,comment:string,version:number) { return this.request<VisitFeedback>(`/visits/${encodeURIComponent(id)}/feedback/edit`,{rating,comment,version}); }
  consultation(id: string) { return this.request<Consultation>(`/visits/${encodeURIComponent(id)}/consultation`); }
  consultationHistory(id:string) { return this.request<ConsultationHistory>(`/visits/${encodeURIComponent(id)}/history`); }
  recommendFollowUp(id:string,recommendedDate:string,reason:string) { return this.request<FollowUp>(`/visits/${encodeURIComponent(id)}/follow-up`,{recommended_date:recommendedDate,reason}); }
  bookFollowUp(id:string,slot:string,requestId:string) { return this.request<Booking>(`/visits/${encodeURIComponent(id)}/follow-up/book`,{slot_id:slot,request_id:requestId}); }
  consultationDraft(id:string) { return this.request<ConsultationDraft>(`/visits/${encodeURIComponent(id)}/consultation/draft`); }
  saveConsultationDraft(id:string,findings:string,followUp:string,version:number) { return this.request<ConsultationDraft>(`/visits/${encodeURIComponent(id)}/consultation/draft`,{findings,follow_up:followUp,version}); }
  publishConsultation(id: string, findings: string, followUp: string,draftVersion?:number) { return this.request<Consultation>(`/visits/${encodeURIComponent(id)}/consultation`, { findings, follow_up: followUp,draft_version:draftVersion }); }
  assessments() { return this.request<Assessment[]>("/assessments"); }
  assessment(id: string) { return this.request<Assessment>(`/assessments/${encodeURIComponent(id)}`); }
  checkPhoto(body: FormData) { return this.request<PhotoCheck>("/photo-check", body,60000); }
  saveAssessment(body: FormData) { return this.request<Assessment>("/assessments", body,60000); }
  shares() { return this.request<AssessmentShare[]>("/assessment-shares"); }
  shareAssessment(id: string, doctor: DemoDoctor, message: string, requestId: string) { return this.request<AssessmentShare>(`/assessments/${encodeURIComponent(id)}/share`, { doctor_id: doctor, patient_message: message, request_id: requestId }); }
  revokeShare(id: string) { return this.request<AssessmentShare>(`/assessment-shares/${encodeURIComponent(id)}/revoke`, {}); }
  linkAssessment(id: string, booking: string, message: string, requestId: string) { return this.request<AssessmentShare>(`/assessments/${encodeURIComponent(id)}/link-appointment`, { booking_id: booking, patient_message: message, request_id: requestId }); }
  sharedAssessment(id: string) { return this.request<AssessmentShare>(`/assessment-shares/${encodeURIComponent(id)}`); }
  reviewDraft(id:string) { return this.request<ReviewDraft>(`/assessment-shares/${encodeURIComponent(id)}/draft`); }
  saveReviewDraft(id:string,note:string,followUp:string,version:number,doctorAssessment:string) { return this.request<ReviewDraft>(`/assessment-shares/${encodeURIComponent(id)}/draft`,{note,follow_up:followUp,version,doctor_assessment:doctorAssessment}); }
  publishReview(id: string, note: string, followUp: string,doctorAssessment:string, draftVersion?:number) { return this.request<AssessmentShare>(`/assessment-shares/${encodeURIComponent(id)}/review`, { note, follow_up: followUp,doctor_assessment:doctorAssessment, ...(draftVersion===undefined?{}:{draft_version:draftVersion}) }); }
  medicines() { return this.request<Medicine[]>("/medicines"); }
  addMedicine(body: Pick<Medicine,"name"|"strength"|"form"|"price_cents"> & {request_id:string}) { return this.request<Medicine>("/medicines",body); }
  stockMovements(id:string,cursor?:string) { return this.request<StockMovementHistory>(`/stock/${encodeURIComponent(id)}/movements${cursor?`?cursor=${encodeURIComponent(cursor)}`:""}`); }
  stock() { return this.request<StockOverview>("/stock"); }
  usableStockAlerts() { return this.request<UsableStockAlerts>("/stock/usable-alerts"); }
  dailyReport(date: string) { return this.request<DailyReport>(`/reports/daily?clinic_date=${encodeURIComponent(date)}`); }
  weeklyReport(weekOf:string) { return this.request<WeeklyVisitReport>(`/reports/weekly?week_of=${encodeURIComponent(weekOf)}`); }
  visitSummary(filter:VisitSummaryFilter) { return this.request<VisitSummary>(`/reports/summary?${new URLSearchParams(Object.entries(filter).map(([key,value])=>[key,String(value)]))}`); }
  inventorySummary(filter:ReportPeriodFilter) { return this.request<InventorySummary>(`/reports/inventory?${new URLSearchParams(Object.entries(filter).map(([key,value])=>[key,String(value)]))}`); }
  editMedicine(id:string,body:Pick<Medicine,"name"|"price_cents"|"version"> & {request_id:string}) { return this.request<Medicine>(`/medicines/${encodeURIComponent(id)}/edit`,body); }
  setMedicineTarget(id:string,body:{target_stock:number|null;version:number;request_id:string}) { return this.request<Medicine>(`/medicines/${encodeURIComponent(id)}/target`,body); }
  setMedicineThreshold(id:string,body:{low_stock_threshold:number;version:number;request_id:string}) { return this.request<Medicine>(`/medicines/${encodeURIComponent(id)}/threshold`,body); }
  setMedicineActive(id:string,body:{active:boolean;version:number;request_id:string}) { return this.request<Medicine>(`/medicines/${encodeURIComponent(id)}/status`,body); }
  setBatchHold(medicineId:string,receiptId:string,body:{held:boolean;reason:string;version:number;request_id:string}) { return this.request<BatchHoldState>(`/stock/${encodeURIComponent(medicineId)}/batches/${encodeURIComponent(receiptId)}/hold`,body); }
  batchMovementHistory(medicineId:string,receiptId:string) { return this.request<BatchMovementHistory>(`/stock/${encodeURIComponent(medicineId)}/batches/${encodeURIComponent(receiptId)}/history`); }
  batchStockOverview(id:string) { return this.request<BatchStockOverview>(`/stock/${encodeURIComponent(id)}/batch-overview`); }
  stockBatches(id:string) { return this.request<ReceiptBatch[]>(`/stock/${encodeURIComponent(id)}/batches`); }
  recordStockLoss(body:{medicine_id:string;quantity:number;kind:"damaged"|"lost";reason:string;request_id:string;receipt_id?:string|null}) { return this.request<StockLoss>("/stock/losses",body); }
  stockExpiry() { return this.request<StockExpiry>("/stock/expiry"); }
  receiveStock(medicineId: string,quantity: number,reason: string,requestId: string,batch?:{batch_number:string;expiry_date:string}) { return this.request<StockReceipt>("/stock/receive",{medicine_id:medicineId,quantity,reason,request_id:requestId,...batch}); }
  prescribe(id: string, items: PrescriptionItem[]) { return this.request<Prescription>(`/visits/${encodeURIComponent(id)}/prescription`, {items}); }
  dispensingStock(id:string) { return this.request<DispensingStock>(`/prescriptions/${encodeURIComponent(id)}/stock-sources`); }
  dispense(id: string,allocations?:DispensingAllocation[]) { return this.request<Prescription>(`/prescriptions/${encodeURIComponent(id)}/dispense`, allocations?{allocations}:{}); }
  invoice(id: string,review?:{prescription_id:string|null}) { return this.request<Invoice>(`/visits/${encodeURIComponent(id)}/invoice`, review??{}); }
  paySimulated(id: string) { return this.request<Invoice>(`/invoices/${encodeURIComponent(id)}/pay-simulated`, {}); }
}
