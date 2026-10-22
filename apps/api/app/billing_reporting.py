"""Invoice issue-date cohorts with their current simulated payment status."""
from datetime import date, datetime, timedelta, timezone
from .visit_reporting import shift_month

FIELDS = ('invoice_count', 'paid_invoice_count', 'unpaid_invoice_count',
          'billed_cents', 'paid_cents', 'unpaid_cents')


def summary(db, period, year, month, quarter):
    count = {'month': 1, 'quarter': 3, 'year': 12}[period]
    first = month if period == 'month' else (quarter - 1) * 3 + 1 if period == 'quarter' else 1
    start = date(year, first, 1)
    stop = shift_month(start, count)
    buckets = {}
    for offset in range((stop - start).days if period == 'month' else count):
        begin = start + timedelta(days=offset) if period == 'month' else shift_month(start, offset)
        end = begin if period == 'month' else shift_month(begin, 1) - timedelta(days=1)
        key = begin.isoformat() if period == 'month' else begin.isoformat()[:7]
        buckets[key] = {'start_date': begin.isoformat(), 'end_date': end.isoformat(),
                        'billing': dict.fromkeys(FIELDS, 0)}
    totals = dict.fromkeys(FIELDS, 0)
    for row in db.execute('''SELECT date(created_at,'+8 hours') AS day,
        COUNT(*) AS invoice_count,
        SUM(CASE WHEN status='paid' THEN 1 ELSE 0 END) AS paid_invoice_count,
        SUM(CASE WHEN status='unpaid' THEN 1 ELSE 0 END) AS unpaid_invoice_count,
        SUM(total_cents) AS billed_cents,
        SUM(CASE WHEN status='paid' THEN total_cents ELSE 0 END) AS paid_cents,
        SUM(CASE WHEN status='unpaid' THEN total_cents ELSE 0 END) AS unpaid_cents
        FROM invoices WHERE date(created_at,'+8 hours') >= ? AND date(created_at,'+8 hours') < ?
        GROUP BY day''', (start.isoformat(), stop.isoformat())):
        key = row['day'] if period == 'month' else row['day'][:7]
        for field in FIELDS:
            buckets[key]['billing'][field] += row[field]
            totals[field] += row[field]
    return {'period': period, 'start_date': start.isoformat(),
            'end_date': (stop - timedelta(days=1)).isoformat(),
            'timezone': 'Asia/Kuala_Lumpur', 'generated_at': datetime.now(timezone.utc).isoformat(),
            'granularity': 'day' if period == 'month' else 'month',
            'billing': totals, 'buckets': list(buckets.values())}
