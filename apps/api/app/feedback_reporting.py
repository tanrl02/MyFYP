"""Current ratings grouped by original submission date, without personal details."""
from datetime import date, datetime, timedelta, timezone
from .visit_reporting import shift_month


def summary(db, period, year, month, quarter):
    first = month if period == 'month' else (quarter - 1) * 3 + 1 if period == 'quarter' else 1
    start = date(year, first, 1)
    stop = shift_month(start, {'month': 1, 'quarter': 3, 'year': 12}[period])
    counts = dict.fromkeys(range(1, 6), 0)
    for row in db.execute('''SELECT rating, COUNT(*) AS total FROM visit_feedback
        WHERE date(created_at,'+8 hours') >= ? AND date(created_at,'+8 hours') < ?
        GROUP BY rating''', (start.isoformat(), stop.isoformat())):
        counts[row['rating']] = row['total']
    total = sum(counts.values())
    return {'period': period, 'start_date': start.isoformat(),
            'end_date': (stop - timedelta(days=1)).isoformat(),
            'timezone': 'Asia/Kuala_Lumpur', 'generated_at': datetime.now(timezone.utc).isoformat(),
            'count': total, 'average_rating': sum(rating * n for rating, n in counts.items()) / total if total else None,
            'ratings': [{'rating': rating, 'count': n} for rating, n in counts.items()]}
