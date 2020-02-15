import I2C_LCD_driver as i2c_charLCD

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
        lcd = i2c_charLCD.lcd()
        lcd.backlight(1)
        lcd.lcd_clear()
        info("Started LCD display.")
        state.drawlist[:] = [True, True, True, True, True]
    except:
        if not retry:
            error("LCD display init failed.  The program will exit.")
            state.run = False
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
    lcd.lcd_display_string(state_name.ljust(10), 1)


def draw_time(state, lcd):
    if state.drawlist[1] == 2:
        state.blinker_last_refresh = monotonic()

        if not state.blinker:
            # blink colon off
            state.blinker = True
            lcd.lcd_display_string(" ", 1, 17)

        else:
            # blink colon back on
            state.blinker = False
            lcd.lcd_display_string(":", 1, 17)

    else:
        state.displayed_time_last_refresh = monotonic()

        if not state.blinker:
            localtime = datetime.now().strftime('%H %M')
        else:
            localtime = datetime.now().strftime('%H:%M')

        lcd.lcd_display_string(localtime.rjust(10), 1, 10)


def draw_temp(state, lcd):
    tts = '{0:.1f}°C'.format(state.setpoint)

    lcd.lcd_display_string(tts.center(20), 2)


def draw_sensor(state, lcd):
    if state.stemp is None:
        sensortemp = 0
    else:
        sensortemp = state.stemp

    sensorhumidity = state.shumidity

    sensortemperature = '{:.1f}°C'.format(sensortemp)
    sensorhumidity = '{:.0f}%'.format(sensorhumidity)

    lcd.lcd_display_string(sensortemperature.ljust(6), 3)
    lcd.lcd_display_string(sensorhumidity.ljust(6), 4)


def draw_weather(state, lcd):
    latest_weather = state.latest_weather

    try:
        outtemp = '{0:.0f}°C'.format(latest_weather['temp'])
        cc = str(latest_weather['short'])
        outhumidity = str(latest_weather['humidity']) + "%"

    except:
        outtemp = '--°C'
        cc = "N/A"
        outhumidity = "---%"

    finally:
        lcd.lcd_display_string(outtemp.rjust(5), 3, 15)
        lcd.lcd_display_string(cc.ljust(8), 4, 7)
        lcd.lcd_display_string(outhumidity.rjust(5), 4, 15)
