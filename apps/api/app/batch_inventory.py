"""Balances start with new receipts only; historical stock remains untracked."""
from datetime import datetime
from uuid import uuid4
from .scheduling import MALAYSIA


def sources(db,medicine_id):
    row=db.execute('SELECT stock FROM medicines WHERE id=?',(medicine_id,)).fetchone()
    if row is None:return None
    batches=[dict(r) for r in db.execute('''SELECT r.id AS receipt_id,r.batch_number,r.expiry_date,b.remaining_units,b.held,b.hold_reason,b.hold_version,b.hold_updated_at
        FROM receipt_balances b JOIN stock_receipts r ON r.id=b.receipt_id
        WHERE r.medicine_id=? ORDER BY r.expiry_date,r.created_at,r.id''',(medicine_id,))]
    today=datetime.now(MALAYSIA).date().isoformat()
    for batch in batches:
        batch['expired']=batch['expiry_date']<today
        batch['held']=bool(batch['held'])
    return {'medicine_id':medicine_id,'stock':row['stock'],'untracked_units':max(0,row['stock']-sum(b['remaining_units'] for b in batches)),
            'batches':batches}


def saved_allocations(db,prescription_id):
    return [dict(row) for row in db.execute('''SELECT medicine_id,receipt_id,batch_number,expiry_date,quantity,actor_id,created_at
        FROM dispensing_allocations WHERE prescription_id=? ORDER BY medicine_id,COALESCE(receipt_id,'')''',(prescription_id,))]


def allocate(db,prescription,allocations,staff,error):
    required={item['medicine_id']:item['quantity'] for item in prescription['items']}
    if allocations is None:allocations=[{'medicine_id':key,'quantity':quantity,'receipt_id':None} for key,quantity in required.items()]
    if not isinstance(allocations,list) or not 1<=len(allocations)<=100:raise error('Choose stock sources for every prescribed item.',422)
    totals={key:0 for key in required};seen=set()
    for part in allocations:
        if not isinstance(part,dict) or set(part)!={'medicine_id','quantity','receipt_id'}:raise error('Invalid dispensing allocation.',422)
        key=part['medicine_id'];receipt=part['receipt_id'];quantity=part['quantity']
        if not isinstance(key,str) or key not in required or type(quantity) is not int or quantity<1 or quantity>20 or (receipt is not None and (not isinstance(receipt,str) or not receipt)):
            raise error('Choose valid whole quantities and sources for the prescription.',422)
        if (key,receipt) in seen:raise error('Each stock source can appear only once per item.',422)
        seen.add((key,receipt));totals[key]+=quantity
    if totals!=required:raise error('Allocated quantities must match every prescribed quantity exactly.',422)
    # Validate all sources before writing. BEGIN IMMEDIATE is held by Store.dispense.
    checked=[]
    for part in allocations:
        available=sources(db,part['medicine_id']);receipt=part['receipt_id'];quantity=part['quantity']
        if available is None or available['stock']<required[part['medicine_id']]:raise error('Insufficient demo stock. Nothing was dispensed.')
        batch=None
        if receipt is None:
            if quantity>available['untracked_units']:raise error('Insufficient untracked stock. Choose recorded batches. Nothing was dispensed.')
        else:
            batch=next((b for b in available['batches'] if b['receipt_id']==receipt),None)
            if batch is None:raise error('Recorded batch is unavailable for this medicine. Reload stock sources.')
            if batch['held']:raise error('This batch is on hold and cannot be dispensed. Choose another stock source.')
            if batch['expired']:raise error('Expired batches cannot be dispensed. Choose another stock source.')
            if quantity>batch['remaining_units']:raise error('Insufficient stock in the selected batch. Reload stock sources.')
        checked.append((part,batch))
    now=datetime.now(MALAYSIA).isoformat()
    for part,batch in checked:
        if batch:db.execute('UPDATE receipt_balances SET remaining_units=remaining_units-? WHERE receipt_id=?',(part['quantity'],part['receipt_id']))
        db.execute('INSERT INTO dispensing_allocations VALUES(?,?,?,?,?,?,?,?,?)',
            (str(uuid4()),prescription['id'],part['medicine_id'],part['receipt_id'],part['quantity'],batch['batch_number'] if batch else None,batch['expiry_date'] if batch else None,staff,now))
