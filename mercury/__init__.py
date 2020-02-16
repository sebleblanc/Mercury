from __future__ import print_function
from bme280 import readBME280All

from enum import Enum
from functools import partial
from logging import critical, error, warning, info, debug
from math import floor
from time import monotonic, sleep
from threading import Thread

import click
import datetime
import signal
import struct
import requests

from mercury import drawing, gpio
from mercury.utils import (
    try_function,
    setup_logging,
    setup_serial,
    log_thread_start,
    get_config_file,
    load_settings,
    save_settings,
    playtone,
)


class State:
    '''Stores all mutable application state'''

    def __init__(self):
        self.tt_in = 0
        self.setback = 0
        self.forecast_day = 0
        self.latest_weather = None
        self.stemp = False
        self.spressure = 0
        self.shumidity = 0
        self.blinker = True
        self.displayed_time_last_refresh = 0
        self.blinker_last_refresh = 0
        self.run = True
        self.toggledisplay = True
        self.refetch = True
        self.htrstatus = HeaterState.OFF

        self.setpoint = 20

        # Defaults
        self.setpoint = 20   # in celsius
        self.sensortimeout = 300
        self.heartbeatinterval = 30
        self.temp_tolerance = 1.8
        self.refreshrate = 0.1 		# in seconds
        self.target_temp = self.setpoint

        # 0 Heater status
        # 1 Time
        # 2 Setpoint
        # 3 Sensor data
        # 4 Weather data
        self.drawlist = [True, True, True, True, True]

        self.configfile = None

        self.serial = None
        self.lhs = [None, None, None]


class HeaterState(Enum):
    OFF = 0
    FAN_ONLY = 1
    LOW_HEAT = 2
    FULL_HEAT = 3

    @property
    def pretty_name(self):
        _pretty_names = {
            HeaterState.OFF: 'OFF',
            HeaterState.FAN_ONLY: 'FAN only',
            HeaterState.LOW_HEAT: 'Low Heat',
            HeaterState.FULL_HEAT: 'Full Heat',
        }

        return _pretty_names[self]


# OS signal handler
def handler_stop_signals(signum, frame):
    state.run = False


def getweather():
    '''Retrieve weather from OpenWeatherMap'''

    weatherapikey = state.weatherapikey
    locationid = state.locationid

    log_thread_start(info, state.threads['weather'])

    while True:
        base_owm_url = ('http://api.openweathermap.org/data/2.5/weather'
                        '?appid={key}'
                        '&id={loc}'
                        '&units={units}')
        try:
            owm_url = base_owm_url.format(key=weatherapikey,
                                          loc=locationid,
                                          units='metric')
            debug("checking weather data using %s" % owm_url)
            response = requests.get(owm_url)
            owm_weather = response.json()

            # Make a simpler dict
            short = owm_weather['weather'][0]['main']
            long = owm_weather['weather'][0]['description']
            if long.lower() == short.lower():
                long = short
            elif short.lower() in long.lower():
                long = long.capitalize()
            else:
                long = ("%s: %s" % (short, long))

            shortened_weather = {
                'temp': int(owm_weather['main']['temp']),
                'feels': int(owm_weather['main']['feels_like']),
                'short': str(owm_weather['weather'][0]['main']),
                'long': str(long),
                'humidity': str(owm_weather['main']['humidity']),
                'pressure': str(owm_weather['main']['pressure']),
            }

            if state.latest_weather == shortened_weather:
                debug("No weather changes detected.")
            else:
                state.latest_weather = shortened_weather
                info('Updated weather.  Temp: {temp}°C '
                     '(feels like {feels}°C), {long}, '
                     'Humidity: {humidity}%, Pressure: {pressure}kPa'
                     .format(**state.latest_weather))
            next_check_seconds = 1800

        except:
            warning("Weather update failure.")
            state.latest_weather = None
            next_check_seconds = 60

        finally:
            state.drawlist[4] = True
            sleep(next_check_seconds)


def fetchhtrstate(serial):
    output = b'9\n'

    debug("sending status request (%s) to the heater" % output)

    serial.write(output)
    sleep(0.1)
    response = serial.readline()
    if response != '':
        st = (struct.unpack('>BBB', response)[0] - 48)

    else:
        st = None
        return

    try:
        htst = HeaterState(st)
    except ValueError as e:
        error('invalid heater state (%s)' % e)
        return
    else:
        debug("heater returned state %s (%s)" % (htst.name, htst.value))
        return htst


def heartbeat():
    lhs = state.lhs
    stemp = state.stemp
    target_temp = state.target_temp
    heartbeatinterval = state.heartbeatinterval
    drawlist = state.drawlist
    lastfetch = monotonic()

    log_thread_start(info, state.threads['hvac'])

    while True:
        while state.refetch:
            now = monotonic()
            previousstatus = state.htrstatus
            getstatus = -1
            debug("Trying to refetch heater status")

            try:
                current_status = fetchhtrstate(state.serial)

                sleep(0.1)

                if getstatus is not None:
                    lastfetch = monotonic()

                    if state.htrstatus == current_status:
                        debug("no heater state change detected")
                    else:
                        # -> redraw the status part of screen and
                        #    remember/reset time, heater state, and
                        #    temperature
                        drawlist[0] = True
                        state.htrstatus = current_status

                        info('Current: {stemp:.2f}°C, '
                             'Target: {target_temp:.2f}°C. '
                             '{previousstatus!r} → now is {heater_status!r}.'
                             .format(
                                 selftemp=stemp,
                                 target_temp=target_temp,
                                 previousstatus=previousstatus.pretty_name,
                                 heater_status=state.htrstatus.pretty_name))

                        lhs[:] = [datetime.datetime.now(),
                                  state.htrstatus,
                                  state.stemp]
                else:
                    error("Got invalid status: %r" % getstatus)

            except:
                warning("Failed to contact Arduino!")

            finally:
                state.refetch = False
                sleep(2)

        while not state.refetch:
            now = monotonic()

            if (now - lastfetch) >= heartbeatinterval:
                state.refetch = True

            else:
                sleep(2)


def smoothsensordata(samples, refresh):
    '''Average out sensor readings. Takes number of samples over a period
    of time (refresh)
    '''
    threads = state.threads

    log_thread_start(info, threads['sensor'])

    sensortime = monotonic()

    while state.run:
        t, p, h = 0, 0, 0
        now = monotonic()
        try:
            stemp, spressure, shumidity = readBME280All()
            for a in range(0, samples):
                temp, pressure, humidity = readBME280All()

                t += temp
                p += pressure
                h += humidity

                sleep(refresh / samples)

            state.stemp = t / samples
            state.spressure = p / samples
            state.shumidity = h / samples

            debug("Got sensor data: %s°C, %skPa, %s%%"
                  % (stemp, spressure, shumidity))
            sensortime = now

        except:
            warning("Sensor failure")
            if (now - sensortime).total_seconds() >= state.sensortimeout:
                error("Timed out waiting for sensor data -- exiting!")
                state.run = False
        finally:
            state.drawlist[3] = True
            sleep(5)


def checkschedule():
    # 0:MON 1:TUE 2:WED 3:THU 4:FRI 5:SAT 6:SUN
    threads = state.threads

    log_thread_start(info, threads['schedule'])

    workdays = range(0, 4)		# workdays
    workhours = range(6, 17)
    customwd = range(4, 5) 		# custom workday(s)
    customwdhrs = range(6, 14)

    awaytemp = -1.5
    sleepingtemp = -0.5

    while state.run:
        now = datetime.datetime.now()
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


def htrtoggle(st):
    # Warning: parameter 'st' (formerly known as state) has nothing to do
    # with the global value named 'state'
    state.refetch = True

    debug("checking current heater status (%s)" % state.refetch)

    while state.run and state.refetch:
        sleep(0.1)

    if state.htrstatus == st:
        warning("toggled heater %s, but already set to %s."
                % (st, state.htrstatus))

    else:
        output = b'%d\n' % st.value
        state.serial.write(output)
        sleep(0.1)
        state.refetch = True

        debug("sent state change to heater: %s" % st)
        debug("confirming heater status...")

        while state.run and state.refetch:
            sleep(0.1)

        if state.htrstatus == HeaterState(st):
            info("Heater toggle succeeded: %s" % state.htrstatus)
        elif state.htrstatus == HeaterState.FAN_ONLY:
            info("Heater toggle resulted in: %s" % state.htrstatus)
        else:
            error("Heater toggle failed: got %s, expected %s"
                  % (state.htrstatus, HeaterState(st)))


def thermostat():
    lhs = state.lhs

    threads = state.threads

    info("Starting threads")
    log_thread_start(info, state.threads['thermostat'])

    # minimum threshold (in °C/hour) under which we switch to stage 2
    stage1min = 0.04

    # maximum threshold (in °C/hour) over which we switch to stage 1
    stage2max = 0.5

    # time (s) to wait before checking if we should change states
    stage1timeout = 10 * 60

    # time until forced switch to stage 2
    stage1maxtime = 60 * 60
    stage2timeout = 10 * 60
    fantimeout = 0

    # time we shold hope to stay off for
    idletime = 30 * 60
    # stdout updates and save settings
    updatetimeout = 60 * 60

    threads['display'].start()
    threads['hvac'].start()

    state.stemp = False
    threads['sensor'].start()

    debug("Waiting for sensor data...")
    while state.run and not state.stemp:
        sleep(0.5)

    debug("Waiting for hvac status...")
    while state.run and not state.htrstatus:
        sleep(0.5)
    debug("Got hvac status: %s" % state.htrstatus)

    # endtime, last state, last temp
    lhs[:] = [datetime.datetime.now(), state.htrstatus, state.stemp]

    threads['schedule'].start()
    threads['weather'].start()
    threads['ui_input'].start()

    sleep(3)

    info("Heater: %s, Temp: %s°C" % (state.htrstatus.pretty_name,
                                     '{0:.1f}'.format(state.stemp)))

    while state.run:
        now = datetime.datetime.now()
        tdelta = now - state.lhs[0]
        seconds = tdelta.total_seconds()
        lasttime = lhs[0]
        lasttemp = lhs[2]
        stemp = state.stemp
        stempdelta = stemp - lasttemp
        current_htrstatus = state.htrstatus
        setpoint = state.setpoint

        status_string = ('{htrstatus}, {stemp:.2f}°C, [{stempdelta:.2f}°C '
                         'since {timestamp} ({temprate:.2f}°C/hr)]'
                         .format(
                             htrstatus=current_htrstatus.pretty_name,
                             stemp=stemp,
                             stempdelta=stempdelta,
                             timestamp=lasttime.strftime('%H:%M:%S'),
                             temprate=stempdelta / seconds * 3600))

        # Shut off the heater if temperature reached,
        # unless the heater is already off (so we can continue to increase time
        # delta counter to check timeouts)
        if (stemp >= state.target_temp + (state.temp_tolerance / 3)
                and current_htrstatus
                not in [HeaterState.OFF,
                        HeaterState.FAN_ONLY]):
            info("Temperature reached.")
            htrtoggle(HeaterState.OFF)

        # Project temperature increase, if we will hit target temperature
        elif current_htrstatus == HeaterState.LOW_HEAT:
            debug("staying %.1f minutes in stage 1" % (stage1timeout / 60))

            if seconds % stage1timeout <= 1:
                if stemp + (stemp - lasttemp) > state.target_temp:
                    info('Predicted target temperature in {0:.1f} minutes.'
                         .format(stage1timeout / 60))

                if seconds >= stage1maxtime:
                    # We have been on stage 1 for too long -> go to stage 2
                    info('Low Heat is taking too long: {0:.2f}°C '
                         'since {1} ({2} minutes ago)'
                         .format(stemp - lasttemp,
                                 lasttime.strftime("%H:%M:%S"),
                                 floor(seconds / 60)))
                    htrtoggle(HeaterState.FULL_HEAT)

        elif current_htrstatus == HeaterState.FULL_HEAT:
            debug("staying %.1f minutes in stage 2" % (stage2timeout / 60))

            if seconds % stage2timeout <= 1:
                if stemp + (stemp - lasttemp) > state.target_temp:
                    info('Predicted target temperature in %.1f minutes'
                         % (stage2timeout / 60))

        elif current_htrstatus == HeaterState.FAN_ONLY:
            pass

        elif current_htrstatus in (HeaterState.OFF, HeaterState.FAN_ONLY):
            # Temperature fell under the threshold, turning on
            if stemp < state.target_temp - state.temp_tolerance:
                info("Temperature more than %.1f°C below setpoint."
                     % state.temp_tolerance)
                if seconds > idletime:
                    htrtoggle(HeaterState.LOW_HEAT)
                else:
                    htrtoggle(HeaterState.FULL_HEAT)
        else:
            # We cannot reach this code unless there is a logic error
            # or a new heater status level that was not fully implemented

            critical("FIXME: Heater behavior not implemented!")
            raise NotImplementedError('No heater behavior implemented '
                                      'for status %s' % current_htrstatus)

        if seconds % updatetimeout <= 1:
            info(status_string)
            save_settings(state.config, state.configfile, setpoint)

        wait_time = (seconds % 1)
        sleep(1.5 - wait_time)		# sleep until next half second


def drawstatus(element):
    # Draw mode 0 (status screen)
    # print ("refreshing screen element ", element)

    def try_draw(method, *args, **kwargs):
        kwargs.setdefault('state', state)
        kwargs.setdefault('lcd', state.lcd)

        try_function(partial(drawing.displayfail, state),
                     method,
                     *args,
                     **kwargs)

    debug("refreshing screen element %s (%s)"
          % (element, drawing.get_screen_element_name(element)))

    # 0 - Heater Status
    if element == 0:
        try_draw(drawing.draw_heaterstatus)

    # 1 - Time
    elif element == 1:
        try_draw(drawing.draw_time)

    # 2 - Temperature setting
    elif element == 2:
        try_draw(drawing.draw_temp)

    # 3 - Sensor data
    elif element == 3:
        try_draw(drawing.draw_sensor)

    # 4 - Weather data
    elif element == 4:
        try_draw(drawing.draw_weather)


def redraw():
    drawlist = state.drawlist
    threads = state.threads

    log_thread_start(info, threads['display'])

    while True:
        if not state.toggledisplay:
            try:
                state.lcd.lcd_clear()
                state.lcd.backlight(0)
            except:
                pass
            return

        else:
            for i in range(0, len(drawlist)):
                if drawlist[i]:
                    drawstatus(i)
                    drawlist[i] = False
                    sleep(0.01)

        now = monotonic()
        # Decide if we should redraw the time...
        if (now - state.displayed_time_last_refresh) > 30:
            drawlist[1] = True
        # ...or just the blinker
        elif (now - state.blinker_last_refresh) >= 1:
            drawlist[1] = 2

        sleep(state.refreshrate)


def ui_input():
    threads = state.threads
    drawlist = state.drawlist

    log_thread_start(info, threads['ui_input'])

    while True:
        if state.tt_in != 0:
            if state.setpoint + state.tt_in >= 0 <= 30:
                state.setpoint += state.tt_in
                state.target_temp = state.setpoint + state.setback
                drawlist[2] = True
            state.tt_in = 0

        sleep(0.3)


# Define rotary actions depending on current mode
def rotaryevent(event):

    if event == 1:
        state.tt_in += 0.1
        playtone(1)
    elif event == 2:
        state.tt_in -= 0.1
        playtone(2)
    sleep(0.01)


@click.command()
@click.option('-c', '--config-file', type=click.Path(),
              default=get_config_file)
@click.option('-d', '--debug', is_flag=True)
@click.option('-v', '--verbose', count=True)
def main(config_file, debug, verbose):
    global state

    if debug:
        # debugging overrides verbosity
        verbose = 10

    # Verbosity starts at 0, most quiet, while Python logging has 50
    # meaning critical errors only.  Therefore, we calculate verbosity
    # by reversing the value and mapping it over 30–0
    logging_level = max(1, (3 - verbose)) * 10
    setup_logging(level=logging_level)

    state = State()

    state.configfile = config_file

    state.lcd = drawing.startlcd(state, retry=False)

    signal.signal(signal.SIGINT, handler_stop_signals)
    signal.signal(signal.SIGTERM, handler_stop_signals)

    try:
        config = load_settings(config_file)
    except FileNotFoundError:
        critical('Config file (%s) does not exist!' % state.configfile)
        raise

    state.config = config

    try:
        state.setpoint = float(config['setpoint'])
        state.weatherapikey = config['weatherapikey']
        state.locationid = config['locationid']

    except KeyError as e:
        critical('Invalid configuration file, missing key %s'
                 % e.args[0])

    try:
        serial = setup_serial()
    except:
        error("Could not setup serial device")
    else:
        state.serial = serial

    gpio.setup_gpio()

    # Define the switch
    gpio.RotaryEncoder(
        gpio.ROTARY_A,
        gpio.ROTARY_B,
        gpio.BUTTON,
        lambda e: gpio.switch_event(rotaryevent, e)
    )

    state.threads = {
        "hvac": Thread(name='hvac', target=heartbeat),
        "schedule": Thread(name='schedule', target=checkschedule),
        "sensor": Thread(name='sensor', target=smoothsensordata,
                         args=(3, 10)),  # (no. of samples, period time)
        "thermostat": Thread(name='thermostat', target=thermostat),
        "ui_input": Thread(name='ui_input', target=ui_input),
        "display": Thread(name='display', target=redraw),
        "weather": Thread(name='weather', target=getweather),
    }

    for t in state.threads:
        if t != "display":
            state.threads[t].setDaemon(True)

    state.threads['thermostat'].start()

    while state.run:
        sleep(0.5)

    info("Aborting...")

    save_settings(state.config, state.configfile, state.setpoint)

    state.toggledisplay = False
    state.threads['display'].join()

    info("EXIT: program exited.")


if __name__ == '__main__':
    main(auto_envvar_prefix="MERCURY")
