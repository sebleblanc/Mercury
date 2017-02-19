import time,pywapi,json,string,threading
import I2C_LCD_driver as i2c_charLCD
import RPi.GPIO as GPIO
from rotary_class import RotaryEncoder
from bme280 import readBME280All 

# Define GPIO inputs
rotaryA = 11 
rotaryB = 13
rotarybutton = 15

# Define GPIO outputs
relay1 = 7

GPIO.setmode(GPIO.BOARD)
GPIO.setup(relay1, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(rotaryA, GPIO.IN)
GPIO.setup(rotaryB, GPIO.IN)

# Initialiaze variables
uimode,forecast_day,latest_weather,stemp,spressure,shumidity = 0,0,0,0,0,0

def getweather():  
# Get weather from weather API
    while True:
      global latest_weather
      latest_weather = pywapi.get_weather_from_weather_com('CAXX2224:1:CA', units = 'metric' )
      time.sleep(900)

def smoothsensordata(samples,refresh):
# Average sensor readings (readings over timeperiod)
    global stemp,spressure,shumidity
    stemp,spressure,shumidity = readBME280All()
    while True:
      t,p,h = 0,0,0
      for a in range(0, samples):
        temp,pressure,humidity = readBME280All()
        t,p,h=t+temp,p+pressure,h+humidity
        time.sleep(refresh/samples)
      stemp,spressure,shumidity=t/samples,p/samples,h/samples

def drawweather():
# Define mode 1 (weather screen)
    global latest_weather,forecast_day,stemp
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

    print ("(re)drawing weather screen")
    mylcd.lcd_display_string(dayofweek[0:3] + " " + date.ljust(6) +"  " + localtime[-13:-8].rjust(8))
    mylcd.lcd_display_string("High".center(9) + "|" + "Low".center(9), 2)
    mylcd.lcd_display_string(high.center(9) + "|" + low.center(9), 3)
    mylcd.lcd_display_string(sensortemp.ljust(10) + outtemp.rjust(10), 4)
    return


# Define rotary actions depending on current mode
def rotaryevent(event):
      global uimode      
      if uimode == 0:
        global target_temp
        if event == 1:
            print ()
        elif event == 2:
            print ()
        elif event == 3:
            print ()
        elif event == 4:
            print ()

      elif uimode == 1:
        global forecast_day
        if event == 1:
            if forecast_day <= 3:
              forecast_day = forecast_day + 1
            if forecast_day > 4:
              forecast_day = 4
        elif event == 2:
            if forecast_day >= 1:
              forecast_day = forecast_day - 1
            if forecast_day < 0:
              forecast_day = 0 
        elif event == 3:
            print ()
        elif event == 4:
            print ()
      return

# This is the event callback routine to handle events
def switch_event(event):
        if event == RotaryEncoder.CLOCKWISE:
          rotaryevent(1)
        elif event == RotaryEncoder.ANTICLOCKWISE:
          rotaryevent(2)
        elif event == RotaryEncoder.BUTTONDOWN:
          rotaryevent(3)
        elif event == RotaryEncoder.BUTTONUP:
          rotaryevent(4)
        return

# Define the switch
rswitch = RotaryEncoder(rotaryA,rotaryB,rotarybutton,switch_event)

weatherthread = threading.Thread(target=getweather)
sensorthread = threading.Thread(target=smoothsensordata,args=(5,30))

weatherthread.start()
sensorthread.start()
mylcd = i2c_charLCD.lcd()
mylcd.backlight(1)


try:
  while 1:

    time.sleep(0.8)
except KeyboardInterrupt:
  weatherthread.stop()
  sensorthread.stop()
  GPIO.cleanup()
GPIO.cleanup()
weatherthread.stop()
sensorthread.stop()
