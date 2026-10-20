"""Transactional SQLite upgrade retaining booking IDs and dependent records."""

def allow_missed_bookings(db):
    schema=db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='bookings'").fetchone()['sql']
    if "'missed'" in schema:
        return
    # SQLite cannot widen a CHECK constraint in place. Rebuild only its parent
    # table, without renaming the old table (which would retarget foreign keys).
    objects=[row['sql'] for row in db.execute("SELECT sql FROM sqlite_master WHERE tbl_name='bookings' AND type IN ('index','trigger') AND sql IS NOT NULL")]
    db.execute('PRAGMA foreign_keys=OFF')
    try:
        db.execute('BEGIN IMMEDIATE')
        db.execute("""CREATE TABLE bookings_with_missed (
            id TEXT PRIMARY KEY, patient_id TEXT NOT NULL, slot_id TEXT NOT NULL REFERENCES slots(id),
            queue_number INTEGER NOT NULL, status TEXT NOT NULL CHECK(status IN ('waiting','called','completed','cancelled','missed')),
            created_at TEXT NOT NULL, request_id TEXT NOT NULL, UNIQUE(patient_id,request_id))""")
        db.execute('INSERT INTO bookings_with_missed SELECT * FROM bookings')
        db.execute('DROP TABLE bookings')
        db.execute('ALTER TABLE bookings_with_missed RENAME TO bookings')
        for sql in objects:
            db.execute(sql)
        if db.execute('PRAGMA foreign_key_check').fetchone():
            raise RuntimeError('Booking migration failed foreign-key validation.')
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.execute('PRAGMA foreign_keys=ON')
