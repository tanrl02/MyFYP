"""Read-only, receipt-specific movement history; no patient information."""
def history(db,medicine_id,receipt_id,error):
    receipt=db.execute('''SELECT r.*,b.remaining_units FROM stock_receipts r
        JOIN receipt_balances b ON b.receipt_id=r.id WHERE r.id=? AND r.medicine_id=?''',(receipt_id,medicine_id)).fetchone()
    if receipt is None:raise error('Tracked receipt batch not found for this medicine.',404)
    totals={'received':receipt['quantity'],'dispensed':0,'damaged':0,'lost':0}
    movements=[{'id':receipt['id'],'kind':'received','quantity':receipt['quantity'],'change':receipt['quantity'],
        'created_at':receipt['created_at'],'actor_id':receipt['actor_id'],'reason':receipt['reason'],'balance_after':receipt['quantity']}]
    balance=receipt['quantity']
    for row in db.execute('''WITH deductions AS (
        SELECT id,'dispensed' AS kind,quantity,created_at,actor_id,NULL AS reason FROM dispensing_allocations WHERE receipt_id=?
        UNION ALL SELECT id,kind,quantity,created_at,actor_id,reason FROM stock_losses WHERE receipt_id=?)
        SELECT * FROM deductions ORDER BY julianday(created_at),kind,id''',(receipt_id,receipt_id)):
        totals[row['kind']]+=row['quantity'];balance-=row['quantity']
        movements.append({**dict(row),'change':-row['quantity'],'balance_after':balance})
    return {'medicine_id':medicine_id,'receipt_id':receipt_id,'batch_number':receipt['batch_number'],
        'expiry_date':receipt['expiry_date'],'remaining_units':receipt['remaining_units'],'totals':totals,
        'calculated_remaining':balance,'reconciled':balance==receipt['remaining_units'],'movements':movements}
