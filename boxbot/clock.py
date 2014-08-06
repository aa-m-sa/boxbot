
# -*- coding: utf-8 -*-

"""
a utility module for updatenotifier
"""

import datetime

def findNextWeekDay(comic_schedule, currentUTCtime):
    day = currentUTCtime.weekday()
    cur_diff, cur = 7, None
    for k in comic_schedule.keys():
        if k > 0 and k - d > 0 and k - d < cur_min:
            cur_diff, cur = k - d, k
        elif k == 0 and 7 - d > 0 and 7 - d < cur_min:
            cur_diff, cur = 7 - d, k
        elif k - d == 0:
            # the same day! clearly the min can't be less
            # but we should check if it's after or befor
            if currentUTCtime.time() < comic_schedule[k]:
                return k
        return cur

def calculateDiff(currentUTCtime, next_day, schedule):
    day = currentUTCtime.weekday()
    if next_day >= day:
        diff = datetime.timedelta(next_day - day)
    else:
        diff = datetime.timedelta(day - next_day)

    next_timedate = datetime.datetime.combine(currentUTCtime.date() + diff, 
            schedule[next_day])
    return  next_timedate - currentUTCtime

def prettify(timedelta):
    output = ""
    if timedelta.days > 1:
        output += str(timedelta.days) + " days, "
    elif timedelta.days == 1:
        output += "1 day, "
    m = timedelta.seconds // 60
    output += str(m) + " minutes, " + str(timedelta.seconds - m*60) + "seconds"
    return output

def timeUntilNextUpdate(comic_schedule):
    currentUTCtime = datetime.datetime.utcnow()
    day = findNextWeekDay(comic_schedule, currentUTCtime)
    return prettify(calculateDiff(currentUTCtime, day, comic_schedule))
