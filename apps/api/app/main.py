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

def create_app(path=None):
    store = Store(path or os.getenv('DEMO_DATABASE', str(Path(__file__).parents[1] / 'data/demo.sqlite3')))
    api = FastAPI(title='Smart Skin - LOCAL DEMO API', version='0.1.0')
    api.add_middleware(CORSMiddleware,
        allow_origins=['http://localhost:3000','http://127.0.0.1:3000','http://localhost:8081','http://127.0.0.1:8081'],
        allow_methods=['GET','POST'], allow_headers=['Content-Type','X-Demo-Actor'])

    def actor(x_demo_actor: str = Header()):
        if x_demo_actor not in {*PATIENTS, 'staff-demo'}:
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

    return api

app = create_app()
