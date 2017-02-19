import I2C_LCD_driver as i2c_charLCD
import time
import pywapi
from pprint import pprint
from rotary_class import RotaryEncoder
import RPi.GPIO as GPIO
from bme280 import readBME280All 
import json  
import string
import threading

# Define Rotary GPIO inputs
PIN_A = 11 
PIN_B = 13
BUTTON = 15

# Define Relay outputs
RELAY_A = 7

GPIO.setmode(GPIO.BOARD)
GPIO.setup(RELAY_A, GPIO.OUT, initial=GPIO.LOW)
#GPIO.setup(RELAY_B, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(PIN_A, GPIO.IN)
GPIO.setup(PIN_B, GPIO.IN)


result,stemp,spressure,shumidity=0,0,0,0
forecast_day=0


mylcd = i2c_charLCD.lcd()
mylcd.backlight(1)

def getweather():
    while True:
      global result
      result = pywapi.get_weather_from_weather_com('CAXX2224:1:CA', units = 'metric' )
      time.sleep(900)

def getsensordata(samples,refresh):
    global stemp,spressure,shumidity
    stemp,spressure,shumidity = readBME280All()
    while True:
      t,p,h = 0,0,0
      for a in range(0, samples):
        temp,pressure,humidity = readBME280All()
        t,p,h=t+temp,p+pressure,h+humidity
        time.sleep(refresh/samples)
      stemp,spressure,shumidity=t/samples,p/samples,h/samples

weatherthread = threading.Thread(target=getweather)
sensorthread = threading.Thread(target=getsensordata,args=(5,30))
weatherthread.start()
sensorthread.start()

# This is the event callback routine to handle events
def switch_event(event):
        global forecast_day
        if event == RotaryEncoder.CLOCKWISE:
          GPIO.output(RELAY_A, GPIO.HIGH)
          if forecast_day < 3:
            forecast_day = forecast_day + 1
          else:
            forecast_day = 4 
        elif event == RotaryEncoder.ANTICLOCKWISE:
          GPIO.output(RELAY_A, GPIO.LOW)
          if forecast_day > 1:
            forecast_day=forecast_day-1
          else:
            forecast_day=0 
        elif event == RotaryEncoder.BUTTONDOWN:
          print ("Button down")
        elif event == RotaryEncoder.BUTTONUP:
          print ("Button up")
        return

# Define the switch
rswitch = RotaryEncoder(PIN_A,PIN_B,BUTTON,switch_event)





try:
  while 1:
    localtime = time.asctime(time.localtime(time.time()))
    
    while result == 0:
      print ("waiting for external weather info")
      time.sleep(1)
   
    outtempraw = int(result['current_conditions'] ['temperature'])
    outtemp = '{0:.1f}'.format(outtempraw) + chr(223) +"C"
    cc = result['current_conditions']['text']
    outhumidity = int(result['current_conditions']['humidity'])
    dayofweek = result['forecasts'][forecast_day]['day_of_week']
    date = result['forecasts'][forecast_day]['date']
    high = result['forecasts'][forecast_day]['high'] + chr(223) + "C" 
    low = result['forecasts'][forecast_day]['low'] + chr(223) + "C"
    sensortemp = '{0:.1f}'.format(stemp) + chr(223) + "C"

    print ("refreshing screen")
    mylcd.lcd_display_string(dayofweek[0:3] + " " + date.ljust(6) +"  " + localtime[-13:-8].rjust(8))
    mylcd.lcd_display_string("High".center(9) + "|" + "Low".center(9), 2)
    mylcd.lcd_display_string(high.center(9) + "|" + low.center(9), 3)
    mylcd.lcd_display_string(sensortemp.ljust(10) + outtemp.rjust(10), 4)





    time.sleep(0.8)
except KeyboardInterrupt:
  weatherthread.stop()
  sensorthread.stop()
  GPIO.cleanup()
  print("exited")
  raise
