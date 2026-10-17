"""Local synthetic demo storage. Keep SQL and transactions out of screens/routes."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import json
from uuid import uuid4

PATIENTS = {'patient-ava': 'Ava Demo', 'patient-noah': 'Noah Demo'}
DOCTORS = {'doctor-lim': 'Dr. Lim (demo)', 'doctor-anita': 'Dr. Anita (demo)'}
DOCTOR_CONCERNS = {'general', 'acne', 'eczema', 'psoriasis'}

class RuleError(Exception):
    def __init__(self, message, status=409):
        self.message, self.status = message, status

class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS doctor_profiles (
                  doctor_id TEXT PRIMARY KEY, specialty TEXT NOT NULL, expertise TEXT NOT NULL,
                  version INTEGER NOT NULL, updated_at TEXT);
                CREATE TABLE IF NOT EXISTS patient_notifications (
                  id TEXT PRIMARY KEY, patient_id TEXT NOT NULL, kind TEXT NOT NULL,
                  source_id TEXT NOT NULL, target_id TEXT NOT NULL, title TEXT NOT NULL,
                  message TEXT NOT NULL, created_at TEXT NOT NULL, read_at TEXT,
                  UNIQUE(patient_id,kind,source_id));
                CREATE TABLE IF NOT EXISTS patient_backgrounds (
                  patient_id TEXT PRIMARY KEY, allergies TEXT NOT NULL, medicines TEXT NOT NULL,
                  conditions TEXT NOT NULL, version INTEGER NOT NULL, updated_at TEXT NOT NULL);
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
                CREATE TABLE IF NOT EXISTS reschedules (
                  actor_id TEXT NOT NULL, request_id TEXT NOT NULL, old_booking_id TEXT NOT NULL REFERENCES bookings(id),
                  new_booking_id TEXT NOT NULL REFERENCES bookings(id), slot_id TEXT NOT NULL REFERENCES slots(id),
                  created_at TEXT NOT NULL, PRIMARY KEY(actor_id,request_id));
                CREATE TABLE IF NOT EXISTS medicines (
                  id TEXT PRIMARY KEY, name TEXT NOT NULL, price_cents INTEGER NOT NULL CHECK(price_cents>=0),
                  stock INTEGER NOT NULL CHECK(stock>=0));
                CREATE TABLE IF NOT EXISTS stock_receipts (
                  id TEXT PRIMARY KEY, medicine_id TEXT NOT NULL REFERENCES medicines(id),
                  quantity INTEGER NOT NULL CHECK(quantity>0), reason TEXT NOT NULL,
                  stock_before INTEGER NOT NULL, stock_after INTEGER NOT NULL,
                  actor_id TEXT NOT NULL, request_id TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL);
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
                CREATE TABLE IF NOT EXISTS assessment_shares (
                  id TEXT PRIMARY KEY, assessment_id TEXT NOT NULL REFERENCES assessments(id),
                  patient_id TEXT NOT NULL, doctor_id TEXT NOT NULL, patient_message TEXT NOT NULL,
                  request_id TEXT NOT NULL, created_at TEXT NOT NULL, revoked_at TEXT,
                  UNIQUE(patient_id,request_id));
                CREATE TABLE IF NOT EXISTS assessment_reviews (
                  id TEXT PRIMARY KEY, share_id TEXT NOT NULL UNIQUE REFERENCES assessment_shares(id),
                  doctor_id TEXT NOT NULL, note TEXT NOT NULL, follow_up TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS consultation_notes (
                  id TEXT PRIMARY KEY, booking_id TEXT NOT NULL UNIQUE REFERENCES bookings(id),
                  doctor_id TEXT NOT NULL, findings TEXT NOT NULL, follow_up TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS visit_feedback (
                  id TEXT PRIMARY KEY, booking_id TEXT NOT NULL UNIQUE REFERENCES bookings(id),
                  patient_id TEXT NOT NULL, rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
                  comment TEXT NOT NULL, created_at TEXT NOT NULL);
            ''')
            for column, definition in [('closed', 'INTEGER NOT NULL DEFAULT 0'),('request_id','TEXT')]:
                if column not in {row['name'] for row in db.execute('PRAGMA table_info(slots)')}:
                    db.execute(f'ALTER TABLE slots ADD COLUMN {column} {definition}')
            db.execute('CREATE UNIQUE INDEX IF NOT EXISTS slot_request ON slots(request_id) WHERE request_id IS NOT NULL')
            if 'booking_id' not in {row['name'] for row in db.execute('PRAGMA table_info(assessment_shares)')}:
                db.execute('ALTER TABLE assessment_shares ADD COLUMN booking_id TEXT REFERENCES bookings(id)')
            db.execute('DROP INDEX IF EXISTS active_assessment_share')
            db.execute('''CREATE UNIQUE INDEX IF NOT EXISTS active_direct_share ON assessment_shares(assessment_id,doctor_id)
                          WHERE revoked_at IS NULL AND booking_id IS NULL''')
            db.execute('''CREATE UNIQUE INDEX IF NOT EXISTS active_visit_share ON assessment_shares(booking_id)
                          WHERE revoked_at IS NULL AND booking_id IS NOT NULL''')
            for column, definition in [('strength',"TEXT NOT NULL DEFAULT ''"),('form',"TEXT NOT NULL DEFAULT ''"),('request_id','TEXT')]:
                if column not in {r['name'] for r in db.execute('PRAGMA table_info(medicines)')}:
                    db.execute(f'ALTER TABLE medicines ADD COLUMN {column} {definition}')
            db.execute('CREATE UNIQUE INDEX IF NOT EXISTS medicine_request ON medicines(request_id) WHERE request_id IS NOT NULL')
            db.executemany('INSERT OR IGNORE INTO medicines(id,name,price_cents,stock) VALUES(?,?,?,?)', [
                ('demo-a', 'Demo item A (not medication)', 500, 20),
                ('demo-b', 'Demo item B (not medication)', 800, 20)])
            for column, definition in [('name','TEXT'),('price_cents','INTEGER'),('strength','TEXT'),('form','TEXT')]:
                if column not in {r['name'] for r in db.execute('PRAGMA table_info(prescription_items)')}:
                    db.execute(f'ALTER TABLE prescription_items ADD COLUMN {column} {definition}')
            db.execute('''UPDATE prescription_items SET
                name=(SELECT name FROM medicines WHERE id=medicine_id),
                price_cents=(SELECT price_cents FROM medicines WHERE id=medicine_id),
                strength=(SELECT strength FROM medicines WHERE id=medicine_id),
                form=(SELECT form FROM medicines WHERE id=medicine_id) WHERE name IS NULL''')
            for doctor in DOCTORS:
                db.execute('INSERT OR IGNORE INTO doctor_profiles VALUES(?,?,?,?,NULL)',
                           (doctor, 'Not specified', '[]', 0))
        self.seed()

    @staticmethod
    def doctor_profile(row):
        return dict(row, doctor_name=DOCTORS[row['doctor_id']], expertise=json.loads(row['expertise']))

    def doctor_profiles(self):
        with self.connect() as db:
            return [self.doctor_profile(row) for row in db.execute('SELECT * FROM doctor_profiles ORDER BY doctor_id')]

    def save_doctor_profile(self, doctor, specialty, expertise, version):
        specialty = specialty.strip()
        if not specialty or len(specialty)>80 or not set(expertise)<=DOCTOR_CONCERNS or len(expertise)!=len(set(expertise)):
            raise RuleError('Enter a specialty and choose distinct supported areas of expertise.', 422)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM doctor_profiles WHERE doctor_id=?', (doctor,)).fetchone()
            if row is None:
                raise RuleError('Doctor not found.', 404)
            current = self.doctor_profile(row)
            expertise = sorted(expertise)
            # A retry after a lost response is harmless, including an old version.
            if (current['specialty'], sorted(current['expertise'])) == (specialty, expertise):
                return current
            if row['version'] != version:
                raise RuleError('This profile changed. Reload profiles before editing again.')
            db.execute('UPDATE doctor_profiles SET specialty=?,expertise=?,version=version+1,updated_at=? WHERE doctor_id=?',
                       (specialty,json.dumps(expertise),datetime.now(timezone.utc).isoformat(),doctor))
            return self.doctor_profile(db.execute('SELECT * FROM doctor_profiles WHERE doctor_id=?',(doctor,)).fetchone())

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
                        db.execute('INSERT OR IGNORE INTO slots(id,doctor_id,starts_at,clinic_date,capacity) VALUES(?,?,?,?,?)',
                                   (key, doctor, start.isoformat(), start.date().isoformat(), 2))

    def slots(self):
        with self.connect() as db:
            rows = db.execute('''SELECT s.id,s.doctor_id,s.starts_at,s.clinic_date,s.capacity, s.capacity - COUNT(b.id) AS available
                FROM slots s LEFT JOIN bookings b ON b.slot_id=s.id AND b.status!='cancelled'
                WHERE s.starts_at > ? AND s.closed=0 GROUP BY s.id ORDER BY s.starts_at, s.doctor_id''',
                (datetime.now(timezone(timedelta(hours=8))).isoformat(),)).fetchall()
        return [dict(r, doctor_name=DOCTORS[r['doctor_id']]) for r in rows]

    def managed_slot(self, db, slot_id):
        row = db.execute('''SELECT s.*,COUNT(b.id) AS booking_count,
                            s.capacity-SUM(CASE WHEN b.id IS NOT NULL AND b.status!='cancelled' THEN 1 ELSE 0 END) AS available
                            FROM slots s LEFT JOIN bookings b ON b.slot_id=s.id WHERE s.id=? GROUP BY s.id''',(slot_id,)).fetchone()
        if not row:
            raise RuleError('Slot not found.',404)
        return {key:row[key] for key in ('id','doctor_id','starts_at','clinic_date','capacity','closed','booking_count','available')} | {'doctor_name':DOCTORS[row['doctor_id']]}

    def managed_slots(self):
        with self.connect() as db:
            db.execute('BEGIN')
            rows=db.execute('SELECT id FROM slots WHERE starts_at>? ORDER BY starts_at,doctor_id',(datetime.now(timezone(timedelta(hours=8))).isoformat(),)).fetchall()
            return [self.managed_slot(db,row['id']) for row in rows]

    def add_slot(self, doctor, clinic_date, time, capacity, request_id):
        start=datetime.fromisoformat(f'{clinic_date}T{time}:00+08:00')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT id FROM slots WHERE request_id=?',(request_id,)).fetchone()
            if old:
                slot=self.managed_slot(db,old['id'])
                if (slot['doctor_id'],slot['starts_at'],slot['capacity'])!=(doctor,start.isoformat(),capacity):
                    raise RuleError('This request already saved different slot details.')
                return slot
            if start<=datetime.now(timezone.utc):
                raise RuleError('Choose a future date and time.')
            if db.execute('SELECT 1 FROM slots WHERE doctor_id=? AND starts_at=?',(doctor,start.isoformat())).fetchone():
                raise RuleError('This doctor already has a slot at that time, including closed slots.')
            slot_id=str(uuid4())
            db.execute('INSERT INTO slots(id,doctor_id,starts_at,clinic_date,capacity,request_id) VALUES(?,?,?,?,?,?)',
                       (slot_id,doctor,start.isoformat(),clinic_date,capacity,request_id))
            return self.managed_slot(db,slot_id)

    def close_slot(self, slot_id):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            slot=self.managed_slot(db,slot_id)
            if slot['closed']:
                return slot
            if slot['booking_count']:
                raise RuleError('This slot has booking history and cannot be closed. Its visit records are retained.')
            if datetime.fromisoformat(slot['starts_at'])<=datetime.now(timezone.utc):
                raise RuleError('This slot has already started.')
            db.execute('UPDATE slots SET closed=1 WHERE id=?',(slot_id,))
            return self.managed_slot(db,slot_id)

    def event(self, db, booking_id, actor, action):
        db.execute('INSERT INTO events VALUES(?,?,?,?,?)',
                   (str(uuid4()), booking_id, actor, action, datetime.now(timezone.utc).isoformat()))

    def notify(self, db, patient, kind, source_id, target_id, title, message):
        db.execute('INSERT OR IGNORE INTO patient_notifications VALUES(?,?,?,?,?,?,?,?,NULL)',
                   (str(uuid4()),patient,kind,source_id,target_id,title,message,datetime.now(timezone.utc).isoformat()))

    def notifications(self, patient):
        if patient not in PATIENTS:
            raise RuleError('Patient identity required.',403)
        with self.connect() as db:
            db.execute('BEGIN')
            rows=db.execute('SELECT * FROM patient_notifications WHERE patient_id=? ORDER BY created_at DESC,id DESC LIMIT 100',(patient,)).fetchall()
            unread=db.execute('SELECT COUNT(*) FROM patient_notifications WHERE patient_id=? AND read_at IS NULL',(patient,)).fetchone()[0]
            return {'items':[dict(row) for row in rows],'unread_count':unread}

    def read_notification(self, notification_id, patient):
        if patient not in PATIENTS:
            raise RuleError('Patient identity required.',403)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT * FROM patient_notifications WHERE id=? AND patient_id=?',(notification_id,patient)).fetchone()
            if not row:
                raise RuleError('Notification unavailable for this patient.',404)
            if not row['read_at']:
                db.execute('UPDATE patient_notifications SET read_at=? WHERE id=?',(datetime.now(timezone.utc).isoformat(),notification_id))
            return dict(db.execute('SELECT * FROM patient_notifications WHERE id=?',(notification_id,)).fetchone())

    def record(self, db, booking_id):
        r = db.execute('''SELECT b.*, s.doctor_id, s.starts_at, s.clinic_date FROM bookings b
                          JOIN slots s ON s.id=b.slot_id WHERE b.id=?''', (booking_id,)).fetchone()
        if r is None:
            raise RuleError('Booking not found.', 404)
        replacement = db.execute('SELECT new_booking_id FROM reschedules WHERE old_booking_id=?',(booking_id,)).fetchone()
        return dict(r, doctor_name=DOCTORS[r['doctor_id']], patient_name=PATIENTS[r['patient_id']],
                    rescheduled_to_id=replacement['new_booking_id'] if replacement else None)

    def book(self, patient, slot_id, request_id, created_by=None):
        if patient not in PATIENTS:
            raise RuleError('Choose a recognised demo patient.', 422)
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
            if slot['closed']:
                raise RuleError('This slot is closed. Choose another time.')
            if datetime.fromisoformat(slot['starts_at']) <= datetime.now(timezone.utc):
                raise RuleError('This slot has already started. Choose another time.')
            if db.execute("SELECT 1 FROM bookings WHERE patient_id=? AND slot_id=? AND status!='cancelled'",
                          (patient, slot_id)).fetchone():
                raise RuleError('This patient already has a booking for this slot.')
            used = db.execute("SELECT COUNT(*) FROM bookings WHERE slot_id=? AND status!='cancelled'", (slot_id,)).fetchone()[0]
            if used >= slot['capacity']:
                raise RuleError('This slot is full. Please choose another time.')
            number = db.execute('''SELECT COALESCE(MAX(b.queue_number),0)+1 FROM bookings b JOIN slots s ON s.id=b.slot_id
                WHERE s.doctor_id=? AND s.clinic_date=?''', (slot['doctor_id'], slot['clinic_date'])).fetchone()[0]
            booking_id = str(uuid4())
            db.execute('INSERT INTO bookings VALUES(?,?,?,?,?,?,?)',
                       (booking_id, patient, slot_id, number, 'waiting', datetime.now(timezone.utc).isoformat(), request_id))
            self.event(db, booking_id, created_by or patient, 'counter-booked' if created_by else 'booked')
            return self.record(db, booking_id)

    def mine(self, patient):
        with self.connect() as db:
            ids = db.execute('SELECT id FROM bookings WHERE patient_id=? ORDER BY created_at DESC', (patient,)).fetchall()
            return [self.record(db, r['id']) for r in ids]

    def visit_details(self, booking_id, patient):
        with self.connect() as db:
            db.execute('BEGIN')
            visit=self.record(db,booking_id)
            if patient not in PATIENTS or visit['patient_id']!=patient:
                raise RuleError('Visit unavailable for this patient.',404)
            note=db.execute('SELECT * FROM consultation_notes WHERE booking_id=?',(booking_id,)).fetchone()
            linked=[]
            for row in db.execute('SELECT id FROM assessment_shares WHERE booking_id=? ORDER BY created_at DESC LIMIT 100',(booking_id,)).fetchall():
                share=self.share_record(db,row['id'],patient)
                assessment=db.execute('SELECT id,patient_id,width,height,created_at FROM assessments WHERE id=?',(share['assessment_id'],)).fetchone()
                linked.append(dict(share,assessment=self.assessment_metadata(assessment)))
            feedback=db.execute('SELECT * FROM visit_feedback WHERE booking_id=?',(booking_id,)).fetchone()
            replacement=self.record(db,visit['rescheduled_to_id']) if visit['rescheduled_to_id'] else None
            return {'visit':visit,'linked_shares':linked,'note':dict(note) if note else None,
                    'prescription':self.prescription(db,booking_id),'invoice':self.invoice(db,booking_id),
                    'feedback':dict(feedback) if feedback else None,'replacement':replacement}

    def feedback(self, actor):
        if actor not in {*PATIENTS,'staff-demo'}:
            raise RuleError('Patient or staff demo identity required.',403)
        with self.connect() as db:
            rows = db.execute('''SELECT * FROM visit_feedback WHERE (?='staff-demo' OR patient_id=?)
                ORDER BY created_at DESC LIMIT 100''',(actor,actor)).fetchall()
            return [dict(row,visit=self.record(db,row['booking_id'])) for row in rows]

    def submit_feedback(self, booking_id, patient, rating, comment):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            visit=self.record(db,booking_id)
            if patient not in PATIENTS or visit['patient_id']!=patient:
                raise RuleError('You cannot submit feedback for this visit.',403)
            if visit['status']!='completed':
                raise RuleError('Feedback is available after the visit is completed.')
            if type(rating) is not int or not 1<=rating<=5 or len(comment)>1000:
                raise RuleError('Choose a rating from 1 to 5 and a comment up to 1000 characters.',422)
            existing=db.execute('SELECT * FROM visit_feedback WHERE booking_id=?',(booking_id,)).fetchone()
            if existing:
                if existing['rating']!=rating or existing['comment']!=comment:
                    raise RuleError('Feedback was already submitted for this visit. Refresh to view it.')
                return dict(existing,visit=visit)
            feedback_id=str(uuid4())
            db.execute('INSERT INTO visit_feedback VALUES(?,?,?,?,?,?)',(feedback_id,booking_id,patient,rating,comment,datetime.now(timezone.utc).isoformat()))
            self.event(db,booking_id,patient,'feedback-submitted')
            return dict(db.execute('SELECT * FROM visit_feedback WHERE id=?',(feedback_id,)).fetchone(),visit=visit)

    def reschedule(self, booking_id, actor, slot_id, request_id):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            old = self.record(db, booking_id)
            if actor != 'staff-demo' and actor != old['patient_id']:
                raise RuleError('You cannot reschedule this booking.', 403)
            retry = db.execute('SELECT * FROM reschedules WHERE actor_id=? AND request_id=?', (actor,request_id)).fetchone()
            if retry:
                if retry['old_booking_id'] != booking_id or retry['slot_id'] != slot_id:
                    raise RuleError('This reschedule request was already used for a different visit or time.')
                return self.record(db,retry['new_booking_id'])
            if old['status'] != 'waiting' or datetime.fromisoformat(old['starts_at']) <= datetime.now(timezone.utc):
                raise RuleError('Only future waiting visits can be rescheduled.')
            if old['slot_id'] == slot_id:
                raise RuleError('Choose a different appointment time.')
            slot = db.execute('SELECT * FROM slots WHERE id=?',(slot_id,)).fetchone()
            if slot is None:
                raise RuleError('Slot not found.',404)
            if slot['closed']:
                raise RuleError('This slot is closed. Choose another time.')
            if datetime.fromisoformat(slot['starts_at']) <= datetime.now(timezone.utc):
                raise RuleError('This slot has already started. Choose another time.')
            if db.execute("SELECT 1 FROM bookings WHERE patient_id=? AND slot_id=? AND status!='cancelled'",(old['patient_id'],slot_id)).fetchone():
                raise RuleError('This patient already has a booking for this slot.')
            used = db.execute("SELECT COUNT(*) FROM bookings WHERE slot_id=? AND status!='cancelled'",(slot_id,)).fetchone()[0]
            if used >= slot['capacity']:
                raise RuleError('This slot is full. Your original booking is unchanged.')
            number = db.execute('''SELECT COALESCE(MAX(b.queue_number),0)+1 FROM bookings b JOIN slots s ON s.id=b.slot_id
                WHERE s.doctor_id=? AND s.clinic_date=?''',(slot['doctor_id'],slot['clinic_date'])).fetchone()[0]
            new_id, now = str(uuid4()), datetime.now(timezone.utc).isoformat()
            db.execute("UPDATE bookings SET status='cancelled' WHERE id=?",(booking_id,))
            db.execute('INSERT INTO bookings VALUES(?,?,?,?,?,?,?)',(new_id,old['patient_id'],slot_id,number,'waiting',now,'reschedule-'+new_id))
            if slot['doctor_id'] == old['doctor_id']:
                db.execute('UPDATE assessment_shares SET booking_id=? WHERE booking_id=? AND revoked_at IS NULL',(new_id,booking_id))
            else:
                db.execute('UPDATE assessment_shares SET revoked_at=? WHERE booking_id=? AND revoked_at IS NULL',(now,booking_id))
            db.execute('INSERT INTO reschedules VALUES(?,?,?,?,?,?)',(actor,request_id,booking_id,new_id,slot_id,now))
            self.event(db,booking_id,actor,'rescheduled-from')
            self.event(db,new_id,actor,'rescheduled-to')
            return self.record(db,new_id)

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
            db.execute('UPDATE assessment_shares SET revoked_at=? WHERE booking_id=? AND revoked_at IS NULL',
                       (datetime.now(timezone.utc).isoformat(),booking_id))
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
            visit=self.record(db,row['id'])
            token=f"{'L' if doctor=='doctor-lim' else 'A'}{visit['queue_number']:03d}"
            self.notify(db,visit['patient_id'],'queue_called',row['id'],row['id'],'Your queue number was called',
                        f"{token} with {DOCTORS[doctor]} was called. Open the visit to check its current status.")
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
            return [dict(r) for r in db.execute('SELECT id,name,strength,form,price_cents,stock FROM medicines ORDER BY id')]

    def add_medicine(self, name, strength, form, price_cents, request_id):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT * FROM medicines WHERE request_id=?',(request_id,)).fetchone()
            values = (name,strength,form,price_cents)
            if old:
                if tuple(old[k] for k in ('name','strength','form','price_cents')) != values:
                    raise RuleError('This catalogue request was already saved with different details.')
                return {k:old[k] for k in ('id','name','strength','form','price_cents','stock')}
            if db.execute('''SELECT 1 FROM medicines WHERE lower(name)=lower(?)
                             AND lower(strength)=lower(?) AND lower(form)=lower(?)''',values[:3]).fetchone():
                raise RuleError('This name, strength and form already exist. Receive stock for the existing item.')
            medicine_id = str(uuid4())
            db.execute('INSERT INTO medicines(id,name,strength,form,price_cents,stock,request_id) VALUES(?,?,?,?,?,0,?)',
                       (medicine_id,*values,request_id))
            return {'id':medicine_id,'name':name,'strength':strength,'form':form,'price_cents':price_cents,'stock':0}

    def daily_report(self, clinic_date):
        with self.connect() as db:
            db.execute('BEGIN')
            visits={key:0 for key in ('waiting','called','completed','cancelled','rescheduled')}
            for row in db.execute('''SELECT CASE WHEN EXISTS(SELECT 1 FROM reschedules r WHERE r.old_booking_id=b.id)
                    THEN 'rescheduled' ELSE b.status END AS state,COUNT(*) AS total
                FROM bookings b JOIN slots s ON s.id=b.slot_id WHERE s.clinic_date=? GROUP BY state''',(clinic_date,)):
                visits[row['state']]=row['total']
            visits['total']=sum(visits.values())
            billing=dict(db.execute('''SELECT COUNT(*) AS invoice_count,
                COALESCE(SUM(i.total_cents),0) AS billed_cents,
                COALESCE(SUM(CASE WHEN i.status='paid' THEN i.total_cents ELSE 0 END),0) AS paid_cents,
                COALESCE(SUM(CASE WHEN i.status='unpaid' THEN i.total_cents ELSE 0 END),0) AS unpaid_cents
                FROM invoices i JOIN bookings b ON b.id=i.booking_id JOIN slots s ON s.id=b.slot_id
                WHERE s.clinic_date=?''',(clinic_date,)).fetchone())
            movements=[]
            for medicine in db.execute('SELECT id,name FROM medicines ORDER BY id').fetchall():
                received=db.execute("SELECT COALESCE(SUM(quantity),0) FROM stock_receipts WHERE medicine_id=? AND date(created_at,'+8 hours')=?",(medicine['id'],clinic_date)).fetchone()[0]
                dispensed=db.execute('''SELECT COALESCE(SUM(i.quantity),0) FROM prescription_items i
                    JOIN prescriptions p ON p.id=i.prescription_id
                    WHERE i.medicine_id=? AND p.status='dispensed' AND date(p.dispensed_at,'+8 hours')=?''',(medicine['id'],clinic_date)).fetchone()[0]
                movements.append({'medicine_id':medicine['id'],'name':medicine['name'],'received':received,'dispensed':dispensed})
            feedback=db.execute("SELECT COUNT(*) AS total,AVG(rating) AS average FROM visit_feedback WHERE date(created_at,'+8 hours')=?",(clinic_date,)).fetchone()
            return {'clinic_date':clinic_date,'timezone':'Asia/Kuala_Lumpur','generated_at':datetime.now(timezone.utc).isoformat(),
                    'visits':visits,'billing':billing,'stock':{'items':movements,'received_units':sum(m['received'] for m in movements),'dispensed_units':sum(m['dispensed'] for m in movements)},
                    'feedback':{'count':feedback['total'],'average_rating':round(feedback['average'],2) if feedback['average'] is not None else None}}

    def stock(self):
        with self.connect() as db:
            medicines=[dict(r) for r in db.execute('SELECT * FROM medicines ORDER BY id')]
            receipts=[dict(r) for r in db.execute('''SELECT r.*,m.name FROM stock_receipts r JOIN medicines m ON m.id=r.medicine_id
                ORDER BY r.created_at DESC LIMIT 100''')]
            return {'medicines':medicines,'receipts':receipts,'low_stock_threshold':5}

    def receive_stock(self, medicine_id, quantity, reason, request_id, staff):
        if staff!='staff-demo':
            raise RuleError('Staff demo identity required.',403)
        if type(quantity) is not int or not 1<=quantity<=1000 or not reason.strip() or len(reason)>300:
            raise RuleError('Enter a whole quantity from 1 to 1000 and a reason up to 300 characters.',422)
        reason=reason.strip()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            existing=db.execute('SELECT * FROM stock_receipts WHERE request_id=?',(request_id,)).fetchone()
            if existing:
                if (existing['medicine_id'],existing['quantity'],existing['reason'])!=(medicine_id,quantity,reason):
                    raise RuleError('This receipt request already saved different details. Check the history.')
                return dict(existing)
            medicine=db.execute('SELECT * FROM medicines WHERE id=?',(medicine_id,)).fetchone()
            if medicine is None:
                raise RuleError('Stock item not found.',404)
            after=medicine['stock']+quantity
            if after>100000:
                raise RuleError('This receipt would exceed the demo stock limit of 100000.')
            receipt_id=str(uuid4())
            db.execute('UPDATE medicines SET stock=? WHERE id=?',(after,medicine_id))
            db.execute('INSERT INTO stock_receipts VALUES(?,?,?,?,?,?,?,?,?)',
                (receipt_id,medicine_id,quantity,reason,medicine['stock'],after,staff,request_id,datetime.now(timezone.utc).isoformat()))
            return dict(db.execute('SELECT * FROM stock_receipts WHERE id=?',(receipt_id,)).fetchone())

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

    def share_record(self, db, share_id, actor):
        row = db.execute('SELECT * FROM assessment_shares WHERE id=?', (share_id,)).fetchone()
        if row is None or (actor in PATIENTS and row['patient_id'] != actor) or (
            actor in DOCTORS and (row['doctor_id'] != actor or row['revoked_at'] is not None)) or actor not in {*PATIENTS, *DOCTORS}:
            raise RuleError('Shared assessment is unavailable for this identity.', 404)
        visit = self.record(db, row['booking_id']) if row['booking_id'] else None
        if actor in DOCTORS and visit and (visit['status'] == 'cancelled' or visit['doctor_id'] != actor):
            raise RuleError('Appointment access is no longer available.', 404)
        review = db.execute('SELECT * FROM assessment_reviews WHERE share_id=?', (share_id,)).fetchone()
        return dict(row, patient_name=PATIENTS[row['patient_id']], doctor_name=DOCTORS[row['doctor_id']],
                    review=dict(review) if review else None, visit=visit)

    def shares(self, actor):
        with self.connect() as db:
            if actor in PATIENTS:
                rows = db.execute('SELECT id FROM assessment_shares WHERE patient_id=? ORDER BY created_at DESC LIMIT 100', (actor,))
            elif actor in DOCTORS:
                rows = db.execute('''SELECT s.id FROM assessment_shares s LEFT JOIN bookings b ON b.id=s.booking_id
                    WHERE s.doctor_id=? AND s.revoked_at IS NULL AND (s.booking_id IS NULL OR b.status!='cancelled')
                    ORDER BY s.created_at DESC LIMIT 100''', (actor,))
            else:
                raise RuleError('Patient or doctor identity required.', 403)
            return [self.share_record(db, row['id'], actor) for row in rows.fetchall()]

    def share_assessment(self, assessment_id, patient, doctor, message, request_id):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('SELECT 1 FROM assessments WHERE id=? AND patient_id=?', (assessment_id,patient)).fetchone():
                raise RuleError('Assessment not found for this patient.', 404)
            existing = db.execute('SELECT * FROM assessment_shares WHERE patient_id=? AND request_id=?', (patient,request_id)).fetchone()
            if existing:
                if existing['booking_id'] is not None or (existing['assessment_id'], existing['doctor_id'], existing['patient_message']) != (assessment_id,doctor,message):
                    raise RuleError('This sharing request was already used. Refresh sharing history.')
                return self.share_record(db, existing['id'], patient)
            active = db.execute('SELECT * FROM assessment_shares WHERE assessment_id=? AND doctor_id=? AND revoked_at IS NULL AND booking_id IS NULL', (assessment_id,doctor)).fetchone()
            if active:
                if active['patient_message'] != message:
                    raise RuleError('Already shared. Revoke before sharing an updated message.')
                return self.share_record(db, active['id'], patient)
            share_id = str(uuid4())
            db.execute('INSERT INTO assessment_shares(id,assessment_id,patient_id,doctor_id,patient_message,request_id,created_at,revoked_at) VALUES(?,?,?,?,?,?,?,NULL)',
                       (share_id,assessment_id,patient,doctor,message,request_id,datetime.now(timezone.utc).isoformat()))
            return self.share_record(db, share_id, patient)

    def link_assessment(self, assessment_id, patient, booking_id, message, request_id):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            visit = self.record(db, booking_id)
            if visit['patient_id'] != patient:
                raise RuleError('Appointment not found for this patient.', 404)
            if not db.execute('SELECT 1 FROM assessments WHERE id=? AND patient_id=?', (assessment_id,patient)).fetchone():
                raise RuleError('Assessment not found for this patient.', 404)
            previous = db.execute('SELECT * FROM assessment_shares WHERE patient_id=? AND request_id=?', (patient,request_id)).fetchone()
            if previous:
                if (previous['assessment_id'],previous['booking_id'],previous['patient_message']) != (assessment_id,booking_id,message):
                    raise RuleError('This request was already used for another link.')
                return self.share_record(db, previous['id'], patient)
            if visit['status'] not in ('waiting','called') or (visit['status']=='waiting' and datetime.fromisoformat(visit['starts_at']) <= datetime.now(timezone.utc)):
                raise RuleError('Choose a future waiting appointment or a called visit.')
            active = db.execute('SELECT * FROM assessment_shares WHERE booking_id=? AND revoked_at IS NULL', (booking_id,)).fetchone()
            if active:
                if (active['assessment_id'],active['patient_message']) != (assessment_id,message):
                    raise RuleError('This appointment already has an assessment. Revoke its link before replacing it.')
                return self.share_record(db, active['id'], patient)
            share_id = str(uuid4())
            db.execute('''INSERT INTO assessment_shares(id,assessment_id,patient_id,doctor_id,patient_message,request_id,created_at,booking_id)
                          VALUES(?,?,?,?,?,?,?,?)''', (share_id,assessment_id,patient,visit['doctor_id'],message,request_id,datetime.now(timezone.utc).isoformat(),booking_id))
            return self.share_record(db, share_id, patient)

    def revoke_share(self, share_id, patient):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            self.share_record(db, share_id, patient)
            db.execute('UPDATE assessment_shares SET revoked_at=? WHERE id=? AND revoked_at IS NULL',
                       (datetime.now(timezone.utc).isoformat(),share_id))
            return self.share_record(db, share_id, patient)

    def shared_assessment(self, share_id, doctor):
        import base64
        with self.connect() as db:
            share = self.share_record(db, share_id, doctor)
            photo = db.execute('SELECT * FROM assessments WHERE id=?', (share['assessment_id'],)).fetchone()
            return dict(share, assessment=self.assessment_metadata(photo) | {
                'photo_uri':'data:image/jpeg;base64,' + base64.b64encode(photo['photo']).decode('ascii')})

    def publish_review(self, share_id, doctor, note, follow_up):
        with self.connect() as db:
            # Serializes publication and revocation: a revoked share cannot accept a new review.
            db.execute('BEGIN IMMEDIATE')
            share = self.share_record(db, share_id, doctor)
            if share['review']:
                if (share['review']['note'],share['review']['follow_up']) != (note,follow_up):
                    raise RuleError('Review already published. Published reviews cannot be replaced.')
                return share
            db.execute('INSERT INTO assessment_reviews VALUES(?,?,?,?,?,?)',
                       (str(uuid4()),share_id,doctor,note,follow_up,datetime.now(timezone.utc).isoformat()))
            self.notify(db,share['patient_id'],'review_published',share_id,share['assessment_id'],'Doctor review is ready',
                        f"{DOCTORS[doctor]} published a review. Open the assessment to read it.")
            return self.share_record(db, share_id, doctor)

    def background_record(self, db, patient):
        row = db.execute('SELECT * FROM patient_backgrounds WHERE patient_id=?', (patient,)).fetchone()
        return dict(row) if row else {'patient_id':patient,'allergies':'','medicines':'','conditions':'','version':0,'updated_at':None}

    def background(self, patient):
        if patient not in PATIENTS:
            raise RuleError('Patient identity required.',403)
        with self.connect() as db:
            return self.background_record(db,patient)

    def save_background(self, patient, allergies, medicines, conditions, version):
        if patient not in PATIENTS:
            raise RuleError('Patient identity required.',403)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            current = self.background_record(db,patient)
            values = (allergies, medicines, conditions)
            if current['version'] != version:
                if values == (current['allergies'],current['medicines'],current['conditions']):
                    return current
                raise RuleError('Background changed elsewhere. Reload the saved background before editing again.')
            if current['version'] and values == (current['allergies'],current['medicines'],current['conditions']):
                return current
            db.execute('''INSERT INTO patient_backgrounds VALUES(?,?,?,?,?,?)
                          ON CONFLICT(patient_id) DO UPDATE SET allergies=excluded.allergies,
                          medicines=excluded.medicines,conditions=excluded.conditions,
                          version=excluded.version,updated_at=excluded.updated_at''',
                       (patient,*values,version+1,datetime.now(timezone.utc).isoformat()))
            return self.background_record(db,patient)

    def consultation_record(self, db, booking_id, actor, include_photo=False):
        if actor not in {*PATIENTS,*DOCTORS}:
            raise RuleError('Patient or doctor identity required.', 403)
        visit = self.record(db, booking_id)
        if (actor in PATIENTS and visit['patient_id'] != actor) or (actor in DOCTORS and visit['doctor_id'] != actor):
            raise RuleError('Consultation unavailable for this identity.', 404)
        note = db.execute('SELECT * FROM consultation_notes WHERE booking_id=?', (booking_id,)).fetchone()
        if (actor in PATIENTS and not note) or (actor in DOCTORS and visit['status'] not in ('called','completed')):
            raise RuleError('Consultation not available yet.', 404)
        linked = None
        if actor in DOCTORS:
            share = db.execute('SELECT id FROM assessment_shares WHERE booking_id=? AND revoked_at IS NULL', (booking_id,)).fetchone()
            if share:
                linked = self.share_record(db, share['id'], actor)
                if include_photo:
                    import base64
                    photo = db.execute('SELECT * FROM assessments WHERE id=?', (linked['assessment_id'],)).fetchone()
                    linked['assessment'] = self.assessment_metadata(photo) | {'photo_uri':'data:image/jpeg;base64,' + base64.b64encode(photo['photo']).decode('ascii')}
        result = {'visit':visit, 'note':dict(note) if note else None, 'linked_share':linked}
        if include_photo:
            result['background'] = self.background_record(db,visit['patient_id'])
        return result

    def consultations(self, actor):
        if actor not in {*PATIENTS,*DOCTORS}:
            raise RuleError('Patient or doctor identity required.', 403)
        with self.connect() as db:
            if actor in PATIENTS:
                rows = db.execute('''SELECT b.id FROM bookings b JOIN consultation_notes n ON n.booking_id=b.id
                                    WHERE b.patient_id=? ORDER BY n.created_at DESC''', (actor,)).fetchall()
            else:
                rows = db.execute('''SELECT b.id FROM bookings b JOIN slots s ON s.id=b.slot_id
                                    WHERE s.doctor_id=? AND b.status IN ('called','completed') ORDER BY b.created_at DESC''', (actor,)).fetchall()
            return [self.consultation_record(db,row['id'],actor) for row in rows]

    def consultation(self, booking_id, actor):
        with self.connect() as db:
            db.execute('BEGIN')
            return self.consultation_record(db,booking_id,actor,include_photo=True)

    def publish_consultation(self, booking_id, doctor, findings, follow_up):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            record = self.consultation_record(db,booking_id,doctor)
            existing = record['note']
            if existing:
                if (existing['findings'],existing['follow_up']) != (findings,follow_up):
                    raise RuleError('Consultation note already published. It cannot be replaced.')
                return record
            if record['visit']['status'] != 'called':
                raise RuleError('Publish the consultation note while the visit is called.')
            db.execute('INSERT INTO consultation_notes VALUES(?,?,?,?,?,?)',
                       (str(uuid4()),booking_id,doctor,findings,follow_up,datetime.now(timezone.utc).isoformat()))
            self.event(db,booking_id,doctor,'consultation-published')
            return self.consultation_record(db,booking_id,doctor)

    def prescription(self, db, booking_id):
        row = db.execute('SELECT * FROM prescriptions WHERE booking_id=?', (booking_id,)).fetchone()
        if not row:
            return None
        items = db.execute('''SELECT i.medicine_id,i.quantity,i.directions,i.name,i.price_cents,i.strength,i.form
            FROM prescription_items i
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
            for item in normalised:
                medicine = db.execute('SELECT * FROM medicines WHERE id=?',(item['medicine_id'],)).fetchone()
                db.execute('INSERT INTO prescription_items(prescription_id,medicine_id,quantity,directions,name,price_cents,strength,form) VALUES(?,?,?,?,?,?,?,?)',
                           (prescription_id,item['medicine_id'],item['quantity'],item['directions'],medicine['name'],medicine['price_cents'],medicine['strength'],medicine['form']))
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
                lines.extend((' · '.join(v for v in (i['name'],i['strength'],i['form']) if v), i['quantity'], i['price_cents']) for i in prescription['items'])
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
