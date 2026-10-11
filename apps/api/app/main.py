from datetime import date
import os
from pathlib import Path
from typing import Literal
from fastapi import Depends, FastAPI, Header, HTTPException, UploadFile, File, Form
import hashlib
from .photos import MAX_BYTES, normalise_photo
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from .store import DOCTORS, PATIENTS, RuleError, Store

class BookingInput(BaseModel):
    slot_id: str = Field(min_length=1, max_length=100)
    request_id: str = Field(min_length=8, max_length=100)

class CounterBookingInput(BookingInput):
    patient_id: Literal['patient-ava','patient-noah']

class QueueInput(BaseModel):
    doctor_id: Literal['doctor-lim', 'doctor-anita']
    clinic_date: date

class PrescriptionItemInput(BaseModel):
    medicine_id: str = Field(min_length=1, max_length=100)
    quantity: int = Field(strict=True, ge=1, le=20)
    directions: str = Field(min_length=1, max_length=300, pattern=r'\S')

class PrescriptionInput(BaseModel):
    items: list[PrescriptionItemInput] = Field(min_length=1, max_length=10)

class ShareInput(BaseModel):
    doctor_id: Literal['doctor-lim', 'doctor-anita']
    patient_message: str = Field(max_length=1000)
    request_id: str = Field(min_length=8, max_length=100)

class ReviewInput(BaseModel):
    note: str = Field(min_length=1, max_length=2000, pattern=r'\S')
    follow_up: str = Field(min_length=1, max_length=1000, pattern=r'\S')

class AppointmentLinkInput(BaseModel):
    booking_id: str = Field(min_length=1, max_length=100)
    patient_message: str = Field(max_length=1000)
    request_id: str = Field(min_length=8, max_length=100)

class ConsultationInput(BaseModel):
    findings: str = Field(min_length=1, max_length=2000, pattern=r'\S')
    follow_up: str = Field(min_length=1, max_length=1000, pattern=r'\S')

def create_app(path=None):
    store = Store(path or os.getenv('DEMO_DATABASE', str(Path(__file__).parents[1] / 'data/demo.sqlite3')))
    api = FastAPI(title='Smart Skin - LOCAL DEMO API', version='0.1.0')
    api.add_middleware(CORSMiddleware,
        allow_origins=['http://localhost:3000','http://127.0.0.1:3000','http://localhost:8081','http://127.0.0.1:8081'],
        allow_methods=['GET','POST'], allow_headers=['Content-Type','X-Demo-Actor'])

    def actor(x_demo_actor: str = Header()):
        if x_demo_actor not in {*PATIENTS, *DOCTORS, 'staff-demo'}:
            raise HTTPException(401, 'Choose a recognised demo identity.')
        return x_demo_actor

    def patient(who=Depends(actor)):
        if who not in PATIENTS:
            raise HTTPException(403, 'Patient demo identity required.')
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
        if who not in {*PATIENTS, 'staff-demo'}:
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

    @api.get('/slots')
    def slots():
        return store.slots()

    @api.get('/bookings')
    def bookings(who=Depends(patient)):
        return store.mine(who)

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
        if who not in {*PATIENTS,'staff-demo'}:
            raise HTTPException(403,'Patient or staff demo identity required.')
        return run(lambda: store.reschedule(booking_id,who,payload.slot_id,payload.request_id))

    @api.get('/queue')
    def queue(doctor_id: Literal['doctor-lim','doctor-anita'], clinic_date: date, who=Depends(staff)):
        return store.queue(doctor_id, clinic_date.isoformat())

    @api.post('/queue/call-next')
    def call_next(payload: QueueInput, who=Depends(staff)):
        return run(lambda: store.call_next(payload.doctor_id, payload.clinic_date.isoformat(), who))

    @api.post('/queue/{booking_id}/complete')
    def complete(booking_id: str, who=Depends(staff)):
        return run(lambda: store.complete(booking_id, who))

    @api.get('/care')
    def care(who=Depends(actor)):
        return store.care(who)

    @api.get('/assessments')
    def assessments(who=Depends(patient)):
        return store.assessments(who)

    @api.get('/assessments/{assessment_id}')
    def assessment(assessment_id: str, who=Depends(patient)):
        return run(lambda: store.assessment(assessment_id, who))

    @api.post('/assessments', status_code=201)
    def save_assessment(photo: UploadFile = File(), request_id: str = Form(min_length=8, max_length=100), who=Depends(patient)):
        try:
            content = photo.file.read(MAX_BYTES + 1)
        finally:
            photo.file.close()
        def save():
            clean, width, height = normalise_photo(content)
            return store.save_assessment(who, request_id, hashlib.sha256(content).hexdigest(), clean, width, height)
        return run(save)

    @api.get('/medicines')
    def medicines(who=Depends(operational)):
        return store.catalog()

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
        return run(lambda: store.publish_review(share_id, who, payload.note.strip(), payload.follow_up.strip()))

    @api.post('/visits/{booking_id}/prescription')
    def prescribe(booking_id: str, payload: PrescriptionInput, who=Depends(doctor)):
        return run(lambda: store.issue_prescription(booking_id, who, [i.model_dump() for i in payload.items]))

    @api.post('/prescriptions/{prescription_id}/dispense')
    def dispense(prescription_id: str, who=Depends(staff)):
        return run(lambda: store.dispense(prescription_id, who))

    @api.get('/consultations')
    def consultations(who=Depends(actor)):
        return run(lambda: store.consultations(who))

    @api.get('/visits/{booking_id}/consultation')
    def consultation(booking_id: str, who=Depends(actor)):
        return run(lambda: store.consultation(booking_id, who))

    @api.post('/visits/{booking_id}/consultation')
    def publish_consultation(booking_id: str, payload: ConsultationInput, who=Depends(doctor)):
        return run(lambda: store.publish_consultation(booking_id,who,payload.findings.strip(),payload.follow_up.strip()))

    @api.post('/visits/{booking_id}/invoice')
    def invoice(booking_id: str, who=Depends(staff)):
        return run(lambda: store.generate_invoice(booking_id, who))

    @api.post('/invoices/{invoice_id}/pay-simulated')
    def pay(invoice_id: str, who=Depends(payer)):
        return run(lambda: store.pay_simulated(invoice_id, who))

    return api

app = create_app()
