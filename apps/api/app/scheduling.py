"""Weekly pattern validation and dated slot planning; no database side effects."""
import hashlib
import json
import re
from datetime import date, datetime, timedelta, timezone

MALAYSIA=timezone(timedelta(hours=8))


def pattern_values(weekdays, start, end, duration, capacity, second_start=None, second_end=None):
    if not weekdays or len(weekdays)>7 or any(type(day) is not int or not 0<=day<=6 for day in weekdays) or len(set(weekdays))!=len(weekdays):
        raise ValueError('Choose distinct working days, Monday through Sunday.')
    if type(duration) is not int or not 15<=duration<=120 or duration%15 or type(capacity) is not int or not 1<=capacity<=20:
        raise ValueError('Use 15–120 minute slots in 15-minute steps and capacity 1–20.')
    if (second_start is None)!=(second_end is None):
        raise ValueError('Enter both start and end times for the second session.')
    sessions=[(start,end)]+([(second_start,second_end)] if second_start is not None else [])
    minutes=lambda value:int(value[:2])*60+int(value[3:])
    total=0
    for session_start,session_end in sessions:
        if any(not isinstance(value,str) or not re.fullmatch(r'(?:[01][0-9]|2[0-3]):[0-5][0-9]',value) for value in (session_start,session_end)):
            raise ValueError('Choose valid session start and end times.')
        length=minutes(session_end)-minutes(session_start)
        if length<=0 or length%duration:
            raise ValueError('Each session must end later on the same day and fit a whole number of slots.')
        total+=length//duration
    if second_start is not None and second_start<end:
        raise ValueError('The second session must start at or after the first session ends.')
    if total*len(weekdays)>200:
        raise ValueError('Limit each generated week to 200 slots across both sessions.')
    return {'weekdays':sorted(weekdays),'start_time':start,'end_time':end,'duration_minutes':duration,'capacity':capacity,
            'second_start_time':second_start,'second_end_time':second_end}


def week_slots(pattern, week_start, today):
    monday=date.fromisoformat(week_start)
    if monday.weekday()!=0 or monday<=today or monday>today+timedelta(days=56):
        raise ValueError('Choose a future Monday within the next eight weeks.')
    sessions=[(pattern['start_time'],pattern['end_time'])]
    if pattern.get('second_start_time') is not None:
        sessions.append((pattern['second_start_time'],pattern['second_end_time']))
    result=[]
    for weekday in pattern['weekdays']:
        day=monday+timedelta(days=weekday)
        for session_start,session_end in sessions:
            length=int(session_end[:2])*60+int(session_end[3:])-int(session_start[:2])*60-int(session_start[3:])
            start=datetime.fromisoformat(f"{day.isoformat()}T{session_start}:00+08:00")
            for minute in range(0,length,pattern['duration_minutes']):
                at=start+timedelta(minutes=minute)
                result.append({'starts_at':at.isoformat(),'ends_at':(at+timedelta(minutes=pattern['duration_minutes'])).isoformat(),
                               'clinic_date':day.isoformat(),'duration_minutes':pattern['duration_minutes'],'capacity':pattern['capacity']})
    return result


def preview_hash(doctor, version, week_start, slots):
    return hashlib.sha256(json.dumps({'doctor_id':doctor,'version':version,'week_start':week_start,'slots':slots},sort_keys=True,separators=(',',':')).encode()).hexdigest()
