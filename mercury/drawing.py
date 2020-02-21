from I2C_LCD_driver import LCD

from datetime import datetime
from logging import error, warning, info, debug
from time import sleep, monotonic


def get_screen_element_name(i):
    screenelements = ["Heater status",
                      "Time",
                      "Temperature setpoint",
                      "Sensor info",
                      "Weather info"]

    return screenelements[i]


# (re)start char LCD
def startlcd(state, retry=False):
    try:
        debug("Starting LCD display...")
        lcd = LCD()
        lcd.backlight(1)
        lcd.clear()
        info("Started LCD display.")
        state.drawlist[:] = [True, True, True, True, True]
    except BaseException as e:
        if not retry:
            error("LCD display init failed. (%s)" % e)
        else:
            warning("LCD display init failed.")
            return False

    return lcd


def displayfail(state):
    warning("Communication failed with display, re-initializing...")
    sleep(1)
    state.lcd = startlcd(state, retry=True)
    sleep(1)


def draw_heaterstatus(state, lcd):
    state_name = state.htrstatus.pretty_name
    lcd.display_string(state_name.ljust(10), 1)


def draw_time(state, lcd):
    if state.drawlist[1] == 2:
        state.blinker_last_refresh = monotonic()

        if not state.blinker:
            # blink colon off
            state.blinker = True
            lcd.display_string(" ", 1, 17)

        else:
            # blink colon back on
            state.blinker = False
            lcd.display_string(":", 1, 17)

    else:
        state.displayed_time_last_refresh = monotonic()

        if not state.blinker:
            localtime = datetime.now().strftime('%H %M')
        else:
            localtime = datetime.now().strftime('%H:%M')

        lcd.display_string(localtime.rjust(10), 1, 10)


def draw_temp(state, lcd):
    # tt = '{0:.1f}'.format(state.target_temp) + chr(223) + "C"
    tts = '{0:.1f}'.format(state.setpoint) + chr(223) + "C"

    lcd.display_string(tts.center(20), 2)


def draw_sensor(state, lcd):
    if state.stemp is None:
        sensortemp = 0
    else:
        sensortemp = state.stemp

    sensorhumidity = state.shumidity

    sensortemperature = '{0:.1f}'.format(sensortemp) + chr(223) + "C"
    sensorhumidity = '{0:.0f}'.format(sensorhumidity) + "%"

    lcd.display_string(sensortemperature.ljust(6), 3)
    lcd.display_string(sensorhumidity.ljust(6), 4)


def draw_weather(state, lcd):
    latest_weather = state.latest_weather

    try:
        outtemp = '{0:.0f}'.format(latest_weather['temp']) + chr(223) + "C"
        cc = str(latest_weather['short'])
        outhumidity = str(latest_weather['humidity']) + "%"

    except BaseException as e:
        warning("Got no weather information. (%s)" % e)
        outtemp = '--' + chr(223) + "C"
        cc = "N/A"
        outhumidity = "---%"

    finally:
        lcd.display_string(outtemp.rjust(5), 3, 15)
        lcd.display_string(cc.ljust(8), 4, 7)
        lcd.display_string(outhumidity.rjust(5), 4, 15)
