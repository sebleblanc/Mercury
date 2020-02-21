from datetime import datetime
from logging import debug
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
            debug("Today is a regular workday")
        elif weekday in customwd:
            whrs = customwdhrs
            debug("Today is a special workday")
        else:
            whrs = []
            state.setback = 0
        if hour in whrs:
            state.setback = awaytemp
            debug("User is away, offsetting setpoint by %d°C."
                  % state.setback)
        elif hour + 1 in whrs:
            state.setback = 1
            debug("User is getting ready for work,"
                  "offsetting setpoint by %d°C."
                  % state.setback)
        else:
            state.setback = 0
            debug("User is home, not offsetting setpoint.")
        state.target_temp = state.setpoint + state.setback
        debug("Actual target temperature is %d." % state.target_temp)
        state.drawlist[2] = True
        sleep(300)
