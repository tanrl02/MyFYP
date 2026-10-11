from datetime import date
import os
from pathlib import Path
from typing import Literal
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from .store import DOCTORS, PATIENTS, RuleError, Store

class BookingInput(BaseModel):
    slot_id: str = Field(min_length=1, max_length=100)
    request_id: str = Field(min_length=8, max_length=100)

class QueueInput(BaseModel):
    doctor_id: Literal['doctor-lim', 'doctor-anita']
    clinic_date: date

class PrescriptionItemInput(BaseModel):
    medicine_id: str = Field(min_length=1, max_length=100)
    quantity: int = Field(strict=True, ge=1, le=20)
    directions: str = Field(min_length=1, max_length=300, pattern=r'\S')

class PrescriptionInput(BaseModel):
    items: list[PrescriptionItemInput] = Field(min_length=1, max_length=10)

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

    @api.get('/medicines')
    def medicines(who=Depends(operational)):
        return store.catalog()

    @api.post('/visits/{booking_id}/prescription')
    def prescribe(booking_id: str, payload: PrescriptionInput, who=Depends(doctor)):
        return run(lambda: store.issue_prescription(booking_id, who, [i.model_dump() for i in payload.items]))

    @api.post('/prescriptions/{prescription_id}/dispense')
    def dispense(prescription_id: str, who=Depends(staff)):
        return run(lambda: store.dispense(prescription_id, who))

    @api.post('/visits/{booking_id}/invoice')
    def invoice(booking_id: str, who=Depends(staff)):
        return run(lambda: store.generate_invoice(booking_id, who))

    @api.post('/invoices/{invoice_id}/pay-simulated')
    def pay(invoice_id: str, who=Depends(payer)):
        return run(lambda: store.pay_simulated(invoice_id, who))

    return api

app = create_app()
