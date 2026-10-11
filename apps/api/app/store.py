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
                CREATE TABLE IF NOT EXISTS medicines (
                  id TEXT PRIMARY KEY, name TEXT NOT NULL, price_cents INTEGER NOT NULL CHECK(price_cents>=0),
                  stock INTEGER NOT NULL CHECK(stock>=0));
                CREATE TABLE IF NOT EXISTS prescriptions (
                  id TEXT PRIMARY KEY, booking_id TEXT NOT NULL UNIQUE REFERENCES bookings(id),
                  doctor_id TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('issued','dispensed')),
                  created_at TEXT NOT NULL, dispensed_at TEXT);
                CREATE TABLE IF NOT EXISTS prescription_items (
                  prescription_id TEXT NOT NULL REFERENCES prescriptions(id), medicine_id TEXT NOT NULL REFERENCES medicines(id),
                  quantity INTEGER NOT NULL CHECK(quantity>0), directions TEXT NOT NULL,
                  PRIMARY KEY(prescription_id,medicine_id));
                CREATE TABLE IF NOT EXISTS invoices (
                  id TEXT PRIMARY KEY, booking_id TEXT NOT NULL UNIQUE REFERENCES bookings(id),
                  total_cents INTEGER NOT NULL CHECK(total_cents>=0), status TEXT NOT NULL CHECK(status IN ('unpaid','paid')),
                  created_at TEXT NOT NULL, paid_at TEXT, payment_mode TEXT);
                CREATE TABLE IF NOT EXISTS invoice_lines (
                  id TEXT PRIMARY KEY, invoice_id TEXT NOT NULL REFERENCES invoices(id),
                  description TEXT NOT NULL, quantity INTEGER NOT NULL CHECK(quantity>0),
                  unit_price_cents INTEGER NOT NULL CHECK(unit_price_cents>=0));
                CREATE TABLE IF NOT EXISTS assessments (
                  id TEXT PRIMARY KEY, patient_id TEXT NOT NULL, request_id TEXT NOT NULL,
                  source_hash TEXT NOT NULL, photo BLOB NOT NULL, width INTEGER NOT NULL,
                  height INTEGER NOT NULL, created_at TEXT NOT NULL, UNIQUE(patient_id, request_id));
            ''')
            db.executemany('INSERT OR IGNORE INTO medicines VALUES(?,?,?,?)', [
                ('demo-a', 'Demo item A (not medication)', 500, 20),
                ('demo-b', 'Demo item B (not medication)', 800, 20)])
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

    def catalog(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute('SELECT * FROM medicines ORDER BY id')]

    def assessment_metadata(self, row):
        return {key: row[key] for key in ('id', 'patient_id', 'width', 'height', 'created_at')} | {
            'origin': 'simulation', 'example_category': 'Acne (example only)',
            'message': 'No image analysis was performed. This example is not a diagnosis.'}

    def assessments(self, patient):
        with self.connect() as db:
            rows = db.execute('SELECT id,patient_id,width,height,created_at FROM assessments WHERE patient_id=? ORDER BY created_at DESC LIMIT 100', (patient,)).fetchall()
            return [self.assessment_metadata(row) for row in rows]

    def assessment(self, assessment_id, patient):
        import base64
        with self.connect() as db:
            row = db.execute('SELECT * FROM assessments WHERE id=? AND patient_id=?', (assessment_id, patient)).fetchone()
            if row is None:
                raise RuleError('Assessment not found for this patient.', 404)
            return self.assessment_metadata(row) | {'photo_uri': 'data:image/jpeg;base64,' + base64.b64encode(row['photo']).decode('ascii')}

    def save_assessment(self, patient, request_id, source_hash, photo, width, height):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            existing = db.execute('SELECT id,source_hash FROM assessments WHERE patient_id=? AND request_id=?', (patient, request_id)).fetchone()
            if existing:
                if existing['source_hash'] != source_hash:
                    raise RuleError('This request already saved a different photo. Refresh history.')
                assessment_id = existing['id']
            else:
                assessment_id = str(uuid4())
                db.execute('INSERT INTO assessments VALUES(?,?,?,?,?,?,?,?)',
                    (assessment_id, patient, request_id, source_hash, photo, width, height, datetime.now(timezone.utc).isoformat()))
        return self.assessment(assessment_id, patient)

    def prescription(self, db, booking_id):
        row = db.execute('SELECT * FROM prescriptions WHERE booking_id=?', (booking_id,)).fetchone()
        if not row:
            return None
        items = db.execute('''SELECT i.medicine_id,i.quantity,i.directions,m.name,m.price_cents
            FROM prescription_items i JOIN medicines m ON m.id=i.medicine_id
            WHERE i.prescription_id=? ORDER BY i.medicine_id''', (row['id'],)).fetchall()
        return dict(row, items=[dict(i) for i in items])

    def invoice(self, db, booking_id):
        row = db.execute('SELECT * FROM invoices WHERE booking_id=?', (booking_id,)).fetchone()
        if not row:
            return None
        lines = db.execute('SELECT description,quantity,unit_price_cents FROM invoice_lines WHERE invoice_id=? ORDER BY rowid', (row['id'],)).fetchall()
        return dict(row, lines=[dict(line) for line in lines])

    def care(self, actor):
        with self.connect() as db:
            records = []
            for row in db.execute('SELECT id FROM bookings ORDER BY created_at DESC').fetchall():
                visit = self.record(db, row['id'])
                if actor in PATIENTS and visit['patient_id'] != actor:
                    continue
                if actor in DOCTORS and visit['doctor_id'] != actor:
                    continue
                records.append({'visit': visit, 'prescription': self.prescription(db, row['id']),
                                'invoice': self.invoice(db, row['id'])})
            return records

    def issue_prescription(self, booking_id, doctor, items):
        # Immutable issued items keep dispensing/billing consistent. Retry same content safely.
        normalised = sorted(items, key=lambda i: i['medicine_id'])
        if len({i['medicine_id'] for i in items}) != len(items):
            raise RuleError('Choose each demo item only once.', 422)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            visit = self.record(db, booking_id)
            if visit['doctor_id'] != doctor:
                raise RuleError('This visit belongs to another doctor.', 403)
            if visit['status'] not in ('called', 'completed'):
                raise RuleError('Call the patient before issuing a prescription.')
            existing = self.prescription(db, booking_id)
            if existing:
                saved = [{key: i[key] for key in ('medicine_id', 'quantity', 'directions')} for i in existing['items']]
                if saved != normalised:
                    raise RuleError('A prescription is already issued. Saved items cannot be replaced in this demo.')
                return existing
            if self.invoice(db, booking_id):
                raise RuleError('This visit has been billed. A prescription cannot be added afterwards.')
            for item in normalised:
                if not db.execute('SELECT 1 FROM medicines WHERE id=?', (item['medicine_id'],)).fetchone():
                    raise RuleError('Unknown demo item.', 422)
            prescription_id = str(uuid4())
            db.execute('INSERT INTO prescriptions VALUES(?,?,?,?,?,NULL)',
                       (prescription_id, booking_id, doctor, 'issued', datetime.now(timezone.utc).isoformat()))
            db.executemany('INSERT INTO prescription_items VALUES(?,?,?,?)',
                [(prescription_id, i['medicine_id'], i['quantity'], i['directions']) for i in normalised])
            self.event(db, booking_id, doctor, 'prescription-issued')
            return self.prescription(db, booking_id)

    def dispense(self, prescription_id, staff):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT booking_id FROM prescriptions WHERE id=?', (prescription_id,)).fetchone()
            if not row:
                raise RuleError('Prescription not found.', 404)
            prescription = self.prescription(db, row['booking_id'])
            if prescription['status'] == 'dispensed':
                return prescription
            for item in prescription['items']:
                result = db.execute('UPDATE medicines SET stock=stock-? WHERE id=? AND stock>=?',
                                    (item['quantity'], item['medicine_id'], item['quantity']))
                if result.rowcount != 1:
                    raise RuleError('Insufficient demo stock. Nothing was dispensed.')
            db.execute("UPDATE prescriptions SET status='dispensed',dispensed_at=? WHERE id=?",
                       (datetime.now(timezone.utc).isoformat(), prescription_id))
            self.event(db, row['booking_id'], staff, 'prescription-dispensed')
            return self.prescription(db, row['booking_id'])

    def generate_invoice(self, booking_id, staff):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            visit = self.record(db, booking_id)
            if visit['status'] != 'completed':
                raise RuleError('Complete the visit before generating a bill.')
            existing = self.invoice(db, booking_id)
            if existing:
                return existing
            lines = [('Demo consultation', 1, 3000)]
            prescription = self.prescription(db, booking_id)
            if prescription:
                lines.extend((i['name'], i['quantity'], i['price_cents']) for i in prescription['items'])
            invoice_id = str(uuid4())
            total = sum(quantity * price for _, quantity, price in lines)
            db.execute('INSERT INTO invoices VALUES(?,?,?,?,?,NULL,NULL)',
                       (invoice_id, booking_id, total, 'unpaid', datetime.now(timezone.utc).isoformat()))
            db.executemany('INSERT INTO invoice_lines VALUES(?,?,?,?,?)',
                [(str(uuid4()), invoice_id, name, quantity, price) for name, quantity, price in lines])
            self.event(db, booking_id, staff, 'invoice-generated')
            return self.invoice(db, booking_id)

    def pay_simulated(self, invoice_id, actor):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT booking_id FROM invoices WHERE id=?', (invoice_id,)).fetchone()
            if not row:
                raise RuleError('Bill not found.', 404)
            visit = self.record(db, row['booking_id'])
            if actor != 'staff-demo' and visit['patient_id'] != actor:
                raise RuleError('You cannot pay this bill.', 403)
            invoice = self.invoice(db, row['booking_id'])
            if invoice['status'] == 'paid':
                return invoice
            prescription = self.prescription(db, row['booking_id'])
            if prescription and prescription['status'] != 'dispensed':
                raise RuleError('Dispense the prescription before recording simulated payment.')
            db.execute("UPDATE invoices SET status='paid',paid_at=?,payment_mode='simulation' WHERE id=?",
                       (datetime.now(timezone.utc).isoformat(), invoice_id))
            self.event(db, row['booking_id'], actor, 'payment-simulated')
            return self.invoice(db, row['booking_id'])
