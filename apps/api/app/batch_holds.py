"""Staff batch hold transitions; caller supplies an immediate transaction."""
import json
from datetime import datetime,timezone


def change(db,medicine_id,receipt_id,held,reason,version,request_id,staff,error):
    if not db.execute("SELECT 1 FROM user_profiles WHERE id=? AND role='staff'",(staff,)).fetchone():raise error('Staff demo identity required.',403)
    if type(held) is not bool or type(version) is not int or version<0 or not isinstance(reason,str) or not reason.strip() or len(reason)>300:
        raise error('Choose a hold state, current version and reason up to 300 characters.',422)
    reason=reason.strip()
    retry=db.execute('SELECT * FROM batch_hold_changes WHERE request_id=?',(request_id,)).fetchone()
    if retry:
        if (retry['medicine_id'],retry['receipt_id'],bool(retry['held']),retry['reason'],retry['from_version'])!=(medicine_id,receipt_id,held,reason,version):
            raise error('This request already saved a different batch hold change.')
        return json.loads(retry['result_json'])
    row=db.execute('''SELECT b.* FROM receipt_balances b JOIN stock_receipts r ON r.id=b.receipt_id
        WHERE b.receipt_id=? AND r.medicine_id=?''',(receipt_id,medicine_id)).fetchone()
    if row is None:raise error('Tracked receipt batch not found for this medicine.',404)
    if row['hold_version']!=version:raise error('Batch hold changed. Reload the latest batch before trying again.')
    if bool(row['held'])==held:raise error('This batch already has that hold state. Reload the batch.',422)
    now=datetime.now(timezone.utc).isoformat()
    result={'receipt_id':receipt_id,'held':held,'hold_reason':reason if held else None,'hold_version':version+1,'hold_updated_at':now}
    db.execute('UPDATE receipt_balances SET held=?,hold_reason=?,hold_version=hold_version+1,hold_updated_at=? WHERE receipt_id=?',
        (int(held),result['hold_reason'],now,receipt_id))
    db.execute('INSERT INTO batch_hold_changes VALUES(?,?,?,?,?,?,?,?,?)',
        (request_id,medicine_id,receipt_id,version,int(held),reason,staff,now,json.dumps(result)))
    return result
