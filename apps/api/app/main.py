from datetime import date
import os
from pathlib import Path
from typing import Annotated, Literal
from fastapi import Depends, FastAPI, Header, HTTPException, UploadFile, File, Form, Query
import hashlib
from .photos import MAX_BYTES, normalise_photo
from .photo_checks import check_photo
from .disease_model import predict_disease
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict, ValidationError
from .store import DOCTORS, PATIENTS, USER_ROLES, RuleError, Store

class RestoreWaitingInput(BaseModel):
    model_config=ConfigDict(extra="forbid")
    missed_event_id: str = Field(min_length=1,max_length=100)

class NotificationBatchReadInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    notification_ids: list[Annotated[str,Field(min_length=1,max_length=100)]] = Field(min_length=1,max_length=100)

class BackgroundInput(BaseModel):
    allergies: str = Field(max_length=1000)
    medicines: str = Field(max_length=1000)
    conditions: str = Field(max_length=1000)
    version: int = Field(strict=True, ge=0)

class AssessmentSymptomsInput(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    body_area: str = Field(min_length=1,max_length=80,pattern=r'\S')
    onset: str = Field(min_length=1,max_length=100,pattern=r'\S')
    itching: Literal['yes','no','not_sure']
    pain: Literal['yes','no','not_sure']
    description: str = Field(default='',max_length=1000)

class DoctorProfileInput(BaseModel):
    specialty: str = Field(min_length=1,max_length=80,pattern=r'\S')
    expertise: list[Literal['general','acne','eczema','psoriasis']] = Field(max_length=4)
    version: int = Field(strict=True,ge=0)

class SlotInput(BaseModel):
    doctor_id: Literal['doctor-lim','doctor-anita']
    clinic_date: date
    time: str = Field(pattern=r'^(?:[01]\d|2[0-3]):[0-5]\d$')
    capacity: int = Field(strict=True,ge=1,le=20)
    duration_minutes: int = Field(default=30,strict=True,ge=15,le=120,multiple_of=15)
    request_id: str = Field(min_length=8,max_length=100)

class DaySessionInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    weekday: int = Field(strict=True,ge=0,le=6)
    start_time: str = Field(pattern=r'^(?:[01][0-9]|2[0-3]):[0-5][0-9]$')
    end_time: str = Field(pattern=r'^(?:[01][0-9]|2[0-3]):[0-5][0-9]$')
    second_start_time: str | None = Field(default=None,pattern=r'^(?:[01][0-9]|2[0-3]):[0-5][0-9]$')
    second_end_time: str | None = Field(default=None,pattern=r'^(?:[01][0-9]|2[0-3]):[0-5][0-9]$')

class SchedulePatternInput(BaseModel):
    day_sessions: list[DaySessionInput] = Field(default_factory=list,max_length=7)
    second_start_time: str | None = Field(default=None,pattern=r'^(?:[01][0-9]|2[0-3]):[0-5][0-9]$')
    second_end_time: str | None = Field(default=None,pattern=r'^(?:[01][0-9]|2[0-3]):[0-5][0-9]$')
    weekdays: list[Annotated[int,Field(strict=True,ge=0,le=6)]] = Field(min_length=1,max_length=7)
    start_time: str = Field(pattern=r'^(?:[01]\d|2[0-3]):[0-5]\d$')
    end_time: str = Field(pattern=r'^(?:[01]\d|2[0-3]):[0-5]\d$')
    duration_minutes: int = Field(strict=True,ge=15,le=120,multiple_of=15)
    capacity: int = Field(strict=True,ge=1,le=20)
    version: int = Field(strict=True,ge=0)

class SchedulePreviewInput(BaseModel):
    week_start: date
    version: int = Field(strict=True,ge=1)

class ScheduleGenerateInput(SchedulePreviewInput):
    preview_token: str = Field(pattern=r'^[0-9a-f]{64}$')
    request_id: str = Field(min_length=8,max_length=100)

class UnavailabilityInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    start_time: str | None = Field(default=None,pattern=r'^(?:[01][0-9]|2[0-3]):[0-5][0-9]$')
    end_time: str | None = Field(default=None,pattern=r'^(?:[01][0-9]|2[0-3]):[0-5][0-9]$')
    clinic_date: date
    reason: str = Field(min_length=1,max_length=300,pattern=r'\S')
    request_id: str = Field(min_length=8,max_length=100)

class BookingInput(BaseModel):
    slot_id: str = Field(min_length=1, max_length=100)
    request_id: str = Field(min_length=8, max_length=100)

class CounterBookingInput(BookingInput):
    patient_id: str = Field(min_length=1,max_length=100)

class QueueInput(BaseModel):
    doctor_id: Literal['doctor-lim', 'doctor-anita']
    clinic_date: date

class PrescriptionItemInput(BaseModel):
    medicine_id: str = Field(min_length=1, max_length=100)
    quantity: int = Field(strict=True, ge=1, le=20)
    directions: str = Field(min_length=1, max_length=300, pattern=r'\S')

class PrescriptionInput(BaseModel):
    items: list[PrescriptionItemInput] = Field(min_length=1, max_length=10)

class PrescriptionDirectionItemInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    medicine_id: str = Field(min_length=1,max_length=100)
    directions: str = Field(min_length=1,max_length=300,pattern=r'\S')

class PrescriptionDirectionsInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    version: int = Field(strict=True,ge=1)
    reason: str = Field(min_length=1,max_length=300,pattern=r'\S')
    items: list[PrescriptionDirectionItemInput] = Field(min_length=1,max_length=10)

class PrescriptionCancellationInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    version: int = Field(strict=True,ge=1)
    reason: str = Field(min_length=1,max_length=300,pattern=r'\S')

class UserProfileInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    name: str = Field(min_length=1,max_length=100,pattern=r'\S')
    phone: str = Field(max_length=30)
    email: str = Field(max_length=254)
    version: int = Field(strict=True,ge=0)

class PatientCreateInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    name: str = Field(min_length=1,max_length=100,pattern=r'\S')
    phone: str = Field(default='',max_length=30)
    email: str = Field(default='',max_length=254)
    request_id: str = Field(min_length=8,max_length=100,pattern=r'\S')

class ShareInput(BaseModel):
    doctor_id: Literal['doctor-lim', 'doctor-anita']
    patient_message: str = Field(max_length=1000)
    request_id: str = Field(min_length=8, max_length=100)

class ReviewInput(BaseModel):
    doctor_assessment: str = Field(min_length=1,max_length=500,pattern=r'\S')
    note: str = Field(min_length=1, max_length=2000, pattern=r'\S')
    follow_up: str = Field(min_length=1, max_length=1000, pattern=r'\S')
    draft_version: int | None = Field(default=None,strict=True,ge=0)

class ReviewDraftInput(BaseModel):
    doctor_assessment: str = Field(default='',max_length=500)
    note: str = Field(max_length=2000)
    follow_up: str = Field(max_length=1000)
    version: int = Field(strict=True,ge=0)

class AppointmentLinkInput(BaseModel):
    booking_id: str = Field(min_length=1, max_length=100)
    patient_message: str = Field(max_length=1000)
    request_id: str = Field(min_length=8, max_length=100)

class ConsultationInput(BaseModel):
    findings: str = Field(min_length=1, max_length=2000, pattern=r'\S')
    follow_up: str = Field(min_length=1, max_length=1000, pattern=r'\S')
    draft_version: int | None = Field(default=None,strict=True,ge=0)

class ConsultationDraftInput(BaseModel):
    findings: str = Field(max_length=2000)
    follow_up: str = Field(max_length=1000)
    version: int = Field(strict=True,ge=0)

class FollowUpInput(BaseModel):
    recommended_date: date
    reason: str = Field(min_length=1,max_length=1000,pattern=r'\S')

class FeedbackInput(BaseModel):
    rating: int = Field(strict=True,ge=1,le=5)
    comment: str = Field(max_length=1000)

class FeedbackEditInput(FeedbackInput):
    version: int = Field(strict=True,ge=0)

class MedicineInput(BaseModel):
    name: str = Field(min_length=1,max_length=100,pattern=r'\S')
    strength: str = Field(min_length=1,max_length=60,pattern=r'\S')
    form: str = Field(min_length=1,max_length=60,pattern=r'\S')
    price_cents: int = Field(strict=True,ge=0,le=1000000)
    request_id: str = Field(min_length=8,max_length=100)

class MedicineEditInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    name: str = Field(min_length=1,max_length=100,pattern=r'\S')
    price_cents: int = Field(strict=True,ge=0,le=1000000)
    version: int = Field(strict=True,ge=0)
    request_id: str = Field(min_length=8,max_length=100)

class MedicineTargetInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    target_stock: int | None = Field(...,strict=True,ge=0,le=99999)
    version: int = Field(strict=True,ge=0)
    request_id: str = Field(min_length=8,max_length=100)

class MedicineThresholdInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    low_stock_threshold: int = Field(strict=True,ge=0,le=99999)
    version: int = Field(strict=True,ge=0)
    request_id: str = Field(min_length=8,max_length=100)

class MedicineStatusInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    active: bool = Field(strict=True)
    version: int = Field(strict=True,ge=0)
    request_id: str = Field(min_length=8,max_length=100)

class StockReceiptInput(BaseModel):
    medicine_id: str = Field(min_length=1,max_length=100)
    quantity: int = Field(strict=True,ge=1,le=1000)
    reason: str = Field(min_length=1,max_length=300,pattern=r'\S')
    request_id: str = Field(min_length=8,max_length=100)

class StockReceiveInput(StockReceiptInput):
    model_config=ConfigDict(extra='forbid')
    batch_number: str | None = Field(default=None,strict=True,min_length=1,max_length=60,pattern=r'\S')
    expiry_date: str | None = Field(default=None,strict=True,min_length=10,max_length=10)

class InvoiceReviewInput(BaseModel):
    model_config=ConfigDict(extra="forbid")
    prescription_id: str | None = Field(default=None,max_length=100)

class DispensingAllocation(BaseModel):
    model_config=ConfigDict(extra='forbid')
    medicine_id: str = Field(min_length=1,max_length=100)
    receipt_id: str | None = Field(default=None,strict=True,min_length=1,max_length=100)
    quantity: int = Field(strict=True,ge=1,le=20)

class DispensingInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    allocations: list[DispensingAllocation] | None = Field(default=None,min_length=1,max_length=100)
    prescription_version: int | None = Field(default=None,strict=True,ge=1)

class BatchHoldInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    held: bool = Field(strict=True)
    reason: str = Field(min_length=1,max_length=300,pattern=r'\S')
    version: int = Field(strict=True,ge=0)
    request_id: str = Field(min_length=8,max_length=100)

class StockLossInput(StockReceiptInput):
    model_config=ConfigDict(extra='forbid')
    kind: Literal['damaged','lost']
    receipt_id: str | None = Field(default=None,strict=True,min_length=1,max_length=100)

def create_app(path=None,photo_checker=None,predictor=None):
    photo_checker=photo_checker or check_photo
    predictor=predictor or predict_disease
    store = Store(path or os.getenv('DEMO_DATABASE', str(Path(__file__).parents[1] / 'data/demo.sqlite3')))
    api = FastAPI(title='Smart Skin - LOCAL DEMO API', version='0.1.0')
    api.add_middleware(CORSMiddleware,
        allow_origins=['http://localhost:3000','http://127.0.0.1:3000','http://localhost:8081','http://127.0.0.1:8081'],
        allow_methods=['GET','POST'], allow_headers=['Content-Type','X-Demo-Actor'])

    def actor(x_demo_actor: str = Header()):
        if store.user_role(x_demo_actor) not in ('patient','doctor','staff'):
            raise HTTPException(401, 'Choose a recognised demo identity.')
        return x_demo_actor

    def patient(who=Depends(actor)):
        if not store.is_patient(who):
            raise HTTPException(403, 'Patient demo identity required.')
        return who

    # Admin is recognised only by the basic-information endpoints. Keeping it out
    # of actor() prevents implicit access through existing clinical routes.
    def user_actor(x_demo_actor: str = Header()):
        if store.user_role(x_demo_actor) is None:raise HTTPException(401,'Choose a recognised demo identity.')
        return x_demo_actor

    def admin(who=Depends(user_actor)):
        if who!='admin-demo':raise HTTPException(403,'Admin demo identity required.')
        return who

    def staff(who=Depends(actor)):
        if who != 'staff-demo':
            raise HTTPException(403, 'Staff demo identity required.')
        return who

    def doctor(who=Depends(actor)):
        if who not in DOCTORS:
            raise HTTPException(403, 'Doctor demo identity required.')
        return who

    def operational(who=Depends(actor)):
        if who not in {*DOCTORS, 'staff-demo'}:
            raise HTTPException(403, 'Doctor or staff demo identity required.')
        return who

    def payer(who=Depends(actor)):
        if not store.is_patient(who) and who!='staff-demo':
            raise HTTPException(403, 'Patient or staff demo identity required.')
        return who

    def run(action):
        try:
            return action()
        except RuleError as error:
            raise HTTPException(error.status, error.message) from error

    @api.get('/health')
    def health():
        return {'status':'ok', 'mode':'local-demo', 'authentication':'simulated'}

    @api.get('/me')
    def my_user_profile(who=Depends(user_actor)):
        return run(lambda:store.user_profile(who))

    @api.get('/admin/users')
    def users(who=Depends(admin)):
        return run(lambda:store.user_profiles(who))

    @api.post('/admin/patients',status_code=201)
    def create_patient(payload: PatientCreateInput,who=Depends(admin)):
        return run(lambda:store.create_patient(who,payload.name,payload.phone,payload.email,payload.request_id))

    @api.get('/demo/patients')
    def demo_patients(who=Depends(user_actor)):
        return store.demo_patients()

    @api.post('/admin/users/{user_id}')
    def save_user_profile(user_id: str,payload: UserProfileInput,who=Depends(admin)):
        return run(lambda:store.save_user_profile(user_id,who,payload.name,payload.phone,payload.email,payload.version))

    @api.get('/slots')
    def slots():
        return store.slots()

    @api.get('/doctors')
    def doctor_profiles(who=Depends(actor)):
        return store.doctor_profiles()

    @api.get('/doctor-matches')
    def doctor_matches(concern: Literal['general','acne','eczema','psoriasis'] | None=None,
                       assessment_id: str | None=Query(default=None,min_length=1,max_length=100),who=Depends(patient)):
        return run(lambda: store.doctor_matches(who,concern,assessment_id))

    @api.post('/staff/doctors/{doctor_id}')
    def save_doctor_profile(doctor_id: str,payload: DoctorProfileInput,who=Depends(staff)):
        return run(lambda: store.save_doctor_profile(doctor_id,payload.specialty,payload.expertise,payload.version))

    @api.get('/staff/slots')
    def managed_slots(who=Depends(staff)):
        return store.managed_slots()

    @api.post('/staff/slots',status_code=201)
    def add_slot(payload: SlotInput,who=Depends(staff)):
        return run(lambda: store.add_slot(payload.doctor_id,payload.clinic_date.isoformat(),payload.time,payload.capacity,payload.request_id,payload.duration_minutes))

    @api.post('/staff/slots/{slot_id}/close')
    def close_slot(slot_id: str,who=Depends(staff)):
        return run(lambda: store.close_slot(slot_id))

    @api.get('/staff/schedules')
    def schedule_patterns(who=Depends(staff)):
        return store.schedule_patterns()

    @api.get('/staff/schedules/{doctor_id}/unavailability')
    def unavailability(doctor_id: str,who=Depends(staff)):
        return run(lambda: store.unavailability(doctor_id))

    @api.post('/staff/schedules/{doctor_id}/unavailability',status_code=201)
    def add_unavailability(doctor_id: str,payload: UnavailabilityInput,who=Depends(staff)):
        return run(lambda: store.add_unavailability(doctor_id,payload.clinic_date.isoformat(),payload.reason.strip(),payload.request_id,payload.start_time,payload.end_time))

    @api.post('/staff/schedules/{doctor_id}/unavailability/{absence_id}/cancel')
    def cancel_unavailability(doctor_id: str,absence_id: str,who=Depends(staff)):
        return run(lambda: store.cancel_unavailability(doctor_id,absence_id))

    @api.post('/staff/schedules/{doctor_id}')
    def save_schedule_pattern(doctor_id: str,payload: SchedulePatternInput,who=Depends(staff)):
        return run(lambda: store.save_schedule_pattern(doctor_id,payload.weekdays,payload.start_time,payload.end_time,payload.duration_minutes,payload.capacity,payload.version,payload.second_start_time,payload.second_end_time,[item.model_dump() for item in payload.day_sessions]))

    @api.post('/staff/schedules/{doctor_id}/preview')
    def preview_schedule(doctor_id: str,payload: SchedulePreviewInput,who=Depends(staff)):
        return run(lambda: store.preview_schedule(doctor_id,payload.week_start.isoformat(),payload.version))

    @api.post('/staff/schedules/{doctor_id}/generate',status_code=201)
    def generate_schedule(doctor_id: str,payload: ScheduleGenerateInput,who=Depends(staff)):
        return run(lambda: store.generate_schedule(doctor_id,payload.week_start.isoformat(),payload.version,payload.preview_token,payload.request_id))

    @api.get('/doctor/schedule')
    def doctor_schedule(week_start: date,who=Depends(doctor)):
        return run(lambda: store.doctor_schedule(who,week_start.isoformat()))

    @api.get('/bookings')
    def bookings(who=Depends(patient)):
        return store.mine(who)

    @api.get('/notifications')
    def notifications(cursor: Annotated[str | None,Query(min_length=1,max_length=100)]=None,who=Depends(patient)):
        return run(lambda: store.notifications(who,cursor))

    @api.post('/notifications/{notification_id}/read')
    def read_notification(notification_id: str,who=Depends(patient)):
        return run(lambda: store.read_notification(notification_id,who))

    @api.post('/notifications/read-displayed')
    def read_displayed_notifications(payload: NotificationBatchReadInput,who=Depends(patient)):
        return run(lambda: store.read_notifications(payload.notification_ids,who))

    @api.post('/notifications/{notification_id}/unread')
    def unread_notification(notification_id: str,who=Depends(patient)):
        return run(lambda: store.unread_notification(notification_id,who))

    @api.get('/bookings/{booking_id}/details')
    def visit_details(booking_id: str,who=Depends(patient)):
        return run(lambda: store.visit_details(booking_id,who))

    @api.post('/bookings', status_code=201)
    def book(payload: BookingInput, who=Depends(patient)):
        return run(lambda: store.book(who, payload.slot_id, payload.request_id))

    @api.post('/bookings/{booking_id}/cancel')
    def cancel(booking_id: str, who=Depends(patient)):
        return run(lambda: store.cancel(booking_id, who))

    @api.post('/counter-bookings', status_code=201)
    def counter_book(payload: CounterBookingInput, who=Depends(staff)):
        return run(lambda: store.book(payload.patient_id,payload.slot_id,payload.request_id,created_by=who))

    @api.post('/bookings/{booking_id}/reschedule')
    def reschedule(booking_id: str, payload: BookingInput, who=Depends(actor)):
        if not store.is_patient(who) and who!='staff-demo':
            raise HTTPException(403,'Patient or staff demo identity required.')
        return run(lambda: store.reschedule(booking_id,who,payload.slot_id,payload.request_id))

    @api.get('/queue')
    def queue(doctor_id: Literal['doctor-lim','doctor-anita'], clinic_date: date, who=Depends(staff)):
        return store.queue(doctor_id, clinic_date.isoformat())

    @api.post('/queue/call-next')
    def call_next(payload: QueueInput, who=Depends(staff)):
        return run(lambda: store.call_next(payload.doctor_id, payload.clinic_date.isoformat(), who))

    @api.post('/queue/{booking_id}/missed')
    def mark_missed(booking_id: str, who=Depends(staff)):
        return run(lambda: store.mark_missed(booking_id, who))

    @api.post('/queue/{booking_id}/restore-waiting')
    def restore_waiting(booking_id: str,payload: RestoreWaitingInput,who=Depends(staff)):
        return run(lambda: store.restore_waiting(booking_id,payload.missed_event_id,who))

    @api.post('/queue/{booking_id}/complete')
    def complete(booking_id: str, who=Depends(staff)):
        return run(lambda: store.complete(booking_id, who))

    @api.get('/care')
    def care(who=Depends(actor)):
        return store.care(who)

    @api.get('/assessments')
    def assessments(who=Depends(patient)):
        return store.assessments(who)

    @api.get('/assessments/history')
    def assessment_history(cursor: Annotated[str | None,Query(min_length=1,max_length=100)]=None,who=Depends(patient)):
        return run(lambda: store.assessment_history(who,cursor))

    @api.get('/assessments/{assessment_id}')
    def assessment(assessment_id: str, who=Depends(patient)):
        return run(lambda: store.assessment(assessment_id, who))

    @api.post('/assessments', status_code=201)
    def save_assessment(photo: UploadFile = File(), request_id: str = Form(min_length=8, max_length=100), symptoms: str | None = Form(default=None,max_length=5000),who=Depends(patient)):
        try:
            content = photo.file.read(MAX_BYTES + 1)
        finally:
            photo.file.close()
        def save():
            try:reported=AssessmentSymptomsInput.model_validate_json(symptoms).model_dump() if symptoms is not None else None
            except ValidationError as error:
                raise RuleError('Enter a body area (up to 80 characters), onset (up to 100), itching and pain choices, and an optional description up to 1000 characters.',422) from error
            source_hash=hashlib.sha256(content).hexdigest()
            existing=store.assessment_retry(who,request_id,source_hash,symptoms=reported)
            if existing is not None:return existing
            checked=photo_checker(content)
            if not checked['accepted']:raise RuleError(' '.join(checked['reasons']),422)
            clean, width, height = normalise_photo(content)
            prediction=predictor(content)
            return store.save_assessment(who,request_id,source_hash,clean,width,height,prediction=prediction,symptoms=reported)
        return run(save)

    @api.post('/photo-check')
    def validate_photo(photo: UploadFile = File(),who=Depends(patient)):
        try:content=photo.file.read(MAX_BYTES+1)
        finally:photo.file.close()
        return run(lambda:photo_checker(content))

    @api.get('/medicines')
    def medicines(who=Depends(operational)):
        return store.catalog(active_only=who!='staff-demo')

    @api.post('/medicines',status_code=201)
    def add_medicine(payload: MedicineInput,who=Depends(staff)):
        return run(lambda: store.add_medicine(payload.name.strip(),payload.strength.strip(),payload.form.strip(),payload.price_cents,payload.request_id))

    @api.post('/medicines/{medicine_id}/edit')
    def edit_medicine(medicine_id: str,payload: MedicineEditInput,who=Depends(staff)):
        return run(lambda: store.edit_medicine(medicine_id,payload.name.strip(),payload.price_cents,payload.version,payload.request_id,who))

    @api.post('/medicines/{medicine_id}/target')
    def medicine_target(medicine_id: str,payload: MedicineTargetInput,who=Depends(staff)):
        return run(lambda: store.set_medicine_target(medicine_id,payload.target_stock,payload.version,payload.request_id,who))

    @api.post('/medicines/{medicine_id}/threshold')
    def medicine_threshold(medicine_id: str,payload: MedicineThresholdInput,who=Depends(staff)):
        return run(lambda: store.set_medicine_threshold(medicine_id,payload.low_stock_threshold,payload.version,payload.request_id,who))

    @api.post('/medicines/{medicine_id}/status')
    def medicine_status(medicine_id: str,payload: MedicineStatusInput,who=Depends(staff)):
        return run(lambda: store.set_medicine_active(medicine_id,payload.active,payload.version,payload.request_id,who))

    @api.get('/stock')
    def stock(who=Depends(staff)):
        return store.stock()

    @api.get('/stock/{medicine_id}/movements')
    def stock_movements(medicine_id: str,cursor: str | None=Query(default=None,min_length=1,max_length=200),who=Depends(staff)):
        return run(lambda: store.stock_movements(medicine_id,cursor))

    @api.get('/reports/daily')
    def daily_report(clinic_date: date,who=Depends(staff)):
        return store.daily_report(clinic_date.isoformat())

    @api.get('/reports/weekly')
    def weekly_report(week_of: date,who=Depends(staff)):
        return run(lambda: store.weekly_report(week_of.isoformat()))

    @api.get('/reports/summary')
    def visit_summary(period: Literal['month','quarter','year'],year: int=Query(ge=2,le=9998),
                      month: int | None=Query(default=None,ge=1,le=12),
                      quarter: int | None=Query(default=None,ge=1,le=4),who=Depends(staff)):
        return run(lambda: store.visit_summary(period,year,month,quarter))

    @api.get('/reports/billing')
    def billing_summary(period: Literal['month','quarter','year'],year: int=Query(ge=2,le=9998),
                        month: int | None=Query(default=None,ge=1,le=12),
                        quarter: int | None=Query(default=None,ge=1,le=4),who=Depends(staff)):
        return run(lambda: store.billing_summary(period,year,month,quarter))

    @api.get('/reports/feedback')
    def feedback_summary(period: Literal['month','quarter','year'],year: int=Query(ge=2,le=9998),
                         month: int | None=Query(default=None,ge=1,le=12),
                         quarter: int | None=Query(default=None,ge=1,le=4),who=Depends(staff)):
        return run(lambda: store.feedback_summary(period,year,month,quarter))

    @api.get('/reports/inventory')
    def inventory_summary(period: Literal['month','quarter','year'],year: int=Query(ge=2,le=9998),
                          month: int | None=Query(default=None,ge=1,le=12),
                          quarter: int | None=Query(default=None,ge=1,le=4),who=Depends(staff)):
        return run(lambda: store.inventory_summary(period,year,month,quarter))

    @api.post('/stock/{medicine_id}/batches/{receipt_id}/hold')
    def set_batch_hold(medicine_id: str,receipt_id: str,payload: BatchHoldInput,who=Depends(staff)):
        return run(lambda: store.set_batch_hold(medicine_id,receipt_id,payload.held,payload.reason,payload.version,payload.request_id,who))

    @api.get('/stock/{medicine_id}/batches/{receipt_id}/history')
    def batch_movement_history(medicine_id: str,receipt_id: str,who=Depends(staff)):
        return run(lambda: store.batch_movement_history(medicine_id,receipt_id))

    @api.get('/stock/{medicine_id}/batch-overview')
    def batch_stock_overview(medicine_id: str,who=Depends(staff)):
        return run(lambda: store.batch_stock_overview(medicine_id))

    @api.get('/stock/{medicine_id}/batches')
    def stock_batches(medicine_id: str,who=Depends(staff)):
        return run(lambda: store.stock_batches(medicine_id))

    @api.get('/stock/usable-alerts')
    def usable_stock_alerts(who=Depends(staff)):
        return store.usable_stock_alerts()

    @api.get('/stock/expiry')
    def stock_expiry(who=Depends(staff)):
        return store.stock_expiry()

    @api.post('/stock/receive',status_code=201)
    def receive_stock(payload: StockReceiveInput,who=Depends(staff)):
        return run(lambda: store.receive_stock(payload.medicine_id,payload.quantity,payload.reason,payload.request_id,who,payload.batch_number,payload.expiry_date))

    @api.post('/stock/losses',status_code=201)
    def stock_loss(payload: StockLossInput,who=Depends(staff)):
        return run(lambda: store.record_stock_loss(payload.medicine_id,payload.quantity,payload.kind,payload.reason,payload.request_id,who,payload.receipt_id))

    @api.get('/assessments/{assessment_id}/sharing-history')
    def assessment_sharing_history(assessment_id: str,who=Depends(patient)):
        return run(lambda: store.assessment_sharing_history(assessment_id,who))

    @api.get('/assessment-shares')
    def shares(who=Depends(actor)):
        return run(lambda: store.shares(who))

    @api.post('/assessments/{assessment_id}/share')
    def share_assessment(assessment_id: str, payload: ShareInput, who=Depends(patient)):
        return run(lambda: store.share_assessment(assessment_id, who, payload.doctor_id, payload.patient_message.strip(), payload.request_id))

    @api.post('/assessment-shares/{share_id}/revoke')
    def revoke_share(share_id: str, who=Depends(patient)):
        return run(lambda: store.revoke_share(share_id, who))

    @api.post('/assessments/{assessment_id}/link-appointment')
    def link_assessment(assessment_id: str, payload: AppointmentLinkInput, who=Depends(patient)):
        return run(lambda: store.link_assessment(assessment_id, who, payload.booking_id, payload.patient_message.strip(), payload.request_id))

    @api.get('/assessment-shares/{share_id}')
    def shared_assessment(share_id: str, who=Depends(doctor)):
        return run(lambda: store.shared_assessment(share_id, who))

    @api.post('/assessment-shares/{share_id}/review')
    def publish_review(share_id: str, payload: ReviewInput, who=Depends(doctor)):
        return run(lambda: store.publish_review(share_id,who,payload.note.strip(),payload.follow_up.strip(),payload.draft_version,doctor_assessment=payload.doctor_assessment.strip()))

    @api.get('/assessment-shares/{share_id}/draft')
    def review_draft(share_id: str,who=Depends(doctor)):
        return run(lambda: store.review_draft(share_id,who))

    @api.post('/assessment-shares/{share_id}/draft')
    def save_review_draft(share_id: str,payload: ReviewDraftInput,who=Depends(doctor)):
        return run(lambda: store.save_review_draft(share_id,who,payload.note.strip(),payload.follow_up.strip(),payload.version,doctor_assessment=payload.doctor_assessment.strip()))

    @api.post('/visits/{booking_id}/prescription')
    def prescribe(booking_id: str, payload: PrescriptionInput, who=Depends(doctor)):
        return run(lambda: store.issue_prescription(booking_id, who, [i.model_dump() for i in payload.items]))

    @api.get('/visits/{booking_id}/prescription/directions-history')
    def prescription_directions_history(booking_id: str, who=Depends(doctor)):
        return run(lambda: store.prescription_directions_history(booking_id,who))

    @api.post('/visits/{booking_id}/prescription/directions')
    def correct_prescription_directions(booking_id: str, payload: PrescriptionDirectionsInput, who=Depends(doctor)):
        return run(lambda: store.correct_prescription_directions(booking_id,who,payload.version,payload.reason,[item.model_dump() for item in payload.items]))

    @api.get('/visits/{booking_id}/prescription/cancellation')
    def prescription_cancellation(booking_id: str,who=Depends(doctor)):
        return run(lambda: store.prescription_cancellation(booking_id,who))

    @api.post('/visits/{booking_id}/prescription/cancel')
    def cancel_prescription(booking_id: str,payload: PrescriptionCancellationInput,who=Depends(doctor)):
        return run(lambda: store.cancel_prescription(booking_id,who,payload.version,payload.reason))

    @api.get('/prescriptions/{prescription_id}/stock-sources')
    def dispensing_stock(prescription_id: str,who=Depends(staff)):
        return run(lambda: store.dispensing_stock(prescription_id))

    @api.post('/prescriptions/{prescription_id}/dispense')
    def dispense(prescription_id: str, payload: DispensingInput=DispensingInput(), who=Depends(staff)):
        return run(lambda: store.dispense(prescription_id, who,[part.model_dump() for part in payload.allocations] if payload.allocations is not None else None,payload.prescription_version))

    @api.get('/patient-background')
    def background(who=Depends(patient)):
        return run(lambda: store.background(who))

    @api.post('/patient-background')
    def save_background(payload: BackgroundInput, who=Depends(patient)):
        return run(lambda: store.save_background(who,payload.allergies.strip(),payload.medicines.strip(),payload.conditions.strip(),payload.version))

    @api.get('/consultations')
    def consultations(who=Depends(actor)):
        return run(lambda: store.consultations(who))

    @api.get('/feedback')
    def feedback(who=Depends(actor)):
        return run(lambda: store.feedback(who))

    @api.post('/visits/{booking_id}/feedback',status_code=201)
    def submit_feedback(booking_id: str,payload: FeedbackInput,who=Depends(patient)):
        return run(lambda: store.submit_feedback(booking_id,who,payload.rating,payload.comment.strip()))

    @api.post('/visits/{booking_id}/feedback/edit')
    def edit_feedback(booking_id: str,payload: FeedbackEditInput,who=Depends(patient)):
        return run(lambda: store.edit_feedback(booking_id,who,payload.rating,payload.comment.strip(),payload.version))

    @api.get('/visits/{booking_id}/consultation')
    def consultation(booking_id: str, who=Depends(actor)):
        return run(lambda: store.consultation(booking_id, who))

    @api.get('/visits/{booking_id}/history')
    def consultation_history(booking_id: str,who=Depends(doctor)):
        return run(lambda: store.consultation_history(booking_id,who))

    @api.post('/visits/{booking_id}/follow-up')
    def recommend_follow_up(booking_id: str,payload: FollowUpInput,who=Depends(doctor)):
        return run(lambda: store.recommend_follow_up(booking_id,who,payload.recommended_date.isoformat(),payload.reason.strip()))

    @api.post('/visits/{booking_id}/follow-up/book',status_code=201)
    def book_follow_up(booking_id: str,payload: BookingInput,who=Depends(patient)):
        return run(lambda: store.book(who,payload.slot_id,payload.request_id,follow_up_source=booking_id))

    @api.post('/visits/{booking_id}/consultation')
    def publish_consultation(booking_id: str, payload: ConsultationInput, who=Depends(doctor)):
        return run(lambda: store.publish_consultation(booking_id,who,payload.findings.strip(),payload.follow_up.strip(),payload.draft_version))

    @api.get('/visits/{booking_id}/consultation/draft')
    def consultation_draft(booking_id: str,who=Depends(doctor)):
        return run(lambda: store.consultation_draft(booking_id,who))

    @api.post('/visits/{booking_id}/consultation/finish')
    def finish_consultation(booking_id: str,who=Depends(doctor)):
        return run(lambda: store.finish_consultation(booking_id,who))

    @api.post('/visits/{booking_id}/consultation/draft')
    def save_consultation_draft(booking_id: str,payload: ConsultationDraftInput,who=Depends(doctor)):
        return run(lambda: store.save_consultation_draft(booking_id,who,payload.findings.strip(),payload.follow_up.strip(),payload.version))

    @api.post('/visits/{booking_id}/invoice')
    def invoice(booking_id: str, payload: InvoiceReviewInput | None=None, who=Depends(staff)):
        return run(lambda: store.generate_invoice(booking_id, who, payload.model_dump() if payload and "prescription_id" in payload.model_fields_set else None))

    @api.post('/invoices/{invoice_id}/pay-simulated')
    def pay(invoice_id: str, who=Depends(payer)):
        return run(lambda: store.pay_simulated(invoice_id, who))

    return api

app = create_app()
