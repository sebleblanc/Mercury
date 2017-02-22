import time, pywapi, json, string, threading, csv
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
speaker = 12

GPIO.setmode(GPIO.BOARD)
GPIO.setup(rotaryA, GPIO.IN)
GPIO.setup(rotaryB, GPIO.IN)
GPIO.setup(rotarybutton, GPIO.IN, pull_up_down = GPIO.PUD_UP)
GPIO.setup(relay1, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(speaker, GPIO.OUT)

# Start PWM speaker
p = GPIO.PWM(speaker, 8000) 
p.start(0)


# Initialiaze variables
extemp,expressure,uimode,forecast_day,latest_weather,stemp,spressure,shumidity = 0,0,0,0,0,0,0,0
htrstate = "Off"

# Defaults
target_temp = 21        # in celsius
temp_tolerance = 0	#
refreshrate = 0.1	# in seconds

# todo - Load saved data 

def playtone(tone):
  if tone == 1:
    p.ChangeDutyCycle(100)
    time.sleep(0.001)
    p.ChangeDutyCycle(0)
  elif tone == 2:
    p.ChangeDutyCycle(100)
    time.sleep(0.001)
    p.ChangeDutyCycle(0)
  elif tone == 3:
    p.ChangeFrequency(440)
    p.ChangeDutyCycle(100)
    time.sleep(0.5)
    p.ChangeDutyCycle(0)
    p.ChangeFrequency(4000)
  elif tone == 4:
    p.ChangeFrequency(220)
    p.ChangeDutyCycle(100)
    time.sleep(0.5)
    p.ChangeDutyCycle(0)
    p.ChangeFrequency(4000)


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
      try:
        t,p,h = 0,0,0
        for a in range(0, samples):
          temp,pressure,humidity = readBME280All()
          t,p,h=t+temp,p+pressure,h+humidity
          time.sleep(refresh/samples)
        stemp,spressure,shumidity=t/samples,p/samples,h/samples
      except:
        print ("sensor failure")
        stemp,spressure,shumidity=0,0,0 

def externalsensordata():
    global extemp, expressure
    while True:
        with open('plutolatest.csv') as csvfile:
           reader = csv.DictReader(csvfile)
           for row in reader:
              extemp,expressure = row['temp'], row['pressure']
    time.sleep(3)
                                      # todo: compare timestamps
        
def htrtoggle(state):
    global htrstate
    if state == 0:
        GPIO.output(relay1, GPIO.LOW)
        htrstate = "Off"
    elif state == 1:
        GPIO.output(relay1, GPIO.HIGH)
        htrstate = "Heat"

def thermostat():
    global target_temp, stemp, extemp, temp_tolerance
    while True:
      watchtemp = stemp
      if watchtemp < target_temp - temp_tolerance:
           htrtoggle(1)        
      if watchtemp > target_temp + temp_tolerance:
           htrtoggle(0)
      time.sleep(3)

def drawstatus():
# Draw mode 0 (status screen)
    global latest_weather, stemp, shumidity, target_temp, htrstate, extemp
    localtime = time.asctime(time.localtime(time.time()))
    
    while latest_weather == 0:
      print ("waiting for external weather info")
      time.sleep(1)
   
    outtempraw = int(latest_weather['current_conditions'] ['temperature'])
    outtemp = '{0:.1f}'.format(outtempraw) + chr(223) +"C"
    cc = latest_weather['current_conditions']['text']
    outhumidity = latest_weather['current_conditions']['humidity'] + "%"
    date = time.strftime("%d/%m/%Y")
    sensortemp = '{0:.1f}'.format(stemp) + chr(223) + "C"
#    exsensortemp = (extemp) + chr(223) + "C"
    sensorhumidity = '{0:.1f}'.format(shumidity) + "%"
    tt = '{0:.1f}'.format(target_temp) + chr(223) + "C"

    mylcd.lcd_display_string(htrstate.ljust(10) + localtime[-13:-8].rjust(10),1)
    mylcd.lcd_display_string(tt.center(20), 2)
    mylcd.lcd_display_string(sensortemp.ljust(10) + outtemp.rjust(10), 3)
#    mylcd.lcd_display_string(exsensortemp.ljust(10) + outtemp.rjust(10), 3)
    mylcd.lcd_display_string(sensorhumidity.ljust(10) + outhumidity.rjust(10), 4)
    return

def drawweather():
# Draw mode 1 (weather screen)
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

    mylcd.lcd_display_string(dayofweek[0:3] + " " + date.ljust(6) +"  " + localtime[-13:-8].rjust(8))
    mylcd.lcd_display_string("High".center(9) + "|" + "Low".center(10), 2)
    mylcd.lcd_display_string(high.center(9) + "|" + low.center(10), 3)
    mylcd.lcd_display_string(sensortemp.ljust(10) + outtemp.rjust(10), 4)
    return

def redraw():
    global uimode
    while True:
      if uimode == 0:
        drawstatus()
      else:
        drawweather()
      time.sleep(refreshrate)
        

# Define rotary actions depending on current mode
def rotaryevent(event):
      global uimode
      if uimode == 0:
        global target_temp
        if event == 1:
            target_temp = target_temp + 0.1
            playtone(1)
        elif event == 2:
            target_temp = target_temp - 0.1
            playtone(2)

      elif uimode == 1:
        global forecast_day
        if event == 1:
            forecast_day = forecast_day + 1
            if forecast_day > 4:
              forecast_day = 4
            else:
              playtone(1)

        elif event == 2:
            if forecast_day >= 1:
              forecast_day = forecast_day - 1
              if forecast_day < 0:
                forecast_day = 0 
              else:
                playtone(2)
      return

# This is the event callback routine to handle events
def switch_event(event):
        global uimode
        if event == RotaryEncoder.CLOCKWISE:
            rotaryevent(1)
        elif event == RotaryEncoder.ANTICLOCKWISE:
            rotaryevent(2)
        elif event == RotaryEncoder.BUTTONUP:
            if uimode == 0:
              uimode = 1
            else:
              uimode = 0
            playtone(3)
        elif event == RotaryEncoder.BUTTONDOWN:
            playtone(4)
        return

# Define the switch
rswitch = RotaryEncoder(rotaryA,rotaryB,rotarybutton,switch_event)

weatherthread = threading.Thread(target=getweather)
sensorthread = threading.Thread(target=smoothsensordata,args=(2,5))
externalsensorthread = threading.Thread(target=externalsensordata)
thermostatthread = threading.Thread(target=thermostat)
displaythread = threading.Thread(target=redraw)

weatherthread.start()
sensorthread.start()
#externalsensorthread.start()
thermostatthread.start()
displaythread.start()

mylcd = i2c_charLCD.lcd()
mylcd.backlight(1)

try:
  while True:
    time.sleep(5)
      
except KeyboardInterrupt:
  GPIO.cleanup()
  p.stop()
  weatherthread.stop()
  sensorthread.stop()
  externalsensorthread.stop()
  thermostatthread.stop()
  displaythread.stop()
