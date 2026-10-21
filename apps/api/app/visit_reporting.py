"""Read-only calendar-period aggregates for the staff visit summary."""
from datetime import date,datetime,timedelta,timezone

STATES=('waiting','called','completed','cancelled','missed','rescheduled','total')

def shift_month(start,offset):
    index=start.year*12+start.month-1+offset
    return date(index//12,index%12+1,1)

def summary(db,period,year,month,quarter):
    # Validated by the route before entering the store transaction.
    count={'month':1,'quarter':3,'year':12}[period]
    first=month if period=='month' else (quarter-1)*3+1 if period=='quarter' else 1
    start=date(year,first,1)
    stop=shift_month(start,count)
    previous_start=shift_month(start,-count)
    buckets={}
    if period=='month':
        for offset in range((stop-start).days):
            day=(start+timedelta(days=offset)).isoformat()
            buckets[day]={'start_date':day,'end_date':day,'visits':dict.fromkeys(STATES,0)}
    else:
        for offset in range(count):
            begin=shift_month(start,offset)
            buckets[begin.isoformat()[:7]]={'start_date':begin.isoformat(),
                'end_date':(shift_month(begin,1)-timedelta(days=1)).isoformat(),'visits':dict.fromkeys(STATES,0)}
    totals=dict.fromkeys(STATES,0)
    previous=dict.fromkeys(STATES,0)
    for row in db.execute('''SELECT s.clinic_date,
            CASE WHEN EXISTS(SELECT 1 FROM reschedules r WHERE r.old_booking_id=b.id)
            THEN 'rescheduled' ELSE b.status END AS state,COUNT(*) AS total
        FROM bookings b JOIN slots s ON s.id=b.slot_id
        WHERE s.clinic_date>=? AND s.clinic_date<? GROUP BY s.clinic_date,state''',
        (previous_start.isoformat(),stop.isoformat())):
        current=row['clinic_date']>=start.isoformat()
        target=totals if current else previous
        target[row['state']]+=row['total'];target['total']+=row['total']
        if current:
            key=row['clinic_date'] if period=='month' else row['clinic_date'][:7]
            counts=buckets[key]['visits']
            counts[row['state']]+=row['total'];counts['total']+=row['total']
    return {'period':period,'start_date':start.isoformat(),'end_date':(stop-timedelta(days=1)).isoformat(),
        'timezone':'Asia/Kuala_Lumpur','generated_at':datetime.now(timezone.utc).isoformat(),
        'granularity':'day' if period=='month' else 'month','visits':totals,'buckets':list(buckets.values()),
        'previous':{'start_date':previous_start.isoformat(),'end_date':(start-timedelta(days=1)).isoformat(),'visits':previous}}
