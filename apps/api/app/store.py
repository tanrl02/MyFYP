"""Local synthetic demo storage. Keep SQL and transactions out of screens/routes."""
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import re
import sqlite3
import json
from uuid import uuid4
from .booking_migrations import allow_missed_bookings
from .scheduling import MALAYSIA, pattern_values, week_slots, preview_hash

PATIENTS = {'patient-ava': 'Ava Demo', 'patient-noah': 'Noah Demo'}
DOCTORS = {'doctor-lim': 'Dr. Lim (demo)', 'doctor-anita': 'Dr. Anita (demo)'}
USER_ROLES = {**dict.fromkeys(PATIENTS,'patient'), **dict.fromkeys(DOCTORS,'doctor'), 'staff-demo':'staff', 'admin-demo':'admin'}
DOCTOR_CONCERNS = {'general', 'acne', 'eczema', 'psoriasis'}
# Reminder rows are retained, but only currently upcoming waiting visits are visible.
NOTIFICATION_VISIBLE = """(n.kind!='appointment_reminder' OR EXISTS (
    SELECT 1 FROM bookings b JOIN slots s ON s.id=b.slot_id
    WHERE b.id=n.target_id AND b.patient_id=n.patient_id AND b.status='waiting'
      AND julianday(s.starts_at)>julianday(?) AND julianday(s.starts_at)<=julianday(?)))"""

class RuleError(Exception):
    def __init__(self, message, status=409):
        self.message, self.status = message, status

class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS user_profiles (
                  id TEXT PRIMARY KEY, role TEXT NOT NULL CHECK(role IN ('patient','doctor','staff','admin')),
                  name TEXT NOT NULL, phone TEXT NOT NULL, email TEXT NOT NULL,
                  version INTEGER NOT NULL, updated_at TEXT, updated_by TEXT);
                CREATE TABLE IF NOT EXISTS patient_creations (
                  request_id TEXT PRIMARY KEY, user_id TEXT NOT NULL UNIQUE REFERENCES user_profiles(id),
                  payload_json TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS doctor_creations (
                  request_id TEXT PRIMARY KEY, user_id TEXT NOT NULL UNIQUE REFERENCES user_profiles(id),
                  payload_json TEXT NOT NULL, queue_prefix TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS doctor_profiles (
                  doctor_id TEXT PRIMARY KEY, specialty TEXT NOT NULL, expertise TEXT NOT NULL,
                  version INTEGER NOT NULL, updated_at TEXT);
                CREATE TABLE IF NOT EXISTS doctor_schedule_patterns (
                  doctor_id TEXT PRIMARY KEY, pattern_json TEXT NOT NULL, version INTEGER NOT NULL,
                  updated_at TEXT NOT NULL, actor_id TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS doctor_unavailability (
                  id TEXT PRIMARY KEY, doctor_id TEXT NOT NULL, clinic_date TEXT NOT NULL,
                  reason TEXT NOT NULL, created_at TEXT NOT NULL, request_id TEXT NOT NULL UNIQUE,
                  cancelled_at TEXT);
                CREATE TABLE IF NOT EXISTS schedule_generations (
                  request_id TEXT PRIMARY KEY, doctor_id TEXT NOT NULL, week_start TEXT NOT NULL,
                  pattern_version INTEGER NOT NULL, preview_token TEXT NOT NULL, result_json TEXT NOT NULL);
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
                  queue_number INTEGER NOT NULL, status TEXT NOT NULL CHECK(status IN ('waiting','called','completed','cancelled','missed')),
                  created_at TEXT NOT NULL, request_id TEXT NOT NULL,
                  UNIQUE(patient_id, request_id));
                CREATE TABLE IF NOT EXISTS follow_up_recommendations (
                  source_booking_id TEXT PRIMARY KEY REFERENCES bookings(id), doctor_id TEXT NOT NULL,
                  recommended_date TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS follow_up_bookings (
                  booking_id TEXT PRIMARY KEY REFERENCES bookings(id),
                  source_booking_id TEXT NOT NULL REFERENCES follow_up_recommendations(source_booking_id));
                CREATE INDEX IF NOT EXISTS booking_slot ON bookings(slot_id, status);
                CREATE TABLE IF NOT EXISTS events (
                  id TEXT PRIMARY KEY, booking_id TEXT NOT NULL REFERENCES bookings(id),
                  actor_id TEXT NOT NULL, action TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS missed_restorations (
                  missed_event_id TEXT PRIMARY KEY REFERENCES events(id),
                  restored_event_id TEXT NOT NULL UNIQUE REFERENCES events(id));
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
                CREATE TABLE IF NOT EXISTS prescription_direction_revisions (
                  id TEXT PRIMARY KEY, prescription_id TEXT NOT NULL REFERENCES prescriptions(id),
                  version INTEGER NOT NULL, doctor_id TEXT NOT NULL, reason TEXT NOT NULL,
                  previous_directions_json TEXT NOT NULL, directions_json TEXT NOT NULL,
                  created_at TEXT NOT NULL, UNIQUE(prescription_id,version));
                CREATE TABLE IF NOT EXISTS prescription_cancellations (
                  prescription_id TEXT PRIMARY KEY REFERENCES prescriptions(id),
                  doctor_id TEXT NOT NULL, reason TEXT NOT NULL, version INTEGER NOT NULL,
                  created_at TEXT NOT NULL);
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
                CREATE TABLE IF NOT EXISTS assessment_review_drafts (
                  share_id TEXT PRIMARY KEY REFERENCES assessment_shares(id), doctor_id TEXT NOT NULL,
                  note TEXT NOT NULL, follow_up TEXT NOT NULL, version INTEGER NOT NULL, updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS consultation_notes (
                  id TEXT PRIMARY KEY, booking_id TEXT NOT NULL UNIQUE REFERENCES bookings(id),
                  doctor_id TEXT NOT NULL, findings TEXT NOT NULL, follow_up TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS consultation_drafts (
                  booking_id TEXT PRIMARY KEY REFERENCES bookings(id), doctor_id TEXT NOT NULL,
                  findings TEXT NOT NULL, follow_up TEXT NOT NULL, version INTEGER NOT NULL,
                  updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS consultation_handoffs (
                  booking_id TEXT PRIMARY KEY REFERENCES bookings(id), doctor_id TEXT NOT NULL,
                  note_id TEXT NOT NULL REFERENCES consultation_notes(id),
                  prescription_id TEXT REFERENCES prescriptions(id), finished_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS visit_feedback (
                  id TEXT PRIMARY KEY, booking_id TEXT NOT NULL UNIQUE REFERENCES bookings(id),
                  patient_id TEXT NOT NULL, rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
                  comment TEXT NOT NULL, created_at TEXT NOT NULL);
            ''')
            db.executescript('''CREATE TABLE IF NOT EXISTS receipt_balances (
                receipt_id TEXT PRIMARY KEY REFERENCES stock_receipts(id),remaining_units INTEGER NOT NULL CHECK(remaining_units>=0));
                CREATE TABLE IF NOT EXISTS dispensing_allocations (
                id TEXT PRIMARY KEY,prescription_id TEXT NOT NULL REFERENCES prescriptions(id),medicine_id TEXT NOT NULL REFERENCES medicines(id),
                receipt_id TEXT REFERENCES stock_receipts(id),quantity INTEGER NOT NULL CHECK(quantity>0),batch_number TEXT,expiry_date TEXT,
                actor_id TEXT NOT NULL,created_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS allocation_prescription ON dispensing_allocations(prescription_id);''')
            for column,definition in [('held','INTEGER NOT NULL DEFAULT 0 CHECK(held IN (0,1))'),('hold_reason','TEXT'),('hold_version','INTEGER NOT NULL DEFAULT 0'),('hold_updated_at','TEXT')]:
                if column not in {row['name'] for row in db.execute('PRAGMA table_info(receipt_balances)')}:
                    db.execute(f'ALTER TABLE receipt_balances ADD COLUMN {column} {definition}')
            db.execute('''CREATE TABLE IF NOT EXISTS batch_hold_changes (
                request_id TEXT PRIMARY KEY,medicine_id TEXT NOT NULL REFERENCES medicines(id),receipt_id TEXT NOT NULL REFERENCES stock_receipts(id),
                from_version INTEGER NOT NULL,held INTEGER NOT NULL,reason TEXT NOT NULL,actor_id TEXT NOT NULL,created_at TEXT NOT NULL,result_json TEXT NOT NULL)''')
            for column in ('batch_number','expiry_date'):
                if column not in {row['name'] for row in db.execute('PRAGMA table_info(stock_receipts)')}:
                    db.execute(f'ALTER TABLE stock_receipts ADD COLUMN {column} TEXT')
            allow_missed_bookings(db)
            if 'cancelled_at' not in {row['name'] for row in db.execute('PRAGMA table_info(doctor_unavailability)')}:
                # Replace the old permanent doctor/date uniqueness with active-only uniqueness.
                # No tables reference absence IDs; preserve every ID, request key and source value.
                db.execute('BEGIN IMMEDIATE')
                db.execute('ALTER TABLE doctor_unavailability RENAME TO doctor_unavailability_legacy')
                db.execute('''CREATE TABLE doctor_unavailability (
                    id TEXT PRIMARY KEY, doctor_id TEXT NOT NULL, clinic_date TEXT NOT NULL,
                    reason TEXT NOT NULL, created_at TEXT NOT NULL, request_id TEXT NOT NULL UNIQUE,
                    cancelled_at TEXT)''')
                db.execute('''INSERT INTO doctor_unavailability(id,doctor_id,clinic_date,reason,created_at,request_id)
                    SELECT id,doctor_id,clinic_date,reason,created_at,request_id FROM doctor_unavailability_legacy''')
                db.execute('DROP TABLE doctor_unavailability_legacy')
            if not db.in_transaction:
                db.execute('BEGIN IMMEDIATE')
            for column in ('start_time','end_time'):
                if column not in {row['name'] for row in db.execute('PRAGMA table_info(doctor_unavailability)')}:
                    db.execute(f'ALTER TABLE doctor_unavailability ADD COLUMN {column} TEXT')
            db.execute('DROP INDEX IF EXISTS active_doctor_unavailability')
            db.execute('CREATE INDEX IF NOT EXISTS doctor_absence_date ON doctor_unavailability(doctor_id,clinic_date) WHERE cancelled_at IS NULL')
            if 'prediction_json' not in {row['name'] for row in db.execute('PRAGMA table_info(assessments)')}:
                db.execute('ALTER TABLE assessments ADD COLUMN prediction_json TEXT')
            if 'symptoms_json' not in {row['name'] for row in db.execute('PRAGMA table_info(assessments)')}:
                db.execute('ALTER TABLE assessments ADD COLUMN symptoms_json TEXT')
            for column,definition in [('version','INTEGER NOT NULL DEFAULT 0'),('edited_at','TEXT')]:
                if column not in {row['name'] for row in db.execute('PRAGMA table_info(visit_feedback)')}:
                    db.execute(f'ALTER TABLE visit_feedback ADD COLUMN {column} {definition}')
            for table in ('assessment_reviews','assessment_review_drafts'):
                if 'doctor_assessment' not in {row['name'] for row in db.execute(f'PRAGMA table_info({table})')}:
                    db.execute(f"ALTER TABLE {table} ADD COLUMN doctor_assessment TEXT NOT NULL DEFAULT ''")
            for column, definition in [('closed', 'INTEGER NOT NULL DEFAULT 0'),('request_id','TEXT'),
                                       ('duration_minutes','INTEGER NOT NULL DEFAULT 30 CHECK(duration_minutes BETWEEN 15 AND 120 AND duration_minutes%15=0)')]:
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
            for column, definition in [('target_stock','INTEGER CHECK(target_stock BETWEEN 0 AND 99999)'),('low_stock_threshold','INTEGER NOT NULL DEFAULT 5 CHECK(low_stock_threshold BETWEEN 0 AND 99999)'),('strength',"TEXT NOT NULL DEFAULT ''"),('form',"TEXT NOT NULL DEFAULT ''"),('request_id','TEXT'),('version','INTEGER NOT NULL DEFAULT 0'),('updated_at','TEXT'),('creation_json','TEXT'),('active','INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1))')]:
                if column not in {r['name'] for r in db.execute('PRAGMA table_info(medicines)')}:
                    db.execute(f'ALTER TABLE medicines ADD COLUMN {column} {definition}')
            db.execute('CREATE UNIQUE INDEX IF NOT EXISTS medicine_request ON medicines(request_id) WHERE request_id IS NOT NULL')
            db.executemany('INSERT OR IGNORE INTO medicines(id,name,price_cents,stock) VALUES(?,?,?,?)', [
                ('demo-a', 'Demo item A (not medication)', 500, 20),
                ('demo-b', 'Demo item B (not medication)', 800, 20)])
            db.execute('''UPDATE medicines SET creation_json=json_object('name',name,'strength',strength,'form',form,'price_cents',price_cents)
                          WHERE creation_json IS NULL''')
            db.execute('''CREATE TABLE IF NOT EXISTS medicine_edits (
                request_id TEXT PRIMARY KEY, medicine_id TEXT NOT NULL REFERENCES medicines(id),
                from_version INTEGER NOT NULL, name TEXT NOT NULL, price_cents INTEGER NOT NULL,
                old_name TEXT NOT NULL, old_price_cents INTEGER NOT NULL,
                actor_id TEXT NOT NULL, created_at TEXT NOT NULL, result_json TEXT NOT NULL)''')
            db.execute('''CREATE TABLE IF NOT EXISTS medicine_target_changes (
                request_id TEXT PRIMARY KEY, medicine_id TEXT NOT NULL REFERENCES medicines(id),
                from_version INTEGER NOT NULL, target INTEGER, old_target INTEGER,
                actor_id TEXT NOT NULL, created_at TEXT NOT NULL, result_json TEXT NOT NULL)''')
            db.execute('''CREATE TABLE IF NOT EXISTS medicine_threshold_changes (
                request_id TEXT PRIMARY KEY, medicine_id TEXT NOT NULL REFERENCES medicines(id),
                from_version INTEGER NOT NULL, threshold INTEGER NOT NULL, old_threshold INTEGER NOT NULL,
                actor_id TEXT NOT NULL, created_at TEXT NOT NULL, result_json TEXT NOT NULL)''')
            db.execute('''CREATE TABLE IF NOT EXISTS medicine_status_changes (
                request_id TEXT PRIMARY KEY, medicine_id TEXT NOT NULL REFERENCES medicines(id),
                from_version INTEGER NOT NULL, active INTEGER NOT NULL, old_active INTEGER NOT NULL,
                actor_id TEXT NOT NULL, created_at TEXT NOT NULL, result_json TEXT NOT NULL)''')
            db.execute('''CREATE TABLE IF NOT EXISTS stock_losses (
                id TEXT PRIMARY KEY, medicine_id TEXT NOT NULL REFERENCES medicines(id),
                quantity INTEGER NOT NULL CHECK(quantity>0), kind TEXT NOT NULL CHECK(kind IN ('damaged','lost')),
                reason TEXT NOT NULL, stock_before INTEGER NOT NULL, stock_after INTEGER NOT NULL CHECK(stock_after>=0),
                actor_id TEXT NOT NULL, request_id TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL, item_label TEXT NOT NULL)''')
            for column, definition in [('receipt_id','TEXT REFERENCES stock_receipts(id)'),('batch_number','TEXT'),('expiry_date','TEXT')]:
                if column not in {row['name'] for row in db.execute('PRAGMA table_info(stock_losses)')}:
                    db.execute(f'ALTER TABLE stock_losses ADD COLUMN {column} {definition}')
            for column, definition in [('name','TEXT'),('price_cents','INTEGER'),('strength','TEXT'),('form','TEXT')]:
                if column not in {r['name'] for r in db.execute('PRAGMA table_info(prescription_items)')}:
                    db.execute(f'ALTER TABLE prescription_items ADD COLUMN {column} {definition}')
            db.execute('''UPDATE prescription_items SET
                name=(SELECT name FROM medicines WHERE id=medicine_id),
                price_cents=(SELECT price_cents FROM medicines WHERE id=medicine_id),
                strength=(SELECT strength FROM medicines WHERE id=medicine_id),
                form=(SELECT form FROM medicines WHERE id=medicine_id) WHERE name IS NULL''')
            names={**PATIENTS,**DOCTORS,'staff-demo':'Staff Demo','admin-demo':'Admin Demo'}
            for user_id,role in USER_ROLES.items():
                db.execute('INSERT OR IGNORE INTO user_profiles VALUES(?,?,?,?,?,0,NULL,NULL)',(user_id,role,names[user_id],'',''))
            for doctor in DOCTORS:
                db.execute('INSERT OR IGNORE INTO doctor_profiles VALUES(?,?,?,?,NULL)',
                           (doctor, 'Not specified', '[]', 0))
        self.seed()

    def user_name(self, db, user_id):
        # Reuse the caller's connection: a nested reader can deadlock with a
        # pending writer while the caller still owns a SQLite read cursor.
        row=db.execute('SELECT name FROM user_profiles WHERE id=?',(user_id,)).fetchone()
        return row['name'] if row else user_id

    def user_profile(self, actor):
        with self.connect() as db:
            row=db.execute('SELECT * FROM user_profiles WHERE id=?',(actor,)).fetchone()
            if not row:raise RuleError('Recognised demo identity required.',403)
            return dict(row)

    def user_role(self, actor, db=None):
        if db is None:
            with self.connect() as connection:return self.user_role(actor,connection)
        row=db.execute('SELECT role FROM user_profiles WHERE id=?',(actor,)).fetchone()
        return row['role'] if row else None

    def is_patient(self, actor, db=None):
        return self.user_role(actor,db)=='patient'

    def is_doctor(self, actor, db=None):
        return self.user_role(actor,db)=='doctor'

    def doctor_names(self, db):
        return {row['id']:row['name'] for row in db.execute("SELECT id,name FROM user_profiles WHERE role='doctor' ORDER BY rowid")}

    def demo_doctors(self):
        with self.connect() as db:
            return [{'id':id,'name':name} for id,name in self.doctor_names(db).items()]

    def queue_prefix(self, db, doctor):
        if doctor=='doctor-lim':return 'L'
        if doctor=='doctor-anita':return 'A'
        row=db.execute('SELECT queue_prefix FROM doctor_creations WHERE user_id=?',(doctor,)).fetchone()
        return row['queue_prefix'] if row else 'D'

    def queue_token(self, db, visit):
        prefix=self.queue_prefix(db,visit['doctor_id'])
        return f"{prefix}{'-' if prefix not in ('L','A') else ''}{visit['queue_number']:03d}"

    def demo_patients(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute("SELECT id,name FROM user_profiles WHERE role='patient' ORDER BY rowid")]

    def user_profiles(self, actor):
        if actor!='admin-demo':raise RuleError('Admin demo identity required.',403)
        with self.connect() as db:
            return [dict(row) for row in db.execute('SELECT * FROM user_profiles ORDER BY role,name,id')]

    @staticmethod
    def normalise_user_information(name, phone, email):
        name,phone,email=name.strip(),phone.strip(),email.strip()
        if not 1<=len(name)<=100 or any(ord(c)<32 or ord(c)==127 for c in name):
            raise RuleError('Enter a name within 100 characters on one line.',422)
        if phone and (len(phone)>30 or not re.fullmatch(r'\+?[0-9 ()-]+',phone) or not 7<=len(re.sub(r'\D','',phone))<=15):
            raise RuleError('Enter a phone number with 7-15 digits, or leave it blank.',422)
        if email and (len(email)>254 or not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+',email)):
            raise RuleError('Enter a valid email address, or leave it blank.',422)
        return name,phone,email

    def create_patient(self, actor, name, phone, email, request_id):
        if actor!='admin-demo':raise RuleError('Admin demo identity required.',403)
        name,phone,email=self.normalise_user_information(name,phone,email)
        if not 8<=len(request_id)<=100 or not request_id.strip():raise RuleError('A valid creation request is required.',422)
        payload=json.dumps({'name':name,'phone':phone,'email':email},sort_keys=True)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            existing=db.execute('SELECT * FROM patient_creations WHERE request_id=?',(request_id,)).fetchone()
            if existing:
                if existing['payload_json']!=payload:raise RuleError('This request was used for different patient details. Start a new patient form.')
                return dict(db.execute('SELECT * FROM user_profiles WHERE id=?',(existing['user_id'],)).fetchone())
            user_id='patient-'+str(uuid4());now=datetime.now(timezone.utc).isoformat()
            db.execute("INSERT INTO user_profiles VALUES(?,'patient',?,?,?,0,?,?)",(user_id,name,phone,email,now,actor))
            db.execute('INSERT INTO patient_creations VALUES(?,?,?,?)',(request_id,user_id,payload,now))
            return dict(db.execute('SELECT * FROM user_profiles WHERE id=?',(user_id,)).fetchone())

    def create_doctor(self, actor, name, phone, email, request_id):
        if actor!='admin-demo':raise RuleError('Admin demo identity required.',403)
        name,phone,email=self.normalise_user_information(name,phone,email)
        if not 8<=len(request_id)<=100 or not request_id.strip():raise RuleError('A valid creation request is required.',422)
        payload=json.dumps({'name':name,'phone':phone,'email':email},sort_keys=True)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            existing=db.execute('SELECT * FROM doctor_creations WHERE request_id=?',(request_id,)).fetchone()
            if existing:
                if existing['payload_json']!=payload:raise RuleError('This request was used for different doctor details. Start a new doctor form.')
                return dict(db.execute('SELECT * FROM user_profiles WHERE id=?',(existing['user_id'],)).fetchone())
            user_id='doctor-'+str(uuid4());now=datetime.now(timezone.utc).isoformat()
            prefix=f"D{db.execute('SELECT COUNT(*) FROM doctor_creations').fetchone()[0]+1:03d}"
            db.execute("INSERT INTO user_profiles VALUES(?,'doctor',?,?,?,0,?,?)",(user_id,name,phone,email,now,actor))
            db.execute('INSERT INTO doctor_profiles VALUES(?,?,?,?,NULL)',(user_id,'Not specified','[]',0))
            db.execute('INSERT INTO doctor_creations VALUES(?,?,?,?,?)',(request_id,user_id,payload,prefix,now))
            return dict(db.execute('SELECT * FROM user_profiles WHERE id=?',(user_id,)).fetchone())

    def save_user_profile(self, user_id, actor, name, phone, email, version):
        if actor!='admin-demo':raise RuleError('Admin demo identity required.',403)
        name,phone,email=self.normalise_user_information(name,phone,email)
        if type(version) is not int or version<0:raise RuleError('A valid reviewed version is required.',422)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT * FROM user_profiles WHERE id=?',(user_id,)).fetchone()
            if not row:raise RuleError('User not found.',404)
            same=(row['name'],row['phone'],row['email'])==(name,phone,email)
            if same and version in (row['version'],row['version']-1):return dict(row)
            if version!=row['version']:raise RuleError('This user information changed. Reload and review the latest version.')
            db.execute('UPDATE user_profiles SET name=?,phone=?,email=?,version=version+1,updated_at=?,updated_by=? WHERE id=?',
                (name,phone,email,datetime.now(timezone.utc).isoformat(),actor,user_id))
            return dict(db.execute('SELECT * FROM user_profiles WHERE id=?',(user_id,)).fetchone())

    def doctor_profile(self, db, row):
        return dict(row, doctor_name=self.user_name(db,row['doctor_id']), expertise=json.loads(row['expertise']))

    def doctor_profiles(self):
        with self.connect() as db:
            return [self.doctor_profile(db,row) for row in db.execute('SELECT * FROM doctor_profiles ORDER BY doctor_id')]

    def doctor_matches(self, patient, concern=None, assessment_id=None):
        if (concern is None) == (assessment_id is None):
            raise RuleError('Choose a concern or a saved assessment, not both.',422)
        if concern is not None and concern not in DOCTOR_CONCERNS:
            raise RuleError('Choose a supported concern.',422)
        source='manual'
        message='Suggestions use staff-entered expertise, not verified qualifications or a diagnosis.'
        with self.connect() as db:
            db.execute('BEGIN')
            if assessment_id is not None:
                row=db.execute('SELECT id,patient_id,width,height,created_at,prediction_json,symptoms_json FROM assessments WHERE id=? AND patient_id=?',
                               (assessment_id,patient)).fetchone()
                if row is None:
                    raise RuleError('Assessment not found for this patient.',404)
                metadata=self.assessment_metadata(row)
                # Explicit categories only. Unknown/uncertain results use general support.
                if metadata['origin']=='experimental_ai':
                    condition=metadata['prediction']['top_predictions'][0]['condition']
                    concern=condition if condition in DOCTOR_CONCERNS else 'general'
                else:
                    concern={'Acne (example only)':'acne','Eczema (example only)':'eczema',
                             'Psoriasis (example only)':'psoriasis'}.get(metadata['example_category'],'general')
                source=metadata['origin']
                message=('EXPERIMENTAL AI: suggestions use an unverified model suggestion and staff-entered expertise. You can choose another concern. This is not a diagnosis.' if source=='experimental_ai' else 'SIMULATION: suggestions use a fixed example category, not image analysis or a diagnosis.')+' No assessment is shared by viewing suggestions or booking.'
            profiles=[self.doctor_profile(db,row) for row in db.execute('SELECT * FROM doctor_profiles ORDER BY doctor_id')]
        for profile in profiles:
            if concern in profile['expertise']:
                level='concern'
                reason='Profile lists general skin concerns.' if concern=='general' else f"Profile lists {concern} as an area of expertise."
            elif 'general' in profile['expertise']:
                level='general'
                reason='General skin concerns are listed; the selected concern is not specifically listed.'
            else:
                level='none'
                reason='No matching expertise is listed. You can still choose this doctor.'
            profile.update(match_level=level,match_reason=reason)
        profiles.sort(key=lambda p:({'concern':0,'general':1,'none':2}[p['match_level']],p['doctor_name']))
        return {'concern':concern,'source':source,'assessment_id':assessment_id,'message':message,'doctors':profiles}

    def save_doctor_profile(self, doctor, specialty, expertise, version):
        specialty = specialty.strip()
        if not specialty or len(specialty)>80 or not set(expertise)<=DOCTOR_CONCERNS or len(expertise)!=len(set(expertise)):
            raise RuleError('Enter a specialty and choose distinct supported areas of expertise.', 422)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM doctor_profiles WHERE doctor_id=?', (doctor,)).fetchone()
            if row is None:
                raise RuleError('Doctor not found.', 404)
            current = self.doctor_profile(db,row)
            expertise = sorted(expertise)
            # A retry after a lost response is harmless, including an old version.
            if (current['specialty'], sorted(current['expertise'])) == (specialty, expertise):
                return current
            if row['version'] != version:
                raise RuleError('This profile changed. Reload profiles before editing again.')
            db.execute('UPDATE doctor_profiles SET specialty=?,expertise=?,version=version+1,updated_at=? WHERE doctor_id=?',
                       (specialty,json.dumps(expertise),datetime.now(timezone.utc).isoformat(),doctor))
            return self.doctor_profile(db,db.execute('SELECT * FROM doctor_profiles WHERE doctor_id=?',(doctor,)).fetchone())

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
            db.execute('BEGIN IMMEDIATE')
            for day in (1, 2):
                for doctor in DOCTORS:
                    if db.execute('SELECT 1 FROM doctor_schedule_patterns WHERE doctor_id=?',(doctor,)).fetchone():
                        continue
                    for hour in (9, 10, 11):
                        start = (local + timedelta(days=day)).replace(hour=hour, minute=0, second=0, microsecond=0)
                        if self.unavailable_overlap(db,doctor,start,30):
                            continue
                        key = f'{doctor}-{start:%Y%m%d}-{hour}'
                        if db.execute('SELECT 1 FROM slots WHERE id=? OR (doctor_id=? AND julianday(starts_at)=julianday(?))',
                                      (key,doctor,start.isoformat())).fetchone() or self.slot_overlap(db,doctor,start,30):
                            continue
                        db.execute('INSERT OR IGNORE INTO slots(id,doctor_id,starts_at,clinic_date,capacity) VALUES(?,?,?,?,?)',
                                   (key, doctor, start.isoformat(), start.date().isoformat(), 2))

    def slots(self):
        with self.connect() as db:
            rows = db.execute('''SELECT s.id,s.doctor_id,s.starts_at,s.clinic_date,s.capacity,s.duration_minutes, s.capacity - COUNT(b.id) AS available
                FROM slots s LEFT JOIN bookings b ON b.slot_id=s.id AND b.status!='cancelled'
                WHERE s.starts_at > ? AND s.closed=0 AND NOT EXISTS (
                    SELECT 1 FROM doctor_unavailability u WHERE u.doctor_id=s.doctor_id AND u.cancelled_at IS NULL
                    AND julianday(u.clinic_date||'T'||COALESCE(u.start_time,'00:00')||':00+08:00')<julianday(s.starts_at,'+'||s.duration_minutes||' minutes')
                    AND julianday(u.clinic_date||'T'||COALESCE(u.end_time,'24:00')||':00+08:00')>julianday(s.starts_at))
                GROUP BY s.id ORDER BY s.starts_at, s.doctor_id''',
                (datetime.now(timezone(timedelta(hours=8))).isoformat(),)).fetchall()
            return [self.slot_metadata(db,r) for r in rows]

    def slot_metadata(self, db, row):
        end=datetime.fromisoformat(row['starts_at'])+timedelta(minutes=row['duration_minutes'])
        return dict(row,doctor_name=self.user_name(db,row['doctor_id']),ends_at=end.isoformat())

    @staticmethod
    def slot_overlap(db, doctor, start, duration):
        end=start+timedelta(minutes=duration)
        return db.execute('''SELECT id FROM slots WHERE doctor_id=? AND closed=0
            AND julianday(starts_at)<julianday(?)
            AND julianday(starts_at,'+'||duration_minutes||' minutes')>julianday(?) LIMIT 1''',
            (doctor,end.isoformat(),start.isoformat())).fetchone()

    def managed_slot(self, db, slot_id):
        row = db.execute('''SELECT s.*,COUNT(b.id) AS booking_count,
                            s.capacity-SUM(CASE WHEN b.id IS NOT NULL AND b.status!='cancelled' THEN 1 ELSE 0 END) AS available
                            FROM slots s LEFT JOIN bookings b ON b.slot_id=s.id WHERE s.id=? GROUP BY s.id''',(slot_id,)).fetchone()
        if not row:
            raise RuleError('Slot not found.',404)
        values={key:row[key] for key in ('id','doctor_id','starts_at','clinic_date','capacity','closed','booking_count','available','duration_minutes')}
        values['unavailable']=bool(self.unavailable_overlap(db,row['doctor_id'],datetime.fromisoformat(row['starts_at']),row['duration_minutes']))
        return self.slot_metadata(db,values)

    def managed_slots(self):
        with self.connect() as db:
            db.execute('BEGIN')
            rows=db.execute('SELECT id FROM slots WHERE starts_at>? ORDER BY starts_at,doctor_id',(datetime.now(timezone(timedelta(hours=8))).isoformat(),)).fetchall()
            return [self.managed_slot(db,row['id']) for row in rows]

    def add_slot(self, doctor, clinic_date, time, capacity, request_id, duration_minutes=30):
        if type(duration_minutes) is not int or not 15<=duration_minutes<=120 or duration_minutes%15:
            raise RuleError('Slot duration must be 15–120 minutes in 15-minute steps.',422)
        start=datetime.fromisoformat(f'{clinic_date}T{time}:00+08:00')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT id FROM slots WHERE request_id=?',(request_id,)).fetchone()
            if old:
                slot=self.managed_slot(db,old['id'])
                if (slot['doctor_id'],slot['starts_at'],slot['capacity'],slot['duration_minutes'])!=(doctor,start.isoformat(),capacity,duration_minutes):
                    raise RuleError('This request already saved different slot details.')
                return slot
            if start<=datetime.now(timezone.utc):
                raise RuleError('Choose a future date and time.')
            if self.unavailable_overlap(db,doctor,start,duration_minutes):
                raise RuleError('This doctor is unavailable during that slot. Choose another date.')
            if db.execute('SELECT 1 FROM slots WHERE doctor_id=? AND julianday(starts_at)=julianday(?)',(doctor,start.isoformat())).fetchone():
                raise RuleError('This doctor already has a slot at that time, including closed slots.')
            if self.slot_overlap(db,doctor,start,duration_minutes):
                raise RuleError('This doctor already has an overlapping open slot. Choose another start time or duration.')
            slot_id=str(uuid4())
            db.execute('INSERT INTO slots(id,doctor_id,starts_at,clinic_date,capacity,request_id,duration_minutes) VALUES(?,?,?,?,?,?,?)',
                       (slot_id,doctor,start.isoformat(),clinic_date,capacity,request_id,duration_minutes))
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

    def schedule_pattern(self, db, doctor):
        if not self.is_doctor(doctor,db):
            raise RuleError('Doctor not found.',404)
        row=db.execute('SELECT * FROM doctor_schedule_patterns WHERE doctor_id=?',(doctor,)).fetchone()
        return {'doctor_id':doctor,'doctor_name':self.user_name(db,doctor),'queue_prefix':self.queue_prefix(db,doctor),'day_sessions':[],'second_start_time':None,'second_end_time':None,
                **(json.loads(row['pattern_json']) if row else {'weekdays':[],'start_time':'09:00','end_time':'12:00','duration_minutes':30,'capacity':2}),
                'version':row['version'] if row else 0,'updated_at':row['updated_at'] if row else None}

    @staticmethod
    def unavailable_overlap(db, doctor, start, duration):
        return db.execute('''SELECT id FROM doctor_unavailability WHERE doctor_id=? AND cancelled_at IS NULL
            AND julianday(clinic_date||'T'||COALESCE(start_time,'00:00')||':00+08:00')<julianday(?)
            AND julianday(clinic_date||'T'||COALESCE(end_time,'24:00')||':00+08:00')>julianday(?) LIMIT 1''',
            (doctor,(start+timedelta(minutes=duration)).isoformat(),start.isoformat())).fetchone()

    def unavailability(self, doctor):
        if not self.is_doctor(doctor):
            raise RuleError('Doctor not found.',404)
        with self.connect() as db:
            return [dict(row) for row in db.execute('SELECT id,doctor_id,clinic_date,reason,created_at,cancelled_at,start_time,end_time FROM doctor_unavailability WHERE doctor_id=? ORDER BY clinic_date DESC,created_at DESC,id',
                        (doctor,)).fetchall()]

    def add_unavailability(self, doctor, clinic_date, reason, request_id, start_time=None, end_time=None):
        if not self.is_doctor(doctor):
            raise RuleError('Doctor not found.',404)
        if not reason.strip() or len(reason)>300:
            raise RuleError('Enter a reason up to 300 characters.',422)
        if (start_time is None)!=(end_time is None) or (start_time is not None and (
                any(not isinstance(value,str) or not re.fullmatch(r'(?:[01][0-9]|2[0-3]):[0-5][0-9]',value) for value in (start_time,end_time))
                or end_time<=start_time)):
            raise RuleError('Choose both start and end times, with the end later on the same day.',422)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT * FROM doctor_unavailability WHERE request_id=?',(request_id,)).fetchone()
            if old:
                if (old['doctor_id'],old['clinic_date'],old['reason'],old['start_time'],old['end_time'])!=(doctor,clinic_date,reason,start_time,end_time):
                    raise RuleError('This request already saved different unavailability details.')
                return {key:old[key] for key in ('id','doctor_id','clinic_date','reason','created_at','cancelled_at','start_time','end_time')}
            day=date.fromisoformat(clinic_date)
            if day<=datetime.now(MALAYSIA).date():
                raise RuleError('Choose a date after today in Malaysia.',422)
            try:next_day=day+timedelta(days=1)
            except OverflowError:raise RuleError('Choose an earlier date.',422)
            start=f'{day.isoformat()}T{start_time or "00:00"}:00+08:00'
            end=f'{day.isoformat()}T{end_time}:00+08:00' if end_time else f'{next_day.isoformat()}T00:00:00+08:00'
            duration=int((datetime.fromisoformat(end)-datetime.fromisoformat(start)).total_seconds()/60)
            if self.unavailable_overlap(db,doctor,datetime.fromisoformat(start),duration):
                raise RuleError('This period overlaps an active absence for this doctor.')
            booked=db.execute('''SELECT 1 FROM bookings b JOIN slots s ON s.id=b.slot_id
                WHERE s.doctor_id=? AND b.status!='cancelled'
                AND julianday(s.starts_at)<julianday(?)
                AND julianday(s.starts_at,'+'||s.duration_minutes||' minutes')>julianday(?) LIMIT 1''',(doctor,end,start)).fetchone()
            if booked:
                raise RuleError('This period overlaps booked visits. Resolve those appointments first; no visits were changed.')
            result={'id':str(uuid4()),'doctor_id':doctor,'clinic_date':clinic_date,'reason':reason,'created_at':datetime.now(timezone.utc).isoformat(),'cancelled_at':None,'start_time':start_time,'end_time':end_time}
            db.execute('INSERT INTO doctor_unavailability(id,doctor_id,clinic_date,reason,created_at,cancelled_at,start_time,end_time,request_id) VALUES(?,?,?,?,?,?,?,?,?)',(*result.values(),request_id))
            return result

    def cancel_unavailability(self, doctor, absence_id):
        if not self.is_doctor(doctor):
            raise RuleError('Doctor not found.',404)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT * FROM doctor_unavailability WHERE id=? AND doctor_id=?',(absence_id,doctor)).fetchone()
            if not row:
                raise RuleError('Unavailable date not found for this doctor.',404)
            if not row['cancelled_at']:
                if date.fromisoformat(row['clinic_date'])<=datetime.now(MALAYSIA).date():
                    raise RuleError('Only absences on a future Malaysia date can be cancelled.')
                db.execute('UPDATE doctor_unavailability SET cancelled_at=? WHERE id=?',
                           (datetime.now(timezone.utc).isoformat(),absence_id))
            saved=db.execute('SELECT id,doctor_id,clinic_date,reason,created_at,cancelled_at,start_time,end_time FROM doctor_unavailability WHERE id=?',(absence_id,)).fetchone()
            return dict(saved)

    def schedule_patterns(self):
        with self.connect() as db:
            return [self.schedule_pattern(db,doctor) for doctor in self.doctor_names(db)]

    def save_schedule_pattern(self, doctor, weekdays, start_time, end_time, duration_minutes, capacity, version, second_start_time=None, second_end_time=None, day_sessions=None):
        try:values=pattern_values(weekdays,start_time,end_time,duration_minutes,capacity,second_start_time,second_end_time,day_sessions)
        except ValueError as error:raise RuleError(str(error),422)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            current=self.schedule_pattern(db,doctor)
            if current['version'] and all(current[key]==value for key,value in values.items()):
                return current
            if current['version']!=version:
                raise RuleError('This weekly pattern changed. Reload it before editing again.')
            db.execute('''INSERT INTO doctor_schedule_patterns VALUES(?,?,?,?,?)
                ON CONFLICT(doctor_id) DO UPDATE SET pattern_json=excluded.pattern_json,version=excluded.version,
                updated_at=excluded.updated_at,actor_id=excluded.actor_id''',
                (doctor,json.dumps(values,sort_keys=True),version+1,datetime.now(timezone.utc).isoformat(),'staff-demo'))
            return self.schedule_pattern(db,doctor)

    def schedule_preview_record(self, db, doctor, week_start, version):
        pattern=self.schedule_pattern(db,doctor)
        if not pattern['version'] or pattern['version']!=version:
            raise RuleError('Save or reload the current weekly pattern before previewing.')
        try:planned=week_slots(pattern,week_start,datetime.now(MALAYSIA).date())
        except ValueError as error:raise RuleError(str(error),422)
        for slot in planned:
            if self.unavailable_overlap(db,doctor,datetime.fromisoformat(slot['starts_at']),slot['duration_minutes']):
                slot.update(status='unavailable',reason='Doctor unavailable. No slot will be created or reopened.')
                continue
            exact=db.execute('SELECT * FROM slots WHERE doctor_id=? AND julianday(starts_at)=julianday(?)',
                             (doctor,slot['starts_at'])).fetchone()
            if exact:
                slot['slot_id']=exact['id']
                if not exact['closed'] and (exact['duration_minutes'],exact['capacity'])==(slot['duration_minutes'],slot['capacity']):
                    slot.update(status='existing',reason='Matching open slot retained, including its bookings.')
                else:
                    slot.update(status='conflict',reason='An existing or closed slot has different details. No slot will be changed.')
            elif self.slot_overlap(db,doctor,datetime.fromisoformat(slot['starts_at']),slot['duration_minutes']):
                slot.update(status='conflict',reason='Overlaps an existing open slot for this doctor.')
            else:
                slot.update(status='new',reason='New appointment slot.')
        return {'doctor_id':doctor,'doctor_name':self.user_name(db,doctor),'week_start':week_start,'pattern_version':version,'slots':planned,
                'new_count':sum(slot['status']=='new' for slot in planned),
                'existing_count':sum(slot['status']=='existing' for slot in planned),
                'conflict_count':sum(slot['status']=='conflict' for slot in planned),
                'unavailable_count':sum(slot['status']=='unavailable' for slot in planned),
                'preview_token':preview_hash(doctor,version,week_start,planned)}

    def preview_schedule(self, doctor, week_start, version):
        with self.connect() as db:
            db.execute('BEGIN')
            return self.schedule_preview_record(db,doctor,week_start,version)

    def generate_schedule(self, doctor, week_start, version, token, request_id):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            previous=db.execute('SELECT * FROM schedule_generations WHERE request_id=?',(request_id,)).fetchone()
            if previous:
                if (previous['doctor_id'],previous['week_start'],previous['pattern_version'],previous['preview_token'])!=(doctor,week_start,version,token):
                    raise RuleError('This request already generated a different schedule.')
                return json.loads(previous['result_json'])
            preview=self.schedule_preview_record(db,doctor,week_start,version)
            if preview['preview_token']!=token:
                raise RuleError('Slot availability changed since preview. Preview the week again before confirming.')
            if preview['conflict_count']:
                raise RuleError('This week has slot conflicts. Resolve them before generating any slots.')
            ids=[]
            for slot in preview['slots']:
                if slot['status']=='unavailable':
                    continue
                if slot['status']=='existing':
                    ids.append(slot['slot_id'])
                    continue
                slot_id=str(uuid4());ids.append(slot_id)
                db.execute('INSERT INTO slots(id,doctor_id,starts_at,clinic_date,capacity,duration_minutes) VALUES(?,?,?,?,?,?)',
                           (slot_id,doctor,slot['starts_at'],slot['clinic_date'],slot['capacity'],slot['duration_minutes']))
            result={'id':str(uuid4()),'doctor_id':doctor,'week_start':week_start,'pattern_version':version,
                    'created_count':preview['new_count'],'existing_count':preview['existing_count'],
                    'unavailable_count':preview['unavailable_count'],
                    'slot_ids':ids,'created_at':datetime.now(timezone.utc).isoformat()}
            db.execute('INSERT INTO schedule_generations VALUES(?,?,?,?,?,?)',(request_id,doctor,week_start,version,token,json.dumps(result)))
            return result

    def doctor_schedule(self, doctor, week_start):
        if not self.is_doctor(doctor):
            raise RuleError('Doctor identity required.',403)
        monday=date.fromisoformat(week_start)
        if monday.weekday()!=0:
            raise RuleError('Choose the Monday starting the week.',422)
        with self.connect() as db:
            db.execute('BEGIN')
            rows=db.execute('SELECT id FROM slots WHERE doctor_id=? AND julianday(starts_at)>=julianday(?) AND julianday(starts_at)<julianday(?) ORDER BY julianday(starts_at),id',
                            (doctor,f'{monday.isoformat()}T00:00:00+08:00',f'{(monday+timedelta(days=7)).isoformat()}T00:00:00+08:00')).fetchall()
            slots=[]
            for row in rows:
                slot=self.managed_slot(db,row['id'])
                visits=db.execute('SELECT id,queue_number,status,patient_id FROM bookings WHERE slot_id=? ORDER BY queue_number',(row['id'],)).fetchall()
                # Operational schedule only: no background, notes, photo, reason, prescription or bill.
                slot['visits']=[{'id':visit['id'],'queue_number':visit['queue_number'],'status':visit['status'],'patient_name':self.user_name(db,visit['patient_id'])} for visit in visits]
                slots.append(slot)
            absences=db.execute('SELECT id,doctor_id,clinic_date,reason,created_at,cancelled_at,start_time,end_time FROM doctor_unavailability WHERE doctor_id=? AND clinic_date>=? AND clinic_date<? ORDER BY clinic_date,created_at,id',
                                (doctor,week_start,(monday+timedelta(days=7)).isoformat())).fetchall()
            return {'pattern':self.schedule_pattern(db,doctor),'week_start':week_start,'slots':slots,'unavailability':[dict(row) for row in absences]}

    def event(self, db, booking_id, actor, action):
        event_id=str(uuid4())
        db.execute('INSERT INTO events VALUES(?,?,?,?,?)',
                   (event_id, booking_id, actor, action, datetime.now(timezone.utc).isoformat()))
        return event_id

    def notify(self, db, patient, kind, source_id, target_id, title, message):
        db.execute('INSERT OR IGNORE INTO patient_notifications VALUES(?,?,?,?,?,?,?,?,NULL)',
                   (str(uuid4()),patient,kind,source_id,target_id,title,message,datetime.now(timezone.utc).isoformat()))

    def notifications(self, patient, cursor=None):
        if not self.is_patient(patient):
            raise RuleError('Patient identity required.',403)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            now=datetime.now(timezone.utc)
            window=(now.isoformat(),(now+timedelta(hours=24)).isoformat())
            visits=db.execute('''SELECT b.id,b.queue_number,s.doctor_id,s.starts_at FROM bookings b
                JOIN slots s ON s.id=b.slot_id WHERE b.patient_id=? AND b.status='waiting'
                AND julianday(s.starts_at)>julianday(?) AND julianday(s.starts_at)<=julianday(?)''',
                (patient,*window)).fetchall()
            for visit in visits:
                token=self.queue_token(db,visit)
                local_start=datetime.fromisoformat(visit['starts_at']).astimezone(timezone(timedelta(hours=8)))
                self.notify(db,patient,'appointment_reminder',visit['id'],visit['id'],'Upcoming appointment',
                            f"{token} with {self.user_name(db,visit['doctor_id'])} on {local_start:%d %b %Y, %I:%M %p} (Malaysia time). Open the visit to check its latest details.")
            boundary=''
            args=(patient,*window)
            if cursor is not None:
                anchor=db.execute('SELECT created_at,id FROM patient_notifications WHERE id=? AND patient_id=?',(cursor,patient)).fetchone()
                if not anchor:
                    raise RuleError('Invalid notification cursor. Refresh newest notifications.',422)
                boundary=' AND (n.created_at<? OR (n.created_at=? AND n.id<?))'
                args+= (anchor['created_at'],anchor['created_at'],anchor['id'])
            rows=db.execute(f'''SELECT n.* FROM patient_notifications n WHERE n.patient_id=? AND {NOTIFICATION_VISIBLE}{boundary}
                ORDER BY n.created_at DESC,n.id DESC LIMIT 101''',args).fetchall()
            unread=db.execute(f'''SELECT COUNT(*) FROM patient_notifications n
                WHERE n.patient_id=? AND n.read_at IS NULL AND {NOTIFICATION_VISIBLE}''',(patient,*window)).fetchone()[0]
            return {'items':[dict(row) for row in rows[:100]],'unread_count':unread,
                    'next_cursor':rows[99]['id'] if len(rows)>100 else None}

    def read_notification(self, notification_id, patient):
        if not self.is_patient(patient):
            raise RuleError('Patient identity required.',403)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            now=datetime.now(timezone.utc)
            row=db.execute(f'''SELECT n.* FROM patient_notifications n WHERE n.id=? AND n.patient_id=? AND {NOTIFICATION_VISIBLE}''',
                           (notification_id,patient,now.isoformat(),(now+timedelta(hours=24)).isoformat())).fetchone()
            if not row:
                raise RuleError('Notification unavailable for this patient.',404)
            if not row['read_at']:
                db.execute('UPDATE patient_notifications SET read_at=? WHERE id=?',(datetime.now(timezone.utc).isoformat(),notification_id))
            return dict(db.execute('SELECT * FROM patient_notifications WHERE id=?',(notification_id,)).fetchone())

    def unread_notification(self, notification_id, patient):
        if not self.is_patient(patient):
            raise RuleError('Patient identity required.',403)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            now=datetime.now(timezone.utc)
            window=(now.isoformat(),(now+timedelta(hours=24)).isoformat())
            row=db.execute(f'''SELECT n.* FROM patient_notifications n
                WHERE n.id=? AND n.patient_id=? AND {NOTIFICATION_VISIBLE}''',(notification_id,patient,*window)).fetchone()
            if not row:
                raise RuleError('Notification unavailable for this patient.',404)
            if row['read_at']:
                db.execute('UPDATE patient_notifications SET read_at=NULL WHERE id=?',(notification_id,))
            saved=dict(db.execute('SELECT * FROM patient_notifications WHERE id=?',(notification_id,)).fetchone())
            unread=db.execute(f'''SELECT COUNT(*) FROM patient_notifications n
                WHERE n.patient_id=? AND n.read_at IS NULL AND {NOTIFICATION_VISIBLE}''',(patient,*window)).fetchone()[0]
            return {'item':saved,'unread_count':unread}

    def read_notifications(self, notification_ids, patient):
        if not self.is_patient(patient):
            raise RuleError('Patient identity required.',403)
        if not notification_ids or len(notification_ids)>100:
            raise RuleError('Review between 1 and 100 displayed notifications.',400)
        ids=list(dict.fromkeys(notification_ids))
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            now=datetime.now(timezone.utc)
            window=(now.isoformat(),(now+timedelta(hours=24)).isoformat())
            placeholders=','.join('?' for _ in ids)
            rows=db.execute(f'''SELECT n.* FROM patient_notifications n
                WHERE n.id IN ({placeholders}) AND n.patient_id=? AND {NOTIFICATION_VISIBLE}''',
                (*ids,patient,*window)).fetchall()
            if len(rows)!=len(ids):
                raise RuleError('Some reviewed notifications are unavailable. Refresh the inbox and review again.',404)
            marked=sum(row['read_at'] is None for row in rows)
            db.execute(f'''UPDATE patient_notifications SET read_at=?
                WHERE id IN ({placeholders}) AND patient_id=? AND read_at IS NULL''',(now.isoformat(),*ids,patient))
            saved={row['id']:dict(row) for row in db.execute(f'SELECT * FROM patient_notifications WHERE id IN ({placeholders})',ids)}
            unread=db.execute(f'''SELECT COUNT(*) FROM patient_notifications n
                WHERE n.patient_id=? AND n.read_at IS NULL AND {NOTIFICATION_VISIBLE}''',(patient,*window)).fetchone()[0]
            return {'items':[saved[id] for id in ids],'marked_count':marked,'unread_count':unread}

    def record(self, db, booking_id):
        r = db.execute('''SELECT b.*, s.doctor_id, s.starts_at, s.clinic_date,s.duration_minutes,
                          h.finished_at AS consultation_finished_at FROM bookings b
                          JOIN slots s ON s.id=b.slot_id LEFT JOIN consultation_handoffs h ON h.booking_id=b.id
                          WHERE b.id=?''', (booking_id,)).fetchone()
        if r is None:
            raise RuleError('Booking not found.', 404)
        replacement = db.execute('SELECT new_booking_id FROM reschedules WHERE old_booking_id=?',(booking_id,)).fetchone()
        follow_up=db.execute('''SELECT f.source_booking_id,r.recommended_date FROM follow_up_bookings f
            JOIN follow_up_recommendations r ON r.source_booking_id=f.source_booking_id WHERE f.booking_id=?''',(booking_id,)).fetchone()
        attendance={}
        if r['status']=='missed':
            event=db.execute("SELECT id FROM events WHERE booking_id=? AND action='missed' ORDER BY rowid DESC LIMIT 1",(booking_id,)).fetchone()
            attendance={'missed_event_id':event['id'] if event else None}
        return dict(r, **attendance, queue_prefix=self.queue_prefix(db,r['doctor_id']), doctor_name=self.user_name(db,r['doctor_id']), patient_name=self.user_name(db,r['patient_id']),
                    ends_at=(datetime.fromisoformat(r['starts_at'])+timedelta(minutes=r['duration_minutes'])).isoformat(),
                    rescheduled_to_id=replacement['new_booking_id'] if replacement else None,
                    follow_up_source_id=follow_up['source_booking_id'] if follow_up else None,
                    follow_up_date=follow_up['recommended_date'] if follow_up else None)

    @staticmethod
    def check_patient_overlap(db, patient, starts_at, duration_minutes, exclude_booking=None):
        # Half-open intervals allow adjacent appointments; julianday normalises UTC offsets.
        # Call inside the same BEGIN IMMEDIATE transaction as the booking/status change.
        conflict=db.execute('''SELECT 1 FROM bookings b JOIN slots s ON s.id=b.slot_id
            WHERE b.patient_id=? AND b.status IN ('waiting','called') AND b.id!=?
              AND julianday(s.starts_at)<julianday(?,'+'||?||' minutes')
              AND julianday(s.starts_at,'+'||s.duration_minutes||' minutes')>julianday(?)
            LIMIT 1''',(patient,exclude_booking or '',starts_at,duration_minutes,starts_at)).fetchone()
        if conflict:
            raise RuleError('This patient already has an active visit that overlaps this time. Choose another time. No bookings were changed.')

    def book(self, patient, slot_id, request_id, created_by=None, follow_up_source=None):
        if not self.is_patient(patient):
            raise RuleError('Choose a recognised demo patient.', 422)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            recommendation=None
            if follow_up_source:
                source=self.record(db,follow_up_source)
                if source['patient_id']!=patient:
                    raise RuleError('Follow-up unavailable for this patient.',404)
                recommendation=self.follow_up_record(db,follow_up_source)
                if not recommendation or source['status'] not in ('called','completed'):
                    raise RuleError('No available follow-up recommendation for this visit.',404)
            existing = db.execute('SELECT id, slot_id FROM bookings WHERE patient_id=? AND request_id=?',
                                  (patient, request_id)).fetchone()
            if existing:
                if existing['slot_id'] != slot_id:
                    raise RuleError('This request was already used for a different slot.')
                if follow_up_source:
                    link=db.execute('SELECT source_booking_id FROM follow_up_bookings WHERE booking_id=?',(existing['id'],)).fetchone()
                    if not link or link['source_booking_id']!=follow_up_source:
                        raise RuleError('This request belongs to another booking. Use a new request.')
                return self.record(db, existing['id'])
            if recommendation and recommendation['booked_visit'] and recommendation['booked_visit']['status'] not in ('cancelled','missed'):
                raise RuleError('A follow-up is already booked. Open that visit to reschedule or cancel it.')
            slot = db.execute('SELECT * FROM slots WHERE id=?', (slot_id,)).fetchone()
            if slot is None:
                raise RuleError('Slot not found.', 404)
            if slot['closed']:
                raise RuleError('This slot is closed. Choose another time.')
            if self.unavailable_overlap(db,slot['doctor_id'],datetime.fromisoformat(slot['starts_at']),slot['duration_minutes']):
                raise RuleError('This doctor is unavailable during that slot. Choose another date.')
            if recommendation:
                self.validate_follow_up_slot(recommendation,slot)
            if datetime.fromisoformat(slot['starts_at']) <= datetime.now(timezone.utc):
                raise RuleError('This slot has already started. Choose another time.')
            if db.execute("SELECT 1 FROM bookings WHERE patient_id=? AND slot_id=? AND status!='cancelled'",
                          (patient, slot_id)).fetchone():
                raise RuleError('This patient already has a booking for this slot.')
            used = db.execute("SELECT COUNT(*) FROM bookings WHERE slot_id=? AND status!='cancelled'", (slot_id,)).fetchone()[0]
            if used >= slot['capacity']:
                raise RuleError('This slot is full. Please choose another time.')
            self.check_patient_overlap(db,patient,slot['starts_at'],slot['duration_minutes'])
            number = db.execute('''SELECT COALESCE(MAX(b.queue_number),0)+1 FROM bookings b JOIN slots s ON s.id=b.slot_id
                WHERE s.doctor_id=? AND s.clinic_date=?''', (slot['doctor_id'], slot['clinic_date'])).fetchone()[0]
            booking_id = str(uuid4())
            db.execute('INSERT INTO bookings VALUES(?,?,?,?,?,?,?)',
                       (booking_id, patient, slot_id, number, 'waiting', datetime.now(timezone.utc).isoformat(), request_id))
            self.event(db, booking_id, created_by or patient, 'counter-booked' if created_by else 'booked')
            if follow_up_source:
                db.execute('INSERT INTO follow_up_bookings VALUES(?,?)',(booking_id,follow_up_source))
                self.event(db,booking_id,patient,'follow-up-booked')
            return self.record(db, booking_id)

    def mine(self, patient):
        with self.connect() as db:
            ids = db.execute('SELECT id FROM bookings WHERE patient_id=? ORDER BY created_at DESC', (patient,)).fetchall()
            return [self.record(db, r['id']) for r in ids]

    def visit_details(self, booking_id, patient):
        with self.connect() as db:
            db.execute('BEGIN')
            visit=self.record(db,booking_id)
            if not self.is_patient(patient,db) or visit['patient_id']!=patient:
                raise RuleError('Visit unavailable for this patient.',404)
            note=db.execute('SELECT * FROM consultation_notes WHERE booking_id=?',(booking_id,)).fetchone()
            linked=[]
            for row in db.execute('SELECT id FROM assessment_shares WHERE booking_id=? ORDER BY created_at DESC LIMIT 100',(booking_id,)).fetchall():
                share=self.share_record(db,row['id'],patient)
                assessment=db.execute('SELECT id,patient_id,width,height,created_at,prediction_json,symptoms_json FROM assessments WHERE id=?',(share['assessment_id'],)).fetchone()
                linked.append(dict(share,assessment=self.assessment_metadata(assessment)))
            feedback=db.execute('SELECT * FROM visit_feedback WHERE booking_id=?',(booking_id,)).fetchone()
            replacement=self.record(db,visit['rescheduled_to_id']) if visit['rescheduled_to_id'] else None
            origin=db.execute('SELECT source_booking_id FROM follow_up_bookings WHERE booking_id=?',(booking_id,)).fetchone()
            return {'visit':visit,'linked_shares':linked,'note':dict(note) if note else None,
                    'prescription':self.prescription(db,booking_id),'invoice':self.invoice(db,booking_id),
                    'feedback':self.feedback_metadata(feedback) if feedback else None,'replacement':replacement,
                    'follow_up':self.follow_up_record(db,booking_id),
                    'follow_up_of':self.record(db,origin['source_booking_id']) if origin else None}

    @staticmethod
    def feedback_metadata(row):
        return dict(row,edit_deadline=(datetime.fromisoformat(row['created_at'])+timedelta(hours=24)).isoformat())

    def feedback(self, actor):
        if (not self.is_patient(actor) and actor!='staff-demo'):
            raise RuleError('Patient or staff demo identity required.',403)
        with self.connect() as db:
            rows = db.execute('''SELECT * FROM visit_feedback WHERE (?='staff-demo' OR patient_id=?)
                ORDER BY created_at DESC LIMIT 100''',(actor,actor)).fetchall()
            return [dict(self.feedback_metadata(row),visit=self.record(db,row['booking_id'])) for row in rows]

    def submit_feedback(self, booking_id, patient, rating, comment):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            visit=self.record(db,booking_id)
            if not self.is_patient(patient,db) or visit['patient_id']!=patient:
                raise RuleError('You cannot submit feedback for this visit.',403)
            if visit['status']!='completed':
                raise RuleError('Feedback is available after the visit is completed.')
            if type(rating) is not int or not 1<=rating<=5 or len(comment)>1000:
                raise RuleError('Choose a rating from 1 to 5 and a comment up to 1000 characters.',422)
            existing=db.execute('SELECT * FROM visit_feedback WHERE booking_id=?',(booking_id,)).fetchone()
            if existing:
                if existing['rating']!=rating or existing['comment']!=comment:
                    raise RuleError('Feedback was already submitted for this visit. Refresh to view it.')
                return dict(self.feedback_metadata(existing),visit=visit)
            feedback_id=str(uuid4())
            db.execute('INSERT INTO visit_feedback(id,booking_id,patient_id,rating,comment,created_at) VALUES(?,?,?,?,?,?)',(feedback_id,booking_id,patient,rating,comment,datetime.now(timezone.utc).isoformat()))
            self.event(db,booking_id,patient,'feedback-submitted')
            return dict(self.feedback_metadata(db.execute('SELECT * FROM visit_feedback WHERE id=?',(feedback_id,)).fetchone()),visit=visit)

    def edit_feedback(self, booking_id, patient, rating, comment, version):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            visit=self.record(db,booking_id)
            if not self.is_patient(patient,db) or visit['patient_id']!=patient:
                raise RuleError('You cannot edit feedback for this visit.',403)
            if visit['status']!='completed':
                raise RuleError('Feedback is available after the visit is completed.')
            if type(rating) is not int or not 1<=rating<=5 or len(comment)>1000 or type(version) is not int or version<0:
                raise RuleError('Choose a rating from 1 to 5, a comment up to 1000 characters and a valid version.',422)
            row=db.execute('SELECT * FROM visit_feedback WHERE booking_id=?',(booking_id,)).fetchone()
            if not row:
                raise RuleError('Submit feedback before editing it.',404)
            same=(row['rating'],row['comment'])==(rating,comment)
            # Return an exact successful retry even if its response was lost near the deadline.
            if row['version']==version+1 and same:
                return dict(self.feedback_metadata(row),visit=visit)
            if row['version']!=version:
                raise RuleError('This feedback changed in another session. Cancel and reopen it before editing again.')
            now=datetime.now(timezone.utc)
            if now>=datetime.fromisoformat(row['created_at'])+timedelta(hours=24):
                raise RuleError('The 24-hour editing window has closed. Your saved feedback is unchanged.')
            if not same:
                db.execute('UPDATE visit_feedback SET rating=?,comment=?,version=version+1,edited_at=? WHERE id=?',
                           (rating,comment,now.isoformat(),row['id']))
                self.event(db,booking_id,patient,'feedback-edited')
            saved=db.execute('SELECT * FROM visit_feedback WHERE id=?',(row['id'],)).fetchone()
            return dict(self.feedback_metadata(saved),visit=visit)

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
            follow_up=db.execute('SELECT source_booking_id FROM follow_up_bookings WHERE booking_id=?',(booking_id,)).fetchone()
            if follow_up:
                self.validate_follow_up_slot(self.follow_up_record(db,follow_up['source_booking_id']),slot)
            if slot['closed']:
                raise RuleError('This slot is closed. Choose another time.')
            if self.unavailable_overlap(db,slot['doctor_id'],datetime.fromisoformat(slot['starts_at']),slot['duration_minutes']):
                raise RuleError('This doctor is unavailable during that slot. Choose another date.')
            if datetime.fromisoformat(slot['starts_at']) <= datetime.now(timezone.utc):
                raise RuleError('This slot has already started. Choose another time.')
            if db.execute("SELECT 1 FROM bookings WHERE patient_id=? AND slot_id=? AND status!='cancelled'",(old['patient_id'],slot_id)).fetchone():
                raise RuleError('This patient already has a booking for this slot.')
            used = db.execute("SELECT COUNT(*) FROM bookings WHERE slot_id=? AND status!='cancelled'",(slot_id,)).fetchone()[0]
            if used >= slot['capacity']:
                raise RuleError('This slot is full. Your original booking is unchanged.')
            self.check_patient_overlap(db,old['patient_id'],slot['starts_at'],slot['duration_minutes'],booking_id)
            number = db.execute('''SELECT COALESCE(MAX(b.queue_number),0)+1 FROM bookings b JOIN slots s ON s.id=b.slot_id
                WHERE s.doctor_id=? AND s.clinic_date=?''',(slot['doctor_id'],slot['clinic_date'])).fetchone()[0]
            new_id, now = str(uuid4()), datetime.now(timezone.utc).isoformat()
            db.execute("UPDATE bookings SET status='cancelled' WHERE id=?",(booking_id,))
            db.execute('INSERT INTO bookings VALUES(?,?,?,?,?,?,?)',(new_id,old['patient_id'],slot_id,number,'waiting',now,'reschedule-'+new_id))
            if follow_up:
                db.execute('INSERT INTO follow_up_bookings VALUES(?,?)',(new_id,follow_up['source_booking_id']))
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
            if not self.is_doctor(doctor,db):raise RuleError('Choose a recognised doctor.',422)
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
            if not self.is_doctor(doctor,db):raise RuleError('Choose a recognised doctor.',422)
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
            token=self.queue_token(db,visit)
            self.notify(db,visit['patient_id'],'queue_called',row['id'],row['id'],'Your queue number was called',
                        f"{token} with {self.user_name(db,doctor)} was called. Open the visit to check its current status.")
            return self.record(db, row['id'])

    def mark_missed(self, booking_id, staff):
        if staff!='staff-demo':
            raise RuleError('Staff demo identity required.',403)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            visit=self.record(db,booking_id)
            if visit['status']=='missed':
                return visit
            if visit['status']!='waiting':
                raise RuleError('Only a waiting appointment can be marked missed.')
            if datetime.fromisoformat(visit['ends_at'])>datetime.now(timezone.utc):
                raise RuleError('Wait until the scheduled appointment has ended before marking it missed.')
            db.execute("UPDATE bookings SET status='missed' WHERE id=?",(booking_id,))
            db.execute('UPDATE assessment_shares SET revoked_at=? WHERE booking_id=? AND revoked_at IS NULL',
                       (datetime.now(timezone.utc).isoformat(),booking_id))
            self.event(db,booking_id,staff,'missed')
            return self.record(db,booking_id)

    def restore_waiting(self, booking_id, missed_event_id, staff):
        if staff!='staff-demo':
            raise RuleError('Staff demo identity required.',403)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            visit=self.record(db,booking_id)
            latest=db.execute("SELECT id FROM events WHERE booking_id=? AND action='missed' ORDER BY rowid DESC LIMIT 1",(booking_id,)).fetchone()
            if not latest or latest['id']!=missed_event_id:
                raise RuleError('Attendance changed. Refresh and review the latest missed appointment.')
            restored=db.execute('SELECT 1 FROM missed_restorations WHERE missed_event_id=?',(missed_event_id,)).fetchone()
            if visit['status']=='waiting' and restored:
                return visit
            if visit['status']!='missed' or restored:
                raise RuleError('Only the currently missed appointment can be restored to waiting.')
            source=visit.get('follow_up_source_id')
            if source and db.execute("""SELECT 1 FROM follow_up_bookings f JOIN bookings b ON b.id=f.booking_id
                    WHERE f.source_booking_id=? AND b.id!=? AND b.status NOT IN ('cancelled','missed') LIMIT 1""",(source,booking_id)).fetchone():
                raise RuleError('Another follow-up is already active. Review that booking before restoring this visit.')
            self.check_patient_overlap(db,visit['patient_id'],visit['starts_at'],visit['duration_minutes'],booking_id)
            db.execute("UPDATE bookings SET status='waiting' WHERE id=?",(booking_id,))
            event_id=self.event(db,booking_id,staff,'missed-restored')
            db.execute('INSERT INTO missed_restorations VALUES(?,?)',(missed_event_id,event_id))
            # Revoked assessment grants stay revoked; sharing requires patient consent.
            return self.record(db,booking_id)

    def finish_consultation(self, booking_id, doctor):
        if not self.is_doctor(doctor):
            raise RuleError('Doctor identity required.',403)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            visit=self.record(db,booking_id)
            if visit['doctor_id']!=doctor:
                raise RuleError('This visit belongs to another doctor.',403)
            if visit['consultation_finished_at']:
                return visit
            if visit['status']!='called':
                raise RuleError('Only a called visit can be handed over to checkout.')
            note=db.execute('SELECT id FROM consultation_notes WHERE booking_id=? AND doctor_id=?',(booking_id,doctor)).fetchone()
            if not note:
                raise RuleError('Publish the consultation note before finishing. A prescription is optional.')
            prescription=db.execute('''SELECT id FROM prescriptions WHERE booking_id=? AND NOT EXISTS
                (SELECT 1 FROM prescription_cancellations c WHERE c.prescription_id=prescriptions.id)''',(booking_id,)).fetchone()
            db.execute('INSERT INTO consultation_handoffs VALUES(?,?,?,?,?)',
                       (booking_id,doctor,note['id'],prescription['id'] if prescription else None,datetime.now(timezone.utc).isoformat()))
            self.event(db,booking_id,doctor,'consultation-finished')
            return self.record(db,booking_id)

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

    @staticmethod
    def medicine_record(row):
        result=dict(row)
        # Saved retry responses from before per-item levels retain their historical default.
        result.setdefault('low_stock_threshold',5)
        result.setdefault('target_stock',None)
        result['active']=bool(result['active'])
        return result

    def catalog(self, active_only=False):
        with self.connect() as db:
            return [self.medicine_record(r) for r in db.execute('SELECT id,name,strength,form,price_cents,stock,version,updated_at,active,low_stock_threshold,target_stock FROM medicines WHERE (?=0 OR active=1) ORDER BY id',(int(active_only),))]

    def add_medicine(self, name, strength, form, price_cents, request_id):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT * FROM medicines WHERE request_id=?',(request_id,)).fetchone()
            values = (name,strength,form,price_cents)
            if old:
                original=json.loads(old['creation_json']) if old['creation_json'] else old
                if tuple(original[k] for k in ('name','strength','form','price_cents')) != values:
                    raise RuleError('This catalogue request was already saved with different details.')
                return self.medicine_record({k:old[k] for k in ('id','name','strength','form','price_cents','stock','version','updated_at','active','low_stock_threshold','target_stock')})
            if db.execute('''SELECT 1 FROM medicines WHERE lower(name)=lower(?)
                             AND lower(strength)=lower(?) AND lower(form)=lower(?)''',values[:3]).fetchone():
                raise RuleError('This name, strength and form already exist. Receive stock for the existing item.')
            medicine_id = str(uuid4())
            db.execute('INSERT INTO medicines(id,name,strength,form,price_cents,stock,request_id,creation_json) VALUES(?,?,?,?,?,0,?,?)',
                       (medicine_id,*values,request_id,json.dumps(dict(zip(('name','strength','form','price_cents'),values)))))
            return {'id':medicine_id,'name':name,'strength':strength,'form':form,'price_cents':price_cents,'stock':0,'version':0,'updated_at':None,'active':True,'low_stock_threshold':5,'target_stock':None}

    def edit_medicine(self, medicine_id, name, price_cents, version, request_id, staff):
        if not name.strip() or len(name)>100 or type(price_cents) is not int or not 0<=price_cents<=1000000 or type(version) is not int or version<0:
            raise RuleError('Enter a name up to 100 characters and a valid unit price.',422)
        name=name.strip()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            retry=db.execute('SELECT * FROM medicine_edits WHERE request_id=?',(request_id,)).fetchone()
            if retry:
                if (retry['medicine_id'],retry['name'],retry['price_cents'],retry['from_version'])!=(medicine_id,name,price_cents,version):
                    raise RuleError('This request already saved different catalogue changes.')
                return self.medicine_record({'active':True,**json.loads(retry['result_json'])})
            current=db.execute('SELECT * FROM medicines WHERE id=?',(medicine_id,)).fetchone()
            if current is None:raise RuleError('Medicine not found.',404)
            if current['version']!=version:
                raise RuleError('This catalogue item changed. Reload the latest item before editing again.')
            if (current['name'],current['price_cents'])==(name,price_cents):
                raise RuleError('Change the name or unit price before saving.',422)
            if db.execute('''SELECT 1 FROM medicines WHERE id!=? AND lower(name)=lower(?)
                AND lower(strength)=lower(?) AND lower(form)=lower(?)''',(medicine_id,name,current['strength'],current['form'])).fetchone():
                raise RuleError('This name, strength and form already exist. Choose a different name.')
            now=datetime.now(timezone.utc).isoformat()
            db.execute('UPDATE medicines SET name=?,price_cents=?,version=version+1,updated_at=? WHERE id=?',(name,price_cents,now,medicine_id))
            saved=self.medicine_record(db.execute('SELECT id,name,strength,form,price_cents,stock,version,updated_at,active,low_stock_threshold,target_stock FROM medicines WHERE id=?',(medicine_id,)).fetchone())
            db.execute('INSERT INTO medicine_edits VALUES(?,?,?,?,?,?,?,?,?,?)',
                       (request_id,medicine_id,version,name,price_cents,current['name'],current['price_cents'],staff,now,json.dumps(saved)))
            return saved

    def set_medicine_target(self, medicine_id, target, version, request_id, staff):
        if (target is not None and (type(target) is not int or not 0<=target<=99999)) or type(version) is not int or version<0:
            raise RuleError('Enter a whole target from 0 to 99,999, or leave it unset.',422)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            retry=db.execute('SELECT * FROM medicine_target_changes WHERE request_id=?',(request_id,)).fetchone()
            if retry:
                if (retry['medicine_id'],retry['target'],retry['from_version'])!=(medicine_id,target,version):
                    raise RuleError('This request already saved a different stock target.')
                return self.medicine_record(json.loads(retry['result_json']))
            current=db.execute('SELECT * FROM medicines WHERE id=?',(medicine_id,)).fetchone()
            if current is None:raise RuleError('Medicine not found.',404)
            if current['version']!=version:
                raise RuleError('This catalogue item changed. Reload the latest item before changing its target.')
            if target is not None and target<current['low_stock_threshold']:
                raise RuleError('Target stock must be at least the alert level.',422)
            if current['target_stock']==target:raise RuleError('Change the target before saving.',422)
            now=datetime.now(timezone.utc).isoformat()
            db.execute('UPDATE medicines SET target_stock=?,version=version+1,updated_at=? WHERE id=?',(target,now,medicine_id))
            saved=self.medicine_record(db.execute('SELECT id,name,strength,form,price_cents,stock,version,updated_at,active,low_stock_threshold,target_stock FROM medicines WHERE id=?',(medicine_id,)).fetchone())
            db.execute('INSERT INTO medicine_target_changes VALUES(?,?,?,?,?,?,?,?)',
                (request_id,medicine_id,version,target,current['target_stock'],staff,now,json.dumps(saved)))
            return saved

    def set_medicine_threshold(self, medicine_id, threshold, version, request_id, staff):
        if type(threshold) is not int or not 0<=threshold<=99999 or type(version) is not int or version<0:
            raise RuleError('Enter a whole alert level from 0 to 99,999 and a valid version.',422)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            retry=db.execute('SELECT * FROM medicine_threshold_changes WHERE request_id=?',(request_id,)).fetchone()
            if retry:
                if (retry['medicine_id'],retry['threshold'],retry['from_version'])!=(medicine_id,threshold,version):
                    raise RuleError('This request already saved a different alert level.')
                return self.medicine_record(json.loads(retry['result_json']))
            current=db.execute('SELECT * FROM medicines WHERE id=?',(medicine_id,)).fetchone()
            if current is None:raise RuleError('Medicine not found.',404)
            if current['version']!=version:
                raise RuleError('This catalogue item changed. Reload the latest item before changing its alert level.')
            if current['target_stock'] is not None and threshold>current['target_stock']:
                raise RuleError('Alert level cannot exceed target stock. Raise or clear the target first.',422)
            if current['low_stock_threshold']==threshold:
                raise RuleError('Change the alert level before saving.',422)
            now=datetime.now(timezone.utc).isoformat()
            db.execute('UPDATE medicines SET low_stock_threshold=?,version=version+1,updated_at=? WHERE id=?',(threshold,now,medicine_id))
            saved=self.medicine_record(db.execute('SELECT id,name,strength,form,price_cents,stock,version,updated_at,active,low_stock_threshold,target_stock FROM medicines WHERE id=?',(medicine_id,)).fetchone())
            db.execute('INSERT INTO medicine_threshold_changes VALUES(?,?,?,?,?,?,?,?)',
                       (request_id,medicine_id,version,threshold,current['low_stock_threshold'],staff,now,json.dumps(saved)))
            return saved

    def set_medicine_active(self, medicine_id, active, version, request_id, staff):
        if type(active) is not bool or type(version) is not int or version<0:
            raise RuleError('Choose a valid catalogue status and version.',422)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            retry=db.execute('SELECT * FROM medicine_status_changes WHERE request_id=?',(request_id,)).fetchone()
            if retry:
                if (retry['medicine_id'],bool(retry['active']),retry['from_version'])!=(medicine_id,active,version):
                    raise RuleError('This request already saved a different catalogue status change.')
                return self.medicine_record(json.loads(retry['result_json']))
            current=db.execute('SELECT * FROM medicines WHERE id=?',(medicine_id,)).fetchone()
            if current is None:raise RuleError('Medicine not found.',404)
            if current['version']!=version:
                raise RuleError('This catalogue item changed. Reload the latest item before changing its status.')
            if bool(current['active'])==active:
                raise RuleError('This item already has that status. Reload the catalogue.',422)
            now=datetime.now(timezone.utc).isoformat()
            db.execute('UPDATE medicines SET active=?,version=version+1,updated_at=? WHERE id=?',(int(active),now,medicine_id))
            saved=self.medicine_record(db.execute('SELECT id,name,strength,form,price_cents,stock,version,updated_at,active,low_stock_threshold,target_stock FROM medicines WHERE id=?',(medicine_id,)).fetchone())
            db.execute('INSERT INTO medicine_status_changes VALUES(?,?,?,?,?,?,?,?)',
                       (request_id,medicine_id,version,int(active),current['active'],staff,now,json.dumps(saved)))
            return saved

    @staticmethod
    def validate_summary_filter(period,year,month,quarter):
        valid=period in ('month','quarter','year') and type(year) is int and 2<=year<=9998
        if period=='month':valid=valid and type(month) is int and 1<=month<=12 and quarter is None
        elif period=='quarter':valid=valid and type(quarter) is int and 1<=quarter<=4 and month is None
        elif period=='year':valid=valid and month is None and quarter is None
        if not valid:raise RuleError('Choose a valid month, quarter or year (year 2–9998) with its matching filter.',422)

    def billing_summary(self,period,year,month=None,quarter=None):
        from .billing_reporting import summary
        self.validate_summary_filter(period,year,month,quarter)
        with self.connect() as db:
            db.execute('BEGIN')
            return summary(db,period,year,month,quarter)

    def feedback_summary(self,period,year,month=None,quarter=None):
        from .feedback_reporting import summary
        self.validate_summary_filter(period,year,month,quarter)
        with self.connect() as db:
            db.execute('BEGIN')
            return summary(db,period,year,month,quarter)

    def inventory_summary(self,period,year,month=None,quarter=None):
        from .inventory_reporting import summary
        self.validate_summary_filter(period,year,month,quarter)
        with self.connect() as db:
            db.execute('BEGIN')
            return summary(db,period,year,month,quarter)

    def visit_summary(self,period,year,month=None,quarter=None):
        from .visit_reporting import summary
        self.validate_summary_filter(period,year,month,quarter)
        with self.connect() as db:
            db.execute('BEGIN')
            return summary(db,period,year,month,quarter)

    def weekly_report(self, week_of):
        try:
            chosen=date.fromisoformat(week_of)
            start=chosen-timedelta(days=chosen.weekday())
            end=start+timedelta(days=6)
        except (ValueError,OverflowError):
            raise RuleError('Choose a date within a complete Monday-to-Sunday week.',422)
        states=('waiting','called','completed','cancelled','missed','rescheduled','total')
        days={ (start+timedelta(days=offset)).isoformat():dict.fromkeys(states,0) for offset in range(7) }
        totals=dict.fromkeys(states,0)
        with self.connect() as db:
            db.execute('BEGIN')
            for row in db.execute('''SELECT s.clinic_date,
                    CASE WHEN EXISTS(SELECT 1 FROM reschedules r WHERE r.old_booking_id=b.id)
                    THEN 'rescheduled' ELSE b.status END AS state,COUNT(*) AS total
                FROM bookings b JOIN slots s ON s.id=b.slot_id
                WHERE s.clinic_date BETWEEN ? AND ? GROUP BY s.clinic_date,state''',(start.isoformat(),end.isoformat())):
                days[row['clinic_date']][row['state']]+=row['total']
                days[row['clinic_date']]['total']+=row['total']
                totals[row['state']]+=row['total']
                totals['total']+=row['total']
            return {'week_start':start.isoformat(),'week_end':end.isoformat(),'timezone':'Asia/Kuala_Lumpur',
                'generated_at':datetime.now(timezone.utc).isoformat(),'visits':totals,
                'days':[{'clinic_date':day,'visits':counts} for day,counts in days.items()]}

    def daily_report(self, clinic_date):
        with self.connect() as db:
            db.execute('BEGIN')
            visits={key:0 for key in ('waiting','called','completed','cancelled','missed','rescheduled')}
            doctors=self.doctor_names(db)
            doctor_visits={doctor:dict(visits,total=0) for doctor in doctors}
            for row in db.execute('''SELECT s.doctor_id,CASE WHEN EXISTS(SELECT 1 FROM reschedules r WHERE r.old_booking_id=b.id)
                    THEN 'rescheduled' ELSE b.status END AS state,COUNT(*) AS total
                FROM bookings b JOIN slots s ON s.id=b.slot_id WHERE s.clinic_date=? GROUP BY s.doctor_id,state''',(clinic_date,)):
                visits[row['state']]+=row['total']
                doctor_visits[row['doctor_id']][row['state']]=row['total']
                doctor_visits[row['doctor_id']]['total']+=row['total']
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
                lost=db.execute("SELECT COALESCE(SUM(quantity),0) FROM stock_losses WHERE medicine_id=? AND date(created_at,'+8 hours')=?",(medicine['id'],clinic_date)).fetchone()[0]
                movements.append({'medicine_id':medicine['id'],'name':medicine['name'],'received':received,'dispensed':dispensed,'lost':lost})
            feedback=db.execute("SELECT COUNT(*) AS total,AVG(rating) AS average FROM visit_feedback WHERE date(created_at,'+8 hours')=?",(clinic_date,)).fetchone()
            return {'clinic_date':clinic_date,'timezone':'Asia/Kuala_Lumpur','generated_at':datetime.now(timezone.utc).isoformat(),
                    'visits':visits,'visits_by_doctor':[{'doctor_id':doctor,'doctor_name':name,'visits':doctor_visits[doctor]} for doctor,name in doctors.items()],
                    'billing':billing,'stock':{'items':movements,'received_units':sum(m['received'] for m in movements),'dispensed_units':sum(m['dispensed'] for m in movements),'lost_units':sum(m['lost'] for m in movements)},
                    'feedback':{'count':feedback['total'],'average_rating':round(feedback['average'],2) if feedback['average'] is not None else None}}

    def stock(self):
        with self.connect() as db:
            db.execute('BEGIN')
            medicines=[self.medicine_record(r) for r in db.execute('SELECT id,name,strength,form,price_cents,stock,version,updated_at,active,low_stock_threshold,target_stock FROM medicines ORDER BY id')]
            receipts=[dict(r) for r in db.execute('''SELECT r.*,m.name FROM stock_receipts r JOIN medicines m ON m.id=r.medicine_id
                ORDER BY r.created_at DESC LIMIT 100''')]
            losses=[dict(row) for row in db.execute('SELECT * FROM stock_losses ORDER BY created_at DESC,id DESC LIMIT 100')]
            # The overview field remains the legacy default; alerts use each medicine's level.
            return {'medicines':medicines,'receipts':receipts,'losses':losses,'low_stock_threshold':5}

    def stock_movements(self, medicine_id, cursor=None):
        with self.connect() as db:
            db.execute('BEGIN')
            medicine=db.execute('SELECT id,name,strength,form,price_cents,stock,version,updated_at,active,low_stock_threshold,target_stock FROM medicines WHERE id=?',(medicine_id,)).fetchone()
            if medicine is None:raise RuleError('Stock item not found.',404)
            movements_sql="""WITH movements AS (
                SELECT id AS source_id,'received' AS kind,quantity AS change,created_at,
                    reason,stock_before,stock_after,actor_id,NULL AS item_label
                FROM stock_receipts WHERE medicine_id=?
                UNION ALL
                SELECT id,kind,-quantity,created_at,reason,stock_before,stock_after,actor_id,item_label
                FROM stock_losses WHERE medicine_id=?
                UNION ALL
                SELECT p.id,'dispensed',-i.quantity,p.dispensed_at,NULL,NULL,NULL,NULL,
                    i.name || CASE WHEN i.strength!='' THEN ' · '||i.strength ELSE '' END ||
                    CASE WHEN i.form!='' THEN ' · '||i.form ELSE '' END
                FROM prescription_items i JOIN prescriptions p ON p.id=i.prescription_id
                WHERE i.medicine_id=? AND p.status='dispensed'
                ) """
            params=(medicine_id,medicine_id,medicine_id)
            boundary_sql=''
            boundary_params=()
            if cursor is not None:
                if not isinstance(cursor,str) or len(cursor)>200 or ':' not in cursor:
                    raise RuleError('Invalid movement cursor. Refresh newest movements.',422)
                kind,source_id=cursor.split(':',1)
                anchor=db.execute(movements_sql+'SELECT julianday(created_at) AS time FROM movements WHERE kind=? AND source_id=?',params+(kind,source_id)).fetchone()
                if anchor is None or anchor['time'] is None:
                    raise RuleError('Movement cursor does not belong to this medicine. Refresh newest movements.',422)
                boundary_sql='WHERE julianday(created_at)<? OR (julianday(created_at)=? AND (kind>? OR (kind=? AND source_id<?)))'
                boundary_params=(anchor['time'],anchor['time'],kind,kind,source_id)
            rows=db.execute(movements_sql+'SELECT * FROM movements '+boundary_sql+' ORDER BY julianday(created_at) DESC,kind,source_id DESC LIMIT 101',params+boundary_params).fetchall()
            next_cursor=f"{rows[99]['kind']}:{rows[99]['source_id']}" if len(rows)>100 else None
            return {'medicine':self.medicine_record(medicine),'movements':[dict(r) for r in rows[:100]],'has_more':len(rows)>100,'next_cursor':next_cursor}

    def stock_expiry(self, as_of=None):
        today=as_of or datetime.now(MALAYSIA).date()
        end=today+timedelta(days=30)
        with self.connect() as db:
            db.execute('BEGIN')
            counts=db.execute("SELECT SUM(CASE WHEN expiry_date<? THEN 1 ELSE 0 END) AS expired, SUM(CASE WHEN expiry_date>=? AND expiry_date<=? THEN 1 ELSE 0 END) AS due_soon, SUM(CASE WHEN expiry_date IS NULL THEN 1 ELSE 0 END) AS untracked FROM stock_receipts r LEFT JOIN receipt_balances b ON b.receipt_id=r.id WHERE b.receipt_id IS NULL OR b.remaining_units>0",(today.isoformat(),today.isoformat(),end.isoformat())).fetchone()
            rows=[dict(row) for row in db.execute("""SELECT r.id,r.medicine_id,r.batch_number,r.expiry_date,r.quantity,r.created_at,
                m.name,m.strength,m.form,m.active,b.remaining_units FROM stock_receipts r JOIN medicines m ON m.id=r.medicine_id LEFT JOIN receipt_balances b ON b.receipt_id=r.id
                WHERE r.expiry_date IS NOT NULL AND r.expiry_date<=? AND (b.receipt_id IS NULL OR b.remaining_units>0) ORDER BY r.expiry_date,r.id LIMIT 201""",(end.isoformat(),))]
            for row in rows:
                row['active']=bool(row['active'])
                row['days_to_expiry']=(date.fromisoformat(row['expiry_date'])-today).days
            return {'as_of':today.isoformat(),'through_date':end.isoformat(),'timezone':'Asia/Kuala_Lumpur',
                'expired_receipts':counts['expired'] or 0,'due_soon_receipts':counts['due_soon'] or 0,
                'untracked_receipts':counts['untracked'] or 0,'items':rows[:200],'has_more':len(rows)>200}

    def receive_stock(self, medicine_id, quantity, reason, request_id, staff, batch_number=None, expiry_date=None):
        if staff!='staff-demo':
            raise RuleError('Staff demo identity required.',403)
        if type(quantity) is not int or not 1<=quantity<=1000 or not reason.strip() or len(reason)>300:
            raise RuleError('Enter a whole quantity from 1 to 1000 and a reason up to 300 characters.',422)
        reason=reason.strip()
        if batch_number is not None:
            if not isinstance(batch_number,str) or not batch_number.strip() or len(batch_number)>60:
                raise RuleError('Enter a batch number up to 60 characters.',422)
            batch_number=batch_number.strip()
        if (batch_number is None)!=(expiry_date is None):
            raise RuleError('Provide both batch number and expiry date, or leave both unset.',422)
        if expiry_date is not None:
            try:
                if not isinstance(expiry_date,str) or date.fromisoformat(expiry_date).isoformat()!=expiry_date:raise ValueError()
            except (TypeError,ValueError):raise RuleError('Enter a valid expiry date in YYYY-MM-DD format.',422)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            existing=db.execute('SELECT * FROM stock_receipts WHERE request_id=?',(request_id,)).fetchone()
            if existing:
                if (existing['medicine_id'],existing['quantity'],existing['reason'],existing['batch_number'],existing['expiry_date'])!=(medicine_id,quantity,reason,batch_number,expiry_date):
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
            db.execute('INSERT INTO stock_receipts(id,medicine_id,quantity,reason,stock_before,stock_after,actor_id,request_id,created_at,batch_number,expiry_date) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                (receipt_id,medicine_id,quantity,reason,medicine['stock'],after,staff,request_id,datetime.now(timezone.utc).isoformat(),batch_number,expiry_date))
            if batch_number is not None:db.execute('INSERT INTO receipt_balances(receipt_id,remaining_units) VALUES(?,?)',(receipt_id,quantity))
            return dict(db.execute('SELECT * FROM stock_receipts WHERE id=?',(receipt_id,)).fetchone())

    def usable_stock_alerts(self):
        today=datetime.now(MALAYSIA).date().isoformat()
        with self.connect() as db:
            db.execute('BEGIN')
            rows=[dict(row) for row in db.execute('''SELECT m.id AS medicine_id,m.name,m.strength,m.form,m.stock,m.low_stock_threshold,
                COALESCE(SUM(b.remaining_units),0) AS tracked_units,
                COALESCE(SUM(CASE WHEN r.expiry_date>=? AND b.held=0 THEN b.remaining_units ELSE 0 END),0) AS usable_units
                FROM medicines m LEFT JOIN stock_receipts r ON r.medicine_id=m.id
                LEFT JOIN receipt_balances b ON b.receipt_id=r.id WHERE m.active=1
                GROUP BY m.id ORDER BY usable_units,m.name COLLATE NOCASE,m.id''',(today,))]
            alerts=[]
            for row in rows:
                if row['usable_units']>row['low_stock_threshold']:continue
                row['untracked_units']=max(0,row['stock']-row['tracked_units'])
                row['blocked_tracked_units']=row['tracked_units']-row['usable_units']
                alerts.append(row)
            return {'as_of':today,'active_items':len(rows),'alerts':alerts,
                'no_usable_items':sum(row['usable_units']==0 for row in alerts),
                'low_usable_items':sum(row['usable_units']>0 for row in alerts),
                'untracked_review_items':sum(row['untracked_units']>0 for row in alerts)}

    def set_batch_hold(self, medicine_id, receipt_id, held, reason, version, request_id, staff):
        from .batch_holds import change
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            return change(db,medicine_id,receipt_id,held,reason,version,request_id,staff,RuleError)

    def batch_movement_history(self, medicine_id, receipt_id):
        from .batch_history import history
        with self.connect() as db:
            db.execute('BEGIN')
            return history(db,medicine_id,receipt_id,RuleError)

    def batch_stock_overview(self, medicine_id):
        from .batch_inventory import sources
        with self.connect() as db:
            db.execute('BEGIN')
            medicine=db.execute('SELECT id,name,strength,form,price_cents,stock,version,updated_at,active,low_stock_threshold,target_stock FROM medicines WHERE id=?',(medicine_id,)).fetchone()
            if medicine is None:raise RuleError('Stock item not found.',404)
            return {**sources(db,medicine_id),'medicine':self.medicine_record(medicine),'as_of':datetime.now(MALAYSIA).date().isoformat()}

    def stock_batches(self, medicine_id):
        with self.connect() as db:
            db.execute('BEGIN')
            if not db.execute('SELECT 1 FROM medicines WHERE id=?',(medicine_id,)).fetchone():raise RuleError('Stock item not found.',404)
            rows=[dict(row) for row in db.execute("""SELECT r.id AS receipt_id,r.batch_number,r.expiry_date,r.quantity,r.created_at,
                COALESCE(SUM(l.quantity),0) AS loss_units FROM stock_receipts r LEFT JOIN stock_losses l ON l.receipt_id=r.id
                WHERE r.medicine_id=? AND r.batch_number IS NOT NULL AND r.expiry_date IS NOT NULL
                GROUP BY r.id ORDER BY r.expiry_date,r.created_at,r.id""",(medicine_id,))]
            for row in rows:
                row['loss_allowance']=max(0,row['quantity']-row['loss_units'])
                balance=db.execute('SELECT remaining_units FROM receipt_balances WHERE receipt_id=?',(row['receipt_id'],)).fetchone()
                row['remaining_units']=balance['remaining_units'] if balance else None
            return rows

    def record_stock_loss(self, medicine_id, quantity, kind, reason, request_id, staff, receipt_id=None):
        if staff!='staff-demo':raise RuleError('Staff demo identity required.',403)
        if type(quantity) is not int or not 1<=quantity<=1000 or kind not in ('damaged','lost') or not reason.strip() or len(reason)>300:
            raise RuleError('Choose damaged or lost, a whole quantity from 1 to 1000 and a reason up to 300 characters.',422)
        reason=reason.strip()
        if receipt_id is not None and (not isinstance(receipt_id,str) or not receipt_id or len(receipt_id)>100):
            raise RuleError('Choose a valid receipt batch.',422)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            existing=db.execute('SELECT * FROM stock_losses WHERE request_id=?',(request_id,)).fetchone()
            if existing:
                if (existing['medicine_id'],existing['quantity'],existing['kind'],existing['reason'],existing['receipt_id'])!=(medicine_id,quantity,kind,reason,receipt_id):
                    raise RuleError('This stock-loss request already saved different details. Check the history.')
                return dict(existing)
            medicine=db.execute('SELECT * FROM medicines WHERE id=?',(medicine_id,)).fetchone()
            if medicine is None:raise RuleError('Stock item not found.',404)
            if medicine['stock']<quantity:
                raise RuleError('Insufficient stock for this deduction. Reload the current stock; nothing was deducted.')
            after=medicine['stock']-quantity
            label=' · '.join(value for value in (medicine['name'],medicine['strength'],medicine['form']) if value)
            receipt=None
            if receipt_id is not None:
                receipt=db.execute('SELECT * FROM stock_receipts WHERE id=?',(receipt_id,)).fetchone()
                if receipt is None:raise RuleError('Receipt batch not found.',404)
                if receipt['medicine_id']!=medicine_id or receipt['batch_number'] is None or receipt['expiry_date'] is None:
                    raise RuleError('Choose a recorded batch receipt for this medicine.',422)
                used=db.execute('SELECT COALESCE(SUM(quantity),0) FROM stock_losses WHERE receipt_id=?',(receipt_id,)).fetchone()[0]
                if quantity>receipt['quantity']-used:
                    raise RuleError('Batch-linked losses would exceed the quantity originally received. Reload batches and check physical stock.')
            from .batch_inventory import sources
            available=sources(db,medicine_id)
            balance=db.execute('SELECT remaining_units FROM receipt_balances WHERE receipt_id=?',(receipt_id,)).fetchone() if receipt_id else None
            if balance:
                if quantity>balance['remaining_units']:raise RuleError('Insufficient remaining stock in the selected batch. Reload batches.')
                db.execute('UPDATE receipt_balances SET remaining_units=remaining_units-? WHERE receipt_id=?',(quantity,receipt_id))
            elif quantity>available['untracked_units']:
                raise RuleError('Insufficient untracked stock. Select the affected tracked batch instead.')
            db.execute('UPDATE medicines SET stock=? WHERE id=?',(after,medicine_id))
            loss_id=str(uuid4())
            db.execute('INSERT INTO stock_losses(id,medicine_id,quantity,kind,reason,stock_before,stock_after,actor_id,request_id,created_at,item_label,receipt_id,batch_number,expiry_date) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                       (loss_id,medicine_id,quantity,kind,reason,medicine['stock'],after,staff,request_id,datetime.now(timezone.utc).isoformat(),label,receipt_id,receipt['batch_number'] if receipt else None,receipt['expiry_date'] if receipt else None))
            return dict(db.execute('SELECT * FROM stock_losses WHERE id=?',(loss_id,)).fetchone())

    def assessment_metadata(self, row):
        metadata={key:row[key] for key in ('id','patient_id','width','height','created_at')}
        metadata['symptoms']=json.loads(row['symptoms_json']) if 'symptoms_json' in row.keys() and row['symptoms_json'] else None
        if 'prediction_json' in row.keys() and row['prediction_json']:
            return metadata | {'origin':'experimental_ai','example_category':None,
                'prediction':json.loads(row['prediction_json']),
                'message':'Experimental model suggestions only; may be wrong. Not a diagnosis. Ask a doctor to review.'}
        return metadata | {
            'origin': 'simulation', 'example_category': 'Acne (example only)',
            'message': 'No disease prediction was performed. Photo checks do not diagnose a condition.'}

    def assessment_review_summaries(self, db, assessment_ids, patient):
        if not assessment_ids:
            return {}
        placeholders=','.join('?' for _ in assessment_ids)
        rows=db.execute(f'''SELECT s.assessment_id,COUNT(r.id) AS published_reviews,
            SUM(CASE WHEN r.id IS NULL AND s.revoked_at IS NULL AND (s.booking_id IS NULL OR EXISTS (
                SELECT 1 FROM bookings b JOIN slots sl ON sl.id=b.slot_id
                WHERE b.id=s.booking_id AND b.patient_id=s.patient_id AND sl.doctor_id=s.doctor_id
                    AND b.status NOT IN ('cancelled','missed'))) THEN 1 ELSE 0 END) AS awaiting_reviews
            FROM assessment_shares s LEFT JOIN assessment_reviews r ON r.share_id=s.id
            WHERE s.patient_id=? AND s.assessment_id IN ({placeholders}) GROUP BY s.assessment_id''',(patient,*assessment_ids)).fetchall()
        return {row['assessment_id']:{'published_reviews':row['published_reviews'],'awaiting_reviews':row['awaiting_reviews']} for row in rows}

    def assessments(self, patient):
        return self.assessment_history(patient)['items']

    def assessment_history(self, patient, cursor=None):
        if not self.is_patient(patient):
            raise RuleError('Patient identity required.',403)
        with self.connect() as db:
            boundary=''
            args=(patient,)
            if cursor is not None:
                anchor=db.execute('SELECT created_at,id FROM assessments WHERE id=? AND patient_id=?',(cursor,patient)).fetchone()
                if not anchor:
                    raise RuleError('Invalid assessment cursor. Refresh history and try again.',422)
                boundary=' AND (created_at<? OR (created_at=? AND id<?))'
                args+=(anchor['created_at'],anchor['created_at'],anchor['id'])
            rows=db.execute(f'''SELECT id,patient_id,width,height,created_at,prediction_json,symptoms_json
                FROM assessments WHERE patient_id=?{boundary} ORDER BY created_at DESC,id DESC LIMIT 101''',args).fetchall()
            summaries=self.assessment_review_summaries(db,[row['id'] for row in rows[:100]],patient)
            return {'items':[self.assessment_metadata(row) | {'review_summary':summaries.get(row['id'],{'published_reviews':0,'awaiting_reviews':0})} for row in rows[:100]],
                    'next_cursor':rows[99]['id'] if len(rows)>100 else None}

    def assessment(self, assessment_id, patient):
        import base64
        with self.connect() as db:
            row = db.execute('SELECT * FROM assessments WHERE id=? AND patient_id=?', (assessment_id, patient)).fetchone()
            if row is None:
                raise RuleError('Assessment not found for this patient.', 404)
            summary=self.assessment_review_summaries(db,[assessment_id],patient).get(assessment_id,{'published_reviews':0,'awaiting_reviews':0})
            return self.assessment_metadata(row) | {'photo_uri': 'data:image/jpeg;base64,' + base64.b64encode(row['photo']).decode('ascii'),'review_summary':summary}

    def assessment_retry(self,patient,request_id,source_hash,symptoms=None):
        with self.connect() as db:
            existing=db.execute('SELECT id,source_hash,symptoms_json FROM assessments WHERE patient_id=? AND request_id=?',(patient,request_id)).fetchone()
            if existing is None:return None
            if existing['source_hash']!=source_hash:raise RuleError('This request already saved a different photo. Refresh history.')
            if (json.loads(existing['symptoms_json']) if existing['symptoms_json'] else None)!=symptoms:
                raise RuleError('This request already saved different symptom details. Refresh history before starting another assessment.')
        return self.assessment(existing['id'],patient)

    def save_assessment(self, patient, request_id, source_hash, photo, width, height, prediction=None,symptoms=None):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            existing = db.execute('SELECT id,source_hash,symptoms_json FROM assessments WHERE patient_id=? AND request_id=?', (patient, request_id)).fetchone()
            if existing:
                if existing['source_hash'] != source_hash:
                    raise RuleError('This request already saved a different photo. Refresh history.')
                if (json.loads(existing['symptoms_json']) if existing['symptoms_json'] else None)!=symptoms:
                    raise RuleError('This request already saved different symptom details. Refresh history before starting another assessment.')
                assessment_id = existing['id']
            else:
                assessment_id = str(uuid4())
                db.execute('INSERT INTO assessments(id,patient_id,request_id,source_hash,photo,width,height,created_at,prediction_json,symptoms_json) VALUES(?,?,?,?,?,?,?,?,?,?)',
                    (assessment_id,patient,request_id,source_hash,photo,width,height,datetime.now(timezone.utc).isoformat(),
                     json.dumps(prediction,allow_nan=False) if prediction is not None else None,
                     json.dumps(symptoms,allow_nan=False) if symptoms is not None else None))
        return self.assessment(assessment_id, patient)

    def share_record(self, db, share_id, actor):
        row = db.execute('SELECT * FROM assessment_shares WHERE id=?', (share_id,)).fetchone()
        if row is None or (self.is_patient(actor,db) and row['patient_id'] != actor) or (
            self.is_doctor(actor,db) and (row['doctor_id'] != actor or row['revoked_at'] is not None)) or (not self.is_patient(actor,db) and not self.is_doctor(actor,db)):
            raise RuleError('Shared assessment is unavailable for this identity.', 404)
        visit = self.record(db, row['booking_id']) if row['booking_id'] else None
        if self.is_doctor(actor,db) and visit and (visit['status'] in ('cancelled','missed') or visit['doctor_id'] != actor):
            raise RuleError('Appointment access is no longer available.', 404)
        review = db.execute('SELECT * FROM assessment_reviews WHERE share_id=?', (share_id,)).fetchone()
        return dict(row, patient_name=self.user_name(db,row['patient_id']), doctor_name=self.user_name(db,row['doctor_id']),
                    review=dict(review) if review else None, visit=visit)

    def assessment_sharing_history(self, assessment_id, patient):
        if not self.is_patient(patient):
            raise RuleError('Patient identity required.',403)
        with self.connect() as db:
            if not db.execute('SELECT 1 FROM assessments WHERE id=? AND patient_id=?',(assessment_id,patient)).fetchone():
                raise RuleError('Assessment not found for this patient.',404)
            rows=db.execute('''SELECT id FROM assessment_shares WHERE assessment_id=? AND patient_id=?
                ORDER BY created_at DESC,id DESC''',(assessment_id,patient)).fetchall()
            return [self.share_record(db,row['id'],patient) for row in rows]

    def shares(self, actor):
        with self.connect() as db:
            if self.is_patient(actor,db):
                rows = db.execute('SELECT id FROM assessment_shares WHERE patient_id=? ORDER BY created_at DESC LIMIT 100', (actor,))
            elif self.is_doctor(actor,db):
                rows = db.execute('''SELECT s.id FROM assessment_shares s LEFT JOIN bookings b ON b.id=s.booking_id
                    WHERE s.doctor_id=? AND s.revoked_at IS NULL AND (s.booking_id IS NULL OR b.status NOT IN ('cancelled','missed'))
                    ORDER BY s.created_at DESC LIMIT 100''', (actor,))
            else:
                raise RuleError('Patient or doctor identity required.', 403)
            return [self.share_record(db, row['id'], actor) for row in rows.fetchall()]

    def share_assessment(self, assessment_id, patient, doctor, message, request_id):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if not self.is_doctor(doctor,db):raise RuleError('Choose a recognised doctor.',422)
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

    def review_draft_record(self, db, share_id, doctor):
        if not self.is_doctor(doctor,db):
            raise RuleError('Doctor identity required.',403)
        share=self.share_record(db,share_id,doctor)
        if share['review']:
            raise RuleError('This review is already published. Draft editing is closed.')
        row=db.execute('SELECT * FROM assessment_review_drafts WHERE share_id=? AND doctor_id=?',(share_id,doctor)).fetchone()
        return dict(row) if row else {'share_id':share_id,'doctor_id':doctor,'doctor_assessment':'','note':'','follow_up':'','version':0,'updated_at':None}

    def review_draft(self, share_id, doctor):
        with self.connect() as db:
            db.execute('BEGIN')
            return self.review_draft_record(db,share_id,doctor)

    def save_review_draft(self, share_id, doctor, note, follow_up, version, doctor_assessment=''):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            current=self.review_draft_record(db,share_id,doctor)
            if (current['note'],current['follow_up'],current['doctor_assessment'])==(note,follow_up,doctor_assessment):
                return current
            if current['version']!=version:
                raise RuleError('This draft changed in another tab. Reload the saved draft before editing again.')
            db.execute('''INSERT INTO assessment_review_drafts(share_id,doctor_id,note,follow_up,version,updated_at,doctor_assessment) VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(share_id) DO UPDATE SET note=excluded.note,follow_up=excluded.follow_up,
                version=excluded.version,updated_at=excluded.updated_at,doctor_assessment=excluded.doctor_assessment''',
                (share_id,doctor,note,follow_up,version+1,datetime.now(timezone.utc).isoformat(),doctor_assessment))
            return self.review_draft_record(db,share_id,doctor)

    def publish_review(self, share_id, doctor, note, follow_up, draft_version=None, doctor_assessment=''):
        with self.connect() as db:
            # Serializes publication and revocation: a revoked share cannot accept a new review.
            db.execute('BEGIN IMMEDIATE')
            share = self.share_record(db, share_id, doctor)
            if share['review']:
                if (share['review']['note'],share['review']['follow_up'],share['review']['doctor_assessment']) != (note,follow_up,doctor_assessment):
                    raise RuleError('Review already published. Published reviews cannot be replaced.')
                return share
            if draft_version is not None:
                draft=self.review_draft_record(db,share_id,doctor)
                if draft['version']!=draft_version:
                    raise RuleError('This draft changed in another tab. Reload the saved draft before publishing.')
            db.execute('INSERT INTO assessment_reviews(id,share_id,doctor_id,note,follow_up,created_at,doctor_assessment) VALUES(?,?,?,?,?,?,?)',
                       (str(uuid4()),share_id,doctor,note,follow_up,datetime.now(timezone.utc).isoformat(),doctor_assessment))
            self.notify(db,share['patient_id'],'review_published',share_id,share['assessment_id'],'Doctor review is ready',
                        f"{self.user_name(db,doctor)} published a review. Open the assessment to read it.")
            db.execute('DELETE FROM assessment_review_drafts WHERE share_id=?',(share_id,))
            return self.share_record(db, share_id, doctor)

    def background_record(self, db, patient):
        row = db.execute('SELECT * FROM patient_backgrounds WHERE patient_id=?', (patient,)).fetchone()
        return dict(row) if row else {'patient_id':patient,'allergies':'','medicines':'','conditions':'','version':0,'updated_at':None}

    def background(self, patient):
        if not self.is_patient(patient):
            raise RuleError('Patient identity required.',403)
        with self.connect() as db:
            return self.background_record(db,patient)

    def save_background(self, patient, allergies, medicines, conditions, version):
        if not self.is_patient(patient):
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
        if (not self.is_patient(actor,db) and not self.is_doctor(actor,db)):
            raise RuleError('Patient or doctor identity required.', 403)
        visit = self.record(db, booking_id)
        if (self.is_patient(actor,db) and visit['patient_id'] != actor) or (self.is_doctor(actor,db) and visit['doctor_id'] != actor):
            raise RuleError('Consultation unavailable for this identity.', 404)
        note = db.execute('SELECT * FROM consultation_notes WHERE booking_id=?', (booking_id,)).fetchone()
        if (self.is_patient(actor,db) and not note) or (self.is_doctor(actor,db) and visit['status'] not in ('called','completed')):
            raise RuleError('Consultation not available yet.', 404)
        linked = None
        if self.is_doctor(actor,db):
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
            result['follow_up'] = self.follow_up_record(db,booking_id)
        return result

    def consultations(self, actor):
        if (not self.is_patient(actor) and not self.is_doctor(actor)):
            raise RuleError('Patient or doctor identity required.', 403)
        with self.connect() as db:
            if self.is_patient(actor,db):
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

    def follow_up_record(self, db, booking_id):
        row=db.execute('SELECT * FROM follow_up_recommendations WHERE source_booking_id=?',(booking_id,)).fetchone()
        if not row:
            return None
        latest=db.execute('''SELECT b.id FROM follow_up_bookings f JOIN bookings b ON b.id=f.booking_id
            WHERE f.source_booking_id=? ORDER BY CASE WHEN b.status NOT IN ('cancelled','missed') THEN 0 ELSE 1 END,
            b.created_at DESC,b.rowid DESC LIMIT 1''',(booking_id,)).fetchone()
        return dict(row,booked_visit=self.record(db,latest['id']) if latest else None)

    @staticmethod
    def validate_follow_up_slot(recommendation, slot):
        if slot['doctor_id']!=recommendation['doctor_id'] or slot['clinic_date']<recommendation['recommended_date']:
            raise RuleError('Choose the recommending doctor on or after the recommended follow-up date.')

    def recommend_follow_up(self, booking_id, doctor, recommended_date, reason):
        if not self.is_doctor(doctor):
            raise RuleError('Doctor identity required.',403)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            source=self.consultation_record(db,booking_id,doctor)['visit']
            existing=self.follow_up_record(db,booking_id)
            if existing:
                if (existing['recommended_date'],existing['reason'])!=(recommended_date,reason):
                    raise RuleError('A follow-up recommendation is already saved for this visit.')
                return existing
            today=datetime.now(timezone(timedelta(hours=8))).date()
            if date.fromisoformat(recommended_date)<=max(today,date.fromisoformat(source['clinic_date'])):
                raise RuleError('Choose a follow-up date after today and after this appointment date.',422)
            db.execute('INSERT INTO follow_up_recommendations VALUES(?,?,?,?,?)',
                       (booking_id,doctor,recommended_date,reason,datetime.now(timezone.utc).isoformat()))
            token=self.queue_token(db,source)
            visit_date=datetime.fromisoformat(source['starts_at']).astimezone(timezone(timedelta(hours=8)))
            earliest=date.fromisoformat(recommended_date)
            self.notify(db,source['patient_id'],'follow_up_recommended',booking_id,booking_id,'Follow-up visit recommended',
                        f"{self.user_name(db,doctor)} recommended a follow-up on or after {earliest:%d %b %Y} (Malaysia date) for {token}, your visit on {visit_date:%d %b %Y, %I:%M %p} (Malaysia time). Open the original visit to review the recommendation and latest booking status. No appointment is booked by this notification.")
            return self.follow_up_record(db,booking_id)

    def consultation_history(self, booking_id, doctor):
        if not self.is_doctor(doctor):
            raise RuleError('Doctor identity required.',403)
        with self.connect() as db:
            db.execute('BEGIN')
            current=self.consultation_record(db,booking_id,doctor)['visit']
            rows=db.execute('''SELECT b.id FROM bookings b JOIN slots s ON s.id=b.slot_id
                WHERE b.patient_id=? AND s.doctor_id=? AND b.status='completed' AND b.id!=?
                  AND julianday(s.starts_at)<julianday(?)
                ORDER BY julianday(s.starts_at) DESC,b.id DESC LIMIT 50''',
                (current['patient_id'],doctor,booking_id,current['starts_at'])).fetchall()
            items=[]
            for row in rows:
                note=db.execute('SELECT * FROM consultation_notes WHERE booking_id=?',(row['id'],)).fetchone()
                prescription=self.prescription(db,row['id'])
                if prescription:
                    # Clinical history does not need catalogue prices or billing data.
                    prescription={key:prescription[key] for key in ('id','booking_id','doctor_id','status','created_at','dispensed_at')} | {
                        'items':[{key:item[key] for key in ('medicine_id','name','strength','form','quantity','directions')} for item in prescription['items']]}
                items.append({'visit':self.record(db,row['id']),'note':dict(note) if note else None,'prescription':prescription})
            return {'current_visit_id':booking_id,'items':items,'limit':50}

    def consultation_draft_record(self, db, booking_id, doctor):
        if not self.is_doctor(doctor,db):
            raise RuleError('Doctor identity required.',403)
        record=self.consultation_record(db,booking_id,doctor)
        if record['note']:
            raise RuleError('This consultation is already published. Draft editing is closed.')
        row=db.execute('SELECT * FROM consultation_drafts WHERE booking_id=? AND doctor_id=?',(booking_id,doctor)).fetchone()
        return dict(row) if row else {'booking_id':booking_id,'doctor_id':doctor,'findings':'','follow_up':'','version':0,'updated_at':None}

    def consultation_draft(self, booking_id, doctor):
        with self.connect() as db:
            db.execute('BEGIN')
            return self.consultation_draft_record(db,booking_id,doctor)

    def save_consultation_draft(self, booking_id, doctor, findings, follow_up, version):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            current=self.consultation_draft_record(db,booking_id,doctor)
            if self.record(db,booking_id)['status']!='called':
                raise RuleError('This visit is completed. Its private draft is read-only.')
            if (current['findings'],current['follow_up'])==(findings,follow_up):
                return current
            if current['version']!=version:
                raise RuleError('This draft changed in another tab. Reload the saved draft before editing again.')
            db.execute('''INSERT INTO consultation_drafts(booking_id,doctor_id,findings,follow_up,version,updated_at) VALUES(?,?,?,?,?,?)
                ON CONFLICT(booking_id) DO UPDATE SET findings=excluded.findings,follow_up=excluded.follow_up,
                version=excluded.version,updated_at=excluded.updated_at''',
                (booking_id,doctor,findings,follow_up,version+1,datetime.now(timezone.utc).isoformat()))
            return self.consultation_draft_record(db,booking_id,doctor)

    def publish_consultation(self, booking_id, doctor, findings, follow_up, draft_version=None):
        if not self.is_doctor(doctor):
            raise RuleError('Doctor identity required.',403)
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
            draft=self.consultation_draft_record(db,booking_id,doctor)
            if (draft_version is not None and draft_version!=draft['version']) or (draft_version is None and draft['version']>0):
                raise RuleError('The private draft changed. Reload the saved draft and confirm publication again.')
            db.execute('INSERT INTO consultation_notes VALUES(?,?,?,?,?,?)',
                       (str(uuid4()),booking_id,doctor,findings,follow_up,datetime.now(timezone.utc).isoformat()))
            self.event(db,booking_id,doctor,'consultation-published')
            db.execute('DELETE FROM consultation_drafts WHERE booking_id=?',(booking_id,))
            return self.consultation_record(db,booking_id,doctor)

    def prescription(self, db, booking_id):
        # One statement keeps the reviewed revision and its directions in the same read snapshot.
        rows=db.execute('''SELECT p.*,i.medicine_id,i.quantity,i.directions,i.name,i.price_cents,i.strength,i.form,
            COALESCE(r.version,1) AS version,r.created_at AS directions_updated_at,
            c.created_at AS cancelled_at FROM prescriptions p
            LEFT JOIN prescription_items i ON i.prescription_id=p.id
            LEFT JOIN prescription_direction_revisions r ON r.prescription_id=p.id
              AND r.version=(SELECT MAX(version) FROM prescription_direction_revisions WHERE prescription_id=p.id)
            LEFT JOIN prescription_cancellations c ON c.prescription_id=p.id
            WHERE p.booking_id=? ORDER BY i.medicine_id''',(booking_id,)).fetchall()
        if not rows:
            return None
        header=('id','booking_id','doctor_id','status','created_at','dispensed_at','version','directions_updated_at','cancelled_at')
        fields=('medicine_id','quantity','directions','name','price_cents','strength','form')
        return {key:rows[0][key] for key in header} | {'status':'cancelled' if rows[0]['cancelled_at'] else rows[0]['status'],'items':[
            {key:row[key] for key in fields} for row in rows if row['medicine_id'] is not None]}

    def prescription_directions_history(self, booking_id, doctor):
        if not self.is_doctor(doctor):raise RuleError('Doctor identity required.',403)
        with self.connect() as db:
            db.execute('BEGIN')
            visit=self.record(db,booking_id)
            if visit['doctor_id']!=doctor:raise RuleError('This visit belongs to another doctor.',403)
            prescription=self.prescription(db,booking_id)
            if not prescription:raise RuleError('Prescription not found.',404)
            rows=db.execute('SELECT * FROM prescription_direction_revisions WHERE prescription_id=? ORDER BY version DESC',(prescription['id'],)).fetchall()
            return {'prescription_id':prescription['id'],'version':prescription['version'],'revisions':[
                {key:row[key] for key in ('id','version','doctor_id','reason','created_at')} |
                {'doctor_name':self.user_name(db,row['doctor_id']),'previous_directions':json.loads(row['previous_directions_json']),
                 'directions':json.loads(row['directions_json'])} for row in rows]}

    def correct_prescription_directions(self, booking_id, doctor, version, reason, items):
        if not self.is_doctor(doctor):raise RuleError('Doctor identity required.',403)
        reason=reason.strip()
        directions=sorted([{'medicine_id':item['medicine_id'],'directions':item['directions'].strip()} for item in items],key=lambda item:item['medicine_id'])
        if not 1<=len(reason)<=300 or not directions or any(not 1<=len(item['directions'])<=300 for item in directions):
            raise RuleError('Enter a correction reason and nonblank directions within 300 characters.',422)
        if len({item['medicine_id'] for item in directions})!=len(directions):raise RuleError('Choose each prescription item only once.',422)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            visit=self.record(db,booking_id)
            if visit['doctor_id']!=doctor:raise RuleError('This visit belongs to another doctor.',403)
            prescription=self.prescription(db,booking_id)
            if not prescription:raise RuleError('Prescription not found.',404)
            latest=db.execute('SELECT * FROM prescription_direction_revisions WHERE prescription_id=? ORDER BY version DESC LIMIT 1',(prescription['id'],)).fetchone()
            if latest and version==prescription['version']-1 and latest['reason']==reason and json.loads(latest['directions_json'])==directions:
                return prescription
            if version!=prescription['version']:raise RuleError('Prescription directions changed. Reload and review the latest revision.')
            if visit['status']!='called' or visit['consultation_finished_at']:
                raise RuleError('Correct directions only while the consultation is open, before doctor handover.')
            if prescription['status']!='issued' or self.invoice(db,booking_id):
                raise RuleError('Directions cannot be corrected after dispensing or bill generation.')
            previous=[{'medicine_id':item['medicine_id'],'directions':item['directions']} for item in prescription['items']]
            if [item['medicine_id'] for item in previous]!=[item['medicine_id'] for item in directions]:
                raise RuleError('Correct directions for the existing items only. Medicines and quantities cannot be changed.',422)
            if previous==directions:raise RuleError('Change at least one direction before confirming.')
            db.execute('INSERT INTO prescription_direction_revisions VALUES(?,?,?,?,?,?,?,?)',
                (str(uuid4()),prescription['id'],version+1,doctor,reason,json.dumps(previous),json.dumps(directions),datetime.now(timezone.utc).isoformat()))
            db.executemany('UPDATE prescription_items SET directions=? WHERE prescription_id=? AND medicine_id=?',
                [(item['directions'],prescription['id'],item['medicine_id']) for item in directions])
            self.event(db,booking_id,doctor,'prescription-directions-corrected')
            return self.prescription(db,booking_id)

    def prescription_cancellation(self, booking_id, doctor):
        if not self.is_doctor(doctor):raise RuleError('Doctor identity required.',403)
        with self.connect() as db:
            visit=self.record(db,booking_id)
            if visit['doctor_id']!=doctor:raise RuleError('This visit belongs to another doctor.',403)
            prescription=self.prescription(db,booking_id)
            if not prescription:raise RuleError('Prescription not found.',404)
            row=db.execute('SELECT * FROM prescription_cancellations WHERE prescription_id=?',(prescription['id'],)).fetchone()
            return dict(row) if row else None

    def cancel_prescription(self, booking_id, doctor, version, reason):
        if not self.is_doctor(doctor):raise RuleError('Doctor identity required.',403)
        reason=reason.strip()
        if type(version) is not int or version<1 or not 1<=len(reason)<=300:
            raise RuleError('Enter a cancellation reason within 300 characters and the reviewed revision.',422)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            visit=self.record(db,booking_id)
            if visit['doctor_id']!=doctor:raise RuleError('This visit belongs to another doctor.',403)
            prescription=self.prescription(db,booking_id)
            if not prescription:raise RuleError('Prescription not found.',404)
            saved=db.execute('SELECT * FROM prescription_cancellations WHERE prescription_id=?',(prescription['id'],)).fetchone()
            if saved:
                if saved['reason']==reason and saved['version']==version:return prescription
                raise RuleError('This prescription is already cancelled. Its saved cancellation cannot be replaced.')
            if version!=prescription['version']:raise RuleError('Prescription directions changed. Reload and review the latest revision.')
            if visit['status']!='called' or visit['consultation_finished_at']:
                raise RuleError('Cancel only while the consultation is open, before doctor handover.')
            if prescription['status']!='issued' or self.invoice(db,booking_id):
                raise RuleError('A prescription cannot be cancelled after dispensing or bill generation.')
            db.execute('INSERT INTO prescription_cancellations VALUES(?,?,?,?,?)',
                (prescription['id'],doctor,reason,version,datetime.now(timezone.utc).isoformat()))
            self.event(db,booking_id,doctor,'prescription-cancelled')
            token=self.queue_token(db,visit)
            local_start=datetime.fromisoformat(visit['starts_at']).astimezone(timezone(timedelta(hours=8)))
            self.notify(db,visit['patient_id'],'prescription_cancelled',prescription['id'],booking_id,'Prescription cancelled',
                        f"The prescription for {token} with {visit['doctor_name']} on {local_start:%d %b %Y, %I:%M %p} (Malaysia time) was cancelled. Open Care & bills to check its latest status. Cancelled items are retained for history and are not an active prescription.")
            return self.prescription(db,booking_id)

    def invoice(self, db, booking_id):
        row = db.execute('SELECT * FROM invoices WHERE booking_id=?', (booking_id,)).fetchone()
        if not row:
            return None
        lines = db.execute('SELECT description,quantity,unit_price_cents FROM invoice_lines WHERE invoice_id=? ORDER BY rowid', (row['id'],)).fetchall()
        return dict(row, lines=[dict(line) for line in lines])

    def care(self, actor):
        if (not self.is_patient(actor) and not self.is_doctor(actor) and actor!='staff-demo'):raise RuleError('Patient, assigned doctor or staff identity required.',403)
        with self.connect() as db:
            records = []
            for row in db.execute('SELECT id FROM bookings ORDER BY created_at DESC').fetchall():
                visit = self.record(db, row['id'])
                if self.is_patient(actor,db) and visit['patient_id'] != actor:
                    continue
                if self.is_doctor(actor,db) and visit['doctor_id'] != actor:
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
            if visit['consultation_finished_at']:
                raise RuleError('The consultation is finished. A new prescription cannot be added after handover.')
            if self.invoice(db, booking_id):
                raise RuleError('This visit has been billed. A prescription cannot be added afterwards.')
            for item in normalised:
                medicine=db.execute('SELECT active FROM medicines WHERE id=?', (item['medicine_id'],)).fetchone()
                if medicine is None:
                    raise RuleError('Unknown demo item.', 422)
                if not medicine['active']:
                    raise RuleError('This medicine is inactive. Reload the catalogue and review the prescription.')
            prescription_id = str(uuid4())
            db.execute('INSERT INTO prescriptions VALUES(?,?,?,?,?,NULL)',
                       (prescription_id, booking_id, doctor, 'issued', datetime.now(timezone.utc).isoformat()))
            for item in normalised:
                medicine = db.execute('SELECT * FROM medicines WHERE id=?',(item['medicine_id'],)).fetchone()
                db.execute('INSERT INTO prescription_items(prescription_id,medicine_id,quantity,directions,name,price_cents,strength,form) VALUES(?,?,?,?,?,?,?,?)',
                           (prescription_id,item['medicine_id'],item['quantity'],item['directions'],medicine['name'],medicine['price_cents'],medicine['strength'],medicine['form']))
            self.event(db, booking_id, doctor, 'prescription-issued')
            token=self.queue_token(db,visit)
            local_start=datetime.fromisoformat(visit['starts_at']).astimezone(timezone(timedelta(hours=8)))
            self.notify(db,visit['patient_id'],'prescription_issued',prescription_id,booking_id,'Prescription issued',
                        f"A prescription was issued for {token} with {visit['doctor_name']} on {local_start:%d %b %Y, %I:%M %p} (Malaysia time). Open Care & bills to view the saved medicines, directions and latest dispensing status.")
            return self.prescription(db, booking_id)

    def dispensing_stock(self, prescription_id):
        from .batch_inventory import sources,saved_allocations
        with self.connect() as db:
            db.execute('BEGIN')
            row=db.execute('SELECT booking_id FROM prescriptions WHERE id=?',(prescription_id,)).fetchone()
            if not row:raise RuleError('Prescription not found.',404)
            prescription=self.prescription(db,row['booking_id'])
            return {'prescription_version':prescription['version'],'items':[sources(db,item['medicine_id']) for item in prescription['items']],
                    'allocations':saved_allocations(db,prescription_id),'status':prescription['status']}

    def dispense(self, prescription_id, staff, allocations=None, prescription_version=None):
        if staff!='staff-demo':raise RuleError('Staff demo identity required.',403)
        from .batch_inventory import allocate,saved_allocations
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT booking_id FROM prescriptions WHERE id=?', (prescription_id,)).fetchone()
            if not row:
                raise RuleError('Prescription not found.', 404)
            prescription = self.prescription(db, row['booking_id'])
            if (prescription_version is not None and prescription_version!=prescription['version']) or (prescription_version is None and prescription['version']>1):
                raise RuleError('Prescription directions changed. Reload and review the latest revision before dispensing.')
            if prescription['status'] == 'dispensed':
                if allocations is not None:
                    original=saved_allocations(db,prescription_id)
                    wanted=sorted((part['medicine_id'],part['receipt_id'] or '',part['quantity']) for part in allocations)
                    saved=sorted((part['medicine_id'],part['receipt_id'] or '',part['quantity']) for part in original)
                    if wanted!=saved:raise RuleError('This prescription was already dispensed with different stock sources. Check saved allocations.')
                return prescription
            if prescription['status']=='cancelled':raise RuleError('This prescription is cancelled. Nothing was dispensed.')
            allocate(db,prescription,allocations,staff,RuleError)
            for item in prescription['items']:
                result = db.execute('UPDATE medicines SET stock=stock-? WHERE id=? AND stock>=?',
                                    (item['quantity'], item['medicine_id'], item['quantity']))
                if result.rowcount != 1:
                    raise RuleError('Insufficient demo stock. Nothing was dispensed.')
            db.execute("UPDATE prescriptions SET status='dispensed',dispensed_at=? WHERE id=?",
                       (datetime.now(timezone.utc).isoformat(), prescription_id))
            self.event(db, row['booking_id'], staff, 'prescription-dispensed')
            return self.prescription(db, row['booking_id'])

    def generate_invoice(self, booking_id, staff, reviewed=None):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            visit = self.record(db, booking_id)
            if visit['status'] != 'completed':
                raise RuleError('Complete the visit before generating a bill.')
            prescription = self.prescription(db, booking_id)
            active_prescription=prescription if prescription and prescription['status']!='cancelled' else None
            if reviewed is not None and reviewed['prescription_id']!=(active_prescription['id'] if active_prescription else None):
                raise RuleError('The prescription changed since review. Cancel and review the bill again. No new bill was created.')
            existing = self.invoice(db, booking_id)
            if existing:
                return existing
            lines = [('Demo consultation', 1, 3000)]
            if active_prescription:
                lines.extend((' · '.join(v for v in (i['name'],i['strength'],i['form']) if v), i['quantity'], i['price_cents']) for i in active_prescription['items'])
            invoice_id = str(uuid4())
            total = sum(quantity * price for _, quantity, price in lines)
            db.execute('INSERT INTO invoices VALUES(?,?,?,?,?,NULL,NULL)',
                       (invoice_id, booking_id, total, 'unpaid', datetime.now(timezone.utc).isoformat()))
            db.executemany('INSERT INTO invoice_lines VALUES(?,?,?,?,?)',
                [(str(uuid4()), invoice_id, name, quantity, price) for name, quantity, price in lines])
            self.event(db, booking_id, staff, 'invoice-generated')
            token=self.queue_token(db,visit)
            local_start=datetime.fromisoformat(visit['starts_at']).astimezone(timezone(timedelta(hours=8)))
            self.notify(db,visit['patient_id'],'bill_ready',invoice_id,booking_id,'Bill ready',
                        f"{token} with {visit['doctor_name']} on {local_start:%d %b %Y, %I:%M %p} (Malaysia time). A simulated bill of RM {total//100}.{total%100:02d} was generated. Open Care & bills to check the latest bill and payment status.")
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
            if prescription and prescription['status'] == 'issued':
                raise RuleError('Dispense the prescription before recording simulated payment.')
            db.execute("UPDATE invoices SET status='paid',paid_at=?,payment_mode='simulation' WHERE id=?",
                       (datetime.now(timezone.utc).isoformat(), invoice_id))
            self.event(db, row['booking_id'], actor, 'payment-simulated')
            token=self.queue_token(db,visit)
            local_start=datetime.fromisoformat(visit['starts_at']).astimezone(timezone(timedelta(hours=8)))
            total=invoice['total_cents']
            self.notify(db,visit['patient_id'],'payment_recorded',invoice_id,row['booking_id'],'Payment recorded · simulation',
                        f"A simulated payment of RM {total//100}.{total%100:02d} was recorded for {token} with {visit['doctor_name']} on {local_start:%d %b %Y, %I:%M %p} (Malaysia time). Receipt {invoice_id[:8]}. Open Care & bills to view the paid bill and receipt details. No money was transferred.")
            return self.invoice(db, row['booking_id'])
