
# -*- coding: utf-8 -*-

"""
a utility module for updatenotifier
"""


import logging

log = logging.getLogger(__name__)

import datetime

def findNextWeekDay(comic_schedule, currentUTCtime):
    d = currentUTCtime.weekday()
    cur_diff, cur = 7, None
    for k in comic_schedule.keys():
        if k > 0 and k - d > 0 and k - d < cur_diff:
            cur_diff, cur = k - d, k
        elif k < d and 7 + k - d > 0 and 7 + k - d < cur_diff:
            cur_diff, cur = 7 + k - d, k
        elif k - d == 0:
            # the same day! clearly the min can't be less
            # but we should check if it's after or befor
            if currentUTCtime.time() < comic_schedule[k]:
                return k
    if cur == 7:
        log.error("error in finding next weekday: cur was not set!")
    return cur

def calculateDiff(currentUTCtime, next_day, schedule):
    day = currentUTCtime.weekday()
    if next_day >= day:
        diff = datetime.timedelta(next_day - day)
    else:
        diff = datetime.timedelta(next_day + 7 - day)

    next_timedate = datetime.datetime.combine(currentUTCtime.date() + diff, 
            schedule[next_day])
    return  next_timedate - currentUTCtime

def prettify(timedelta):
    output = ""
    if timedelta.days > 1:
        output += str(timedelta.days) + " days, "
    elif timedelta.days == 1:
        output += "1 day, "
    h = timedelta.seconds // 60 // 60
    if h > 1:
        output += str(h) + " hours, "
    elif h == 1:
        output += "1 hour and "
    m = (timedelta.seconds - 60*60*h) // 60
    if m > 1:
        output += str(m) + " minutes, "
    if m == 1:
        output += "1 minute, "
    output += str(timedelta.seconds - 60*60*h - 60*m ) + " seconds"
    return output

def timeUntilNextUpdate(comic_schedule):
    log.info("calculator called")
    currentUTCtime = datetime.datetime.utcnow()
    day = findNextWeekDay(comic_schedule, currentUTCtime)
    return prettify(calculateDiff(currentUTCtime, day, comic_schedule))
