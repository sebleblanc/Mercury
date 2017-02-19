import time,pywapi,json,string,threading
import I2C_LCD_driver as i2c_charLCD
import RPi.GPIO as GPIO
from rotary_class import RotaryEncoder
from bme280 import readBME280All 

# Define GPIO inputs
rotaryA = 11 
rotaryB = 13
BUTTON = 15

# Define GPIO outputs
relay1 = 7

GPIO.setmode(GPIO.BOARD)
GPIO.setup(relay1, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(rotaryA, GPIO.IN)
GPIO.setup(rotaryB, GPIO.IN)

# Initialiaze variables
forecast_day,latest_weather,stemp,spressure,shumidity=0,0,0,0,0

mylcd = i2c_charLCD.lcd()
mylcd.backlight(1)


def getweather():  
# Get weather from weather API
    while True:
      global latest_weather
      latest_weather = pywapi.get_weather_from_weather_com('CAXX2224:1:CA', units = 'metric' )
      time.sleep(900)

def smoothsensordata(samples,refresh):
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
sensorthread = threading.Thread(target=smoothsensordata,args=(5,30))

weatherthread.start()
sensorthread.start()

# This is the event callback routine to handle events
def switch_event(event):
        global forecast_day
        if event == RotaryEncoder.CLOCKWISE:
          GPIO.output(relay1, GPIO.HIGH)
          if forecast_day < 3:
            forecast_day = forecast_day + 1
          else:
            forecast_day = 4 
        elif event == RotaryEncoder.ANTICLOCKWISE:
          GPIO.output(relay1, GPIO.LOW)
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
rswitch = RotaryEncoder(rotaryA,rotaryB,BUTTON,switch_event)



try:
  while 1:
    localtime = time.asctime(time.localtime(time.time()))
    
    while latest_weather == 0:
      print ("waiting for external weather info")
      time.sleep(1)
   
    outtempraw = int(latest_weather['current_conditions'] ['temperature'])
    outtemp = '{0:.1f}'.format(outtempraw) + chr(223) +"C"
    cc = latest_weather['current_conditions']['text']
    outhumidity = int(latest_weather['current_conditions']['humidity'])
    dayofweek = latest_weather['forecasts'][forecast_day]['day_of_week']
    date = latest_weather['forecasts'][forecast_day]['date']
    high = latest_weather['forecasts'][forecast_day]['high'] + chr(223) + "C" 
    low = latest_weather['forecasts'][forecast_day]['low'] + chr(223) + "C"
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
GPIO.cleanup()
weatherthread.stop()
sensorthread.stop()
