"""Local synthetic demo storage. Keep SQL and transactions out of screens/routes."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
from uuid import uuid4

PATIENTS = {'patient-ava': 'Ava Demo', 'patient-noah': 'Noah Demo'}
DOCTORS = {'doctor-lim': 'Dr. Lim (demo)', 'doctor-anita': 'Dr. Anita (demo)'}

class RuleError(Exception):
    def __init__(self, message, status=409):
        self.message, self.status = message, status

class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS slots (
                  id TEXT PRIMARY KEY, doctor_id TEXT NOT NULL, starts_at TEXT NOT NULL,
                  clinic_date TEXT NOT NULL, capacity INTEGER NOT NULL CHECK(capacity > 0));
                CREATE TABLE IF NOT EXISTS bookings (
                  id TEXT PRIMARY KEY, patient_id TEXT NOT NULL, slot_id TEXT NOT NULL REFERENCES slots(id),
                  queue_number INTEGER NOT NULL, status TEXT NOT NULL CHECK(status IN ('waiting','called','completed','cancelled')),
                  created_at TEXT NOT NULL, request_id TEXT NOT NULL,
                  UNIQUE(patient_id, request_id));
                CREATE INDEX IF NOT EXISTS booking_slot ON bookings(slot_id, status);
                CREATE TABLE IF NOT EXISTS events (
                  id TEXT PRIMARY KEY, booking_id TEXT NOT NULL REFERENCES bookings(id),
                  actor_id TEXT NOT NULL, action TEXT NOT NULL, created_at TEXT NOT NULL);
            ''')
        self.seed()

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def seed(self):
        # UTC+8, fixed offset (Malaysia); ensure future slots after reopening days later.
        local = datetime.now(timezone(timedelta(hours=8)))
        with self.connect() as db:
            for day in (1, 2):
                for doctor in DOCTORS:
                    for hour in (9, 10, 11):
                        start = (local + timedelta(days=day)).replace(hour=hour, minute=0, second=0, microsecond=0)
                        key = f'{doctor}-{start:%Y%m%d}-{hour}'
                        db.execute('INSERT OR IGNORE INTO slots VALUES(?,?,?,?,?)',
                                   (key, doctor, start.isoformat(), start.date().isoformat(), 2))

    def slots(self):
        with self.connect() as db:
            rows = db.execute('''SELECT s.*, s.capacity - COUNT(b.id) AS available
                FROM slots s LEFT JOIN bookings b ON b.slot_id=s.id AND b.status!='cancelled'
                WHERE s.starts_at > ? GROUP BY s.id ORDER BY s.starts_at, s.doctor_id''',
                (datetime.now(timezone(timedelta(hours=8))).isoformat(),)).fetchall()
        return [dict(r, doctor_name=DOCTORS[r['doctor_id']]) for r in rows]

    def event(self, db, booking_id, actor, action):
        db.execute('INSERT INTO events VALUES(?,?,?,?,?)',
                   (str(uuid4()), booking_id, actor, action, datetime.now(timezone.utc).isoformat()))

    def record(self, db, booking_id):
        r = db.execute('''SELECT b.*, s.doctor_id, s.starts_at, s.clinic_date FROM bookings b
                          JOIN slots s ON s.id=b.slot_id WHERE b.id=?''', (booking_id,)).fetchone()
        if r is None:
            raise RuleError('Booking not found.', 404)
        return dict(r, doctor_name=DOCTORS[r['doctor_id']], patient_name=PATIENTS[r['patient_id']])

    def book(self, patient, slot_id, request_id):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            existing = db.execute('SELECT id, slot_id FROM bookings WHERE patient_id=? AND request_id=?',
                                  (patient, request_id)).fetchone()
            if existing:
                if existing['slot_id'] != slot_id:
                    raise RuleError('This request was already used for a different slot.')
                return self.record(db, existing['id'])
            slot = db.execute('SELECT * FROM slots WHERE id=?', (slot_id,)).fetchone()
            if slot is None:
                raise RuleError('Slot not found.', 404)
            if datetime.fromisoformat(slot['starts_at']) <= datetime.now(timezone.utc):
                raise RuleError('This slot has already started. Choose another time.')
            if db.execute("SELECT 1 FROM bookings WHERE patient_id=? AND slot_id=? AND status!='cancelled'",
                          (patient, slot_id)).fetchone():
                raise RuleError('You already have a booking for this slot.')
            used = db.execute("SELECT COUNT(*) FROM bookings WHERE slot_id=? AND status!='cancelled'", (slot_id,)).fetchone()[0]
            if used >= slot['capacity']:
                raise RuleError('This slot is full. Please choose another time.')
            number = db.execute('''SELECT COALESCE(MAX(b.queue_number),0)+1 FROM bookings b JOIN slots s ON s.id=b.slot_id
                WHERE s.doctor_id=? AND s.clinic_date=?''', (slot['doctor_id'], slot['clinic_date'])).fetchone()[0]
            booking_id = str(uuid4())
            db.execute('INSERT INTO bookings VALUES(?,?,?,?,?,?,?)',
                       (booking_id, patient, slot_id, number, 'waiting', datetime.now(timezone.utc).isoformat(), request_id))
            self.event(db, booking_id, patient, 'booked')
            return self.record(db, booking_id)

    def mine(self, patient):
        with self.connect() as db:
            ids = db.execute('SELECT id FROM bookings WHERE patient_id=? ORDER BY created_at DESC', (patient,)).fetchall()
            return [self.record(db, r['id']) for r in ids]

    def queue(self, doctor, date):
        with self.connect() as db:
            ids = db.execute('''SELECT b.id FROM bookings b JOIN slots s ON s.id=b.slot_id
                WHERE s.doctor_id=? AND s.clinic_date=? ORDER BY s.starts_at, b.queue_number''', (doctor, date)).fetchall()
            return [self.record(db, r['id']) for r in ids]

    def cancel(self, booking_id, patient):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            record = self.record(db, booking_id)
            if record['patient_id'] != patient:
                raise RuleError('You cannot access this booking.', 403)
            if record['status'] == 'cancelled':
                return record
            if record['status'] != 'waiting':
                raise RuleError('Only waiting bookings can be cancelled. Contact staff.')
            if datetime.fromisoformat(record['starts_at']) <= datetime.now(timezone.utc):
                raise RuleError('This appointment has started. Contact staff.')
            db.execute("UPDATE bookings SET status='cancelled' WHERE id=?", (booking_id,))
            self.event(db, booking_id, patient, 'cancelled')
            return self.record(db, booking_id)

    def call_next(self, doctor, date, staff):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            active = db.execute('''SELECT b.id FROM bookings b JOIN slots s ON s.id=b.slot_id
                WHERE s.doctor_id=? AND s.clinic_date=? AND b.status='called' ''', (doctor, date)).fetchone()
            if active:
                raise RuleError('Complete the currently called patient before calling another.')
            row = db.execute('''SELECT b.id FROM bookings b JOIN slots s ON s.id=b.slot_id
                WHERE s.doctor_id=? AND s.clinic_date=? AND b.status='waiting'
                ORDER BY s.starts_at, b.queue_number LIMIT 1''', (doctor, date)).fetchone()
            if not row:
                raise RuleError('No patients are currently waiting.')
            db.execute("UPDATE bookings SET status='called' WHERE id=?", (row['id'],))
            self.event(db, row['id'], staff, 'called')
            return self.record(db, row['id'])

    def complete(self, booking_id, staff):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            record = self.record(db, booking_id)
            if record['status'] == 'completed':
                return record
            if record['status'] != 'called':
                raise RuleError('Only a called patient can be marked completed.')
            db.execute("UPDATE bookings SET status='completed' WHERE id=?", (booking_id,))
            self.event(db, booking_id, staff, 'completed')
            return self.record(db, booking_id)
