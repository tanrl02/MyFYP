"""Weekly pattern validation and dated slot planning; no database side effects."""
import hashlib
import json
import re
from datetime import date, datetime, timedelta, timezone

MALAYSIA=timezone(timedelta(hours=8))


def pattern_values(weekdays, start, end, duration, capacity):
    if not weekdays or len(weekdays)>7 or any(type(day) is not int or not 0<=day<=6 for day in weekdays) or len(set(weekdays))!=len(weekdays):
        raise ValueError('Choose distinct working days, Monday through Sunday.')
    if any(not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',value) for value in (start,end)):
        raise ValueError('Choose valid session start and end times.')
    if type(duration) is not int or not 15<=duration<=120 or duration%15 or type(capacity) is not int or not 1<=capacity<=20:
        raise ValueError('Use 15–120 minute slots in 15-minute steps and capacity 1–20.')
    minutes=lambda value:int(value[:2])*60+int(value[3:])
    length=minutes(end)-minutes(start)
    if length<=0 or length%duration:
        raise ValueError('Session end must be later on the same day and fit a whole number of slots.')
    if length//duration*len(weekdays)>200:
        raise ValueError('Limit each generated week to 200 slots.')
    return {'weekdays':sorted(weekdays),'start_time':start,'end_time':end,'duration_minutes':duration,'capacity':capacity}


def week_slots(pattern, week_start, today):
    monday=date.fromisoformat(week_start)
    if monday.weekday()!=0 or monday<=today or monday>today+timedelta(days=56):
        raise ValueError('Choose a future Monday within the next eight weeks.')
    length=int(pattern['end_time'][:2])*60+int(pattern['end_time'][3:])-int(pattern['start_time'][:2])*60-int(pattern['start_time'][3:])
    result=[]
    for weekday in pattern['weekdays']:
        day=monday+timedelta(days=weekday)
        start=datetime.fromisoformat(f"{day.isoformat()}T{pattern['start_time']}:00+08:00")
        for minute in range(0,length,pattern['duration_minutes']):
            at=start+timedelta(minutes=minute)
            result.append({'starts_at':at.isoformat(),'ends_at':(at+timedelta(minutes=pattern['duration_minutes'])).isoformat(),
                           'clinic_date':day.isoformat(),'duration_minutes':pattern['duration_minutes'],'capacity':pattern['capacity']})
    return result


def preview_hash(doctor, version, week_start, slots):
    return hashlib.sha256(json.dumps({'doctor_id':doctor,'version':version,'week_start':week_start,'slots':slots},sort_keys=True,separators=(',',':')).encode()).hexdigest()
