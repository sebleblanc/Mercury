from datetime import datetime
from logging import info
from time import sleep

from mercury.utils import logged_thread_start


@logged_thread_start
def checkschedule(state):
    ''' Todo: rewrite this so it can have a
        customizable schedule for tracking away
        and sleeping time setpoint temperature offset.'''

    # 0:MON 1:TUE 2:WED 3:THU 4:FRI 5:SAT 6:SUN
    workdays = range(0, 4)		# workdays
    workhours = range(6, 17)
    customwd = range(4, 5) 		# custom workday(s)
    customwdhrs = range(6, 14)

    awaytemp = -1.5
    while state.run:
        now = datetime.now()
        weekday = now.weekday()
        hour = now.hour + 1		# react an hour in advance

        if weekday in workdays:
            whrs = workhours
        elif weekday in customwd:
            whrs = customwdhrs
        else:
            whrs = []
            state.setback = 0
        if hour in whrs:
            state.setback = awaytemp
        elif hour + 1 in whrs:		# temp boost in the morning
            state.setback = 1
        else:
            state.setback = 0
        state.target_temp = state.setpoint + state.setback
        state.drawlist[2] = True
        sleep(300)
