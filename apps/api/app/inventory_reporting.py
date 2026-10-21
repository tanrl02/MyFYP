"""Read-only inventory activity and a separately labelled current stock snapshot."""
from datetime import date,datetime,timedelta,timezone
from .visit_reporting import shift_month

KINDS=('received','dispensed','damaged','lost')

def summary(db,period,year,month,quarter):
    count={'month':1,'quarter':3,'year':12}[period]
    first=month if period=='month' else (quarter-1)*3+1 if period=='quarter' else 1
    start=date(year,first,1);stop=shift_month(start,count)
    buckets={}
    for offset in range((stop-start).days if period=='month' else count):
        begin=start+timedelta(days=offset) if period=='month' else shift_month(start,offset)
        end=begin if period=='month' else shift_month(begin,1)-timedelta(days=1)
        key=begin.isoformat() if period=='month' else begin.isoformat()[:7]
        buckets[key]={'start_date':begin.isoformat(),'end_date':end.isoformat(),'units':dict.fromkeys((*KINDS,'net_change'),0)}
    totals=dict.fromkeys((*KINDS,'net_change'),0)
    dispensed={}
    for row in db.execute('''WITH movements AS (
            SELECT medicine_id,'received' AS kind,quantity,created_at FROM stock_receipts
            UNION ALL SELECT i.medicine_id,'dispensed',i.quantity,p.dispensed_at
                FROM prescription_items i JOIN prescriptions p ON p.id=i.prescription_id WHERE p.status='dispensed'
            UNION ALL SELECT medicine_id,kind,quantity,created_at FROM stock_losses)
        SELECT date(created_at,'+8 hours') AS day,medicine_id,kind,SUM(quantity) AS quantity FROM movements
        WHERE date(created_at,'+8 hours')>=? AND date(created_at,'+8 hours')<?
        GROUP BY day,medicine_id,kind''',(start.isoformat(),stop.isoformat())):
        key=row['day'] if period=='month' else row['day'][:7]
        buckets[key]['units'][row['kind']]+=row['quantity']
        totals[row['kind']]+=row['quantity']
        if row['kind']=='dispensed':dispensed[row['medicine_id']]=dispensed.get(row['medicine_id'],0)+row['quantity']
    for counts in [totals,*[bucket['units'] for bucket in buckets.values()]]:
        counts['net_change']=counts['received']-counts['dispensed']-counts['damaged']-counts['lost']
    medicines=[dict(row) for row in db.execute('SELECT id,name,strength,form,stock,active,low_stock_threshold FROM medicines')]
    active=[item for item in medicines if item['active']]
    alerts=sorted([item for item in active if item['stock']<=item['low_stock_threshold']],key=lambda item:(item['stock'],item['name'].casefold(),item['id']))
    top=sorted([dict(medicine_id=item['id'],name=item['name'],strength=item['strength'],form=item['form'],active=bool(item['active']),units=dispensed[item['id']])
        for item in medicines if item['id'] in dispensed],key=lambda item:(-item['units'],item['name'].casefold(),item['medicine_id']))[:5]
    return {'period':period,'start_date':start.isoformat(),'end_date':(stop-timedelta(days=1)).isoformat(),
        'timezone':'Asia/Kuala_Lumpur','generated_at':datetime.now(timezone.utc).isoformat(),
        'granularity':'day' if period=='month' else 'month','units':totals,'buckets':list(buckets.values()),'top_dispensed':top,
        'current_stock':{'active_items':len(active),'inactive_items':len(medicines)-len(active),
            'active_units':sum(item['stock'] for item in active),'low_stock_items':sum(0<item['stock']<=item['low_stock_threshold'] for item in active),
            # Retained for older clients as the default only, not a report-wide alert level.
            'out_of_stock_items':sum(item['stock']==0 for item in active),'low_stock_threshold':5,
            'alerts':[{'medicine_id':item['id'],'name':item['name'],'strength':item['strength'],'form':item['form'],'stock':item['stock'],'low_stock_threshold':item['low_stock_threshold']} for item in alerts]}}
