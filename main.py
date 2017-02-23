import time, pywapi, json, string, threading, csv, datetime, os, signal, sys
import I2C_LCD_driver as i2c_charLCD
import RPi.GPIO as GPIO
from rotary_class import RotaryEncoder
from bme280 import readBME280All 

# Define GPIO inputs
rotaryA = 11 
rotaryB = 13
rotarybutton = 15

# Define GPIO outputs
relay1 = 16	# --stage 1 heat (W1)
relay2 = 18	# --stage 2 heat (W2)
speaker = 12

GPIO.setmode(GPIO.BOARD)
GPIO.setup(rotaryA, GPIO.IN)
GPIO.setup(rotaryB, GPIO.IN)
GPIO.setup(rotarybutton, GPIO.IN, pull_up_down = GPIO.PUD_UP)
GPIO.setup(relay1, GPIO.OUT, initial=GPIO.HIGH)
GPIO.setup(relay2, GPIO.OUT, initial=GPIO.HIGH)
GPIO.setup(speaker, GPIO.OUT)

# Start char LCD
mylcd = i2c_charLCD.lcd()
mylcd.backlight(1)

# Start PWM speaker
p = GPIO.PWM(speaker, 600) 
p.start(0)

# Initialiaze variables
now = datetime.datetime.now()
uimode,forecast_day,latest_weather,spressure,shumidity = 0,0,0,0,0
run,toggledisplay = True,True
stemp = None
htrstate = ['Off', 'Low Heat', 'Full Heat']
htrstatus = htrstate[0]
lhs = [now, htrstatus,  0] 	# endtime, last state, last temp

# Defaults
target_temp_setting = 20.8      # in celsius
temp_tolerance = 0.9	
refreshrate = 0.1		# in seconds

# todo - Load saved data 

# OS signal handler
def handler_stop_signals(signum, frame):
    global run
    run = False
signal.signal(signal.SIGINT, handler_stop_signals)
signal.signal(signal.SIGTERM, handler_stop_signals)

def playtone(tone):
  if tone == 1:
    p.ChangeDutyCycle(100)
    time.sleep(0.01)
    p.ChangeDutyCycle(0)
  elif tone == 2:
    p.ChangeDutyCycle(100)
    time.sleep(0.01)
    p.ChangeDutyCycle(0)
  elif tone == 3:
    p.ChangeDutyCycle(50)
    p.ChangeFrequency(880)
    time.sleep(0.05)
    p.ChangeDutyCycle(0)
    p.ChangeFrequency(50)
  elif tone == 4:
    p.ChangeFrequency(220)
    p.ChangeDutyCycle(50)
    time.sleep(0.05)
    p.ChangeDutyCycle(0)

def getweather():  
# Get weather from weather API
    while True:
      try:
        global latest_weather
        print (datetime.datetime.now()," - updating weather data...")
        latest_weather = pywapi.get_weather_from_weather_com('CAXX2224:1:CA', units = 'metric' )
        time.sleep(3)
      except:
        print (datetime.datetime.now()," - ERROR: weather update failure")
      finally:
        print (datetime.datetime.now()," - weather updated from weather.com")
        time.sleep(900)

def smoothsensordata(samples,refresh):
# Average sensor readings (readings over timeperiod)
    global stemp,spressure,shumidity
    while True:
      try:
        stemp,spressure,shumidity = readBME280All()
      except:
        print (datetime.datetime.now()," - ERROR: sensor failure")
        stemp,spressure,shumidity=None,0,0 
        time.sleep(5)
      finally:
        t,p,h = 0,0,0
        for a in range(0, samples):
          temp,pressure,humidity = readBME280All()
          t,p,h=t+temp,p+pressure,h+humidity
          time.sleep(refresh/samples)
        stemp,spressure,shumidity=t/samples,p/samples,h/samples

def checkschedule():	# 0:MON 1:TUE 2:WED 3:THU 4:FRI 5:SAT 6:SUN
    global target_temp, target_temp_setting
    while True:
      awaytemp = target_temp_setting - 2
      sleepingtemp = target_temp_setting

      now = datetime.datetime.now()
      weekday = now.weekday()
      hour = now.hour + 1		# react an hour in advance
    
      workdays=range(0,4)		# workdays
      workhours=range(6,18)
      customwd=range(4,5) 	# custom workday(s)
      customwdhours=range(6,14)

      if weekday in workdays:
        whrs = workhours
      elif weekday in customwd:
        whrs = customwdhrs
      else:
        whrs = None
        target_temp = target_temp_setting

      if hour in whrs:
        target_temp = awaytemp
      elif hour+1 in whrs:		# temp boost in the morning
        target_temp = target_temp_setting + 1
      else:
        target_temp = target_temp_setting
      
      time.sleep(300)

def htrtoggle(state):
    global htrstatus, stemp, htrstate, lhs
    now = datetime.datetime.now()
    lhs = [now, htrstatus, stemp]
    if state == 0:
        GPIO.output(relay1, GPIO.HIGH)
        GPIO.output(relay2, GPIO.HIGH)
        htrstatus = htrstate[0]
    elif state == 1:
        GPIO.output(relay1, GPIO.LOW)
        GPIO.output(relay2, GPIO.HIGH)
        htrstatus = htrstate[1]
    elif state == 2:
        GPIO.output(relay1, GPIO.LOW)
        GPIO.output(relay2, GPIO.LOW)
        htrstatus = htrstate[2]
    if lhs[1] != htrstatus:
      print (now," - Heater was set to ", lhs[1],", setting to ", htrstatus)

def thermostat():
    global target_temp, stemp, temp_tolerance, htrstatus, htrstate, lhs
    time.sleep(5)
    while True:
      now = datetime.datetime.now()
      tdelta = now - lhs[0]
      seconds = tdelta.total_seconds()
      lasttemp = lhs[2]
 
      while stemp == None:
        now = datetime.datetime.now()
        tdelta = now - lhs[0]
        seconds = tdelta.total_seconds()
        time.sleep(3)
        if seconds >= 300:
          htrtoggle(0)

      if stemp >= target_temp:
        htrtoggle(0)
      elif htrstatus == htrstate[1]:
        if seconds > 300:			# determine if stage 1 is heating fast enough
          if stemp - lasttemp < 0.066:		# threshold for 0.8°C per hour =  0.066°C over 5min  (0.8/60)*5
            htrtoggle(2)
      elif htrstatus == htrstate[2]:
        if seconds > 300:
          if stemp + (stemp - lasttemp) >= target_temp:		# project temperature increase to see if we are 5 min away from target temperature
            htrtoggle(1)
      elif htrstatus == htrstate[0]:
        if stemp < target_temp - temp_tolerance:		# Turn on at full heat for at least 10 seconds
          htrtoggle(2)
          time.sleep(10)
      time.sleep(1)

def drawstatus():
# Draw mode 0 (status screen)
    global latest_weather, stemp, shumidity, target_temp, target_temp_setting, htrstatus
    localtime = time.asctime(time.localtime(time.time()))
    
    if stemp == None:
       sensortemp = 0
    else:
       sensortemp = stemp

    if latest_weather == 0:
      outtemp = '---' + chr(223) +"C"
      cc = "N/A"
      outhumidity = "---%"
    else:
      outtempraw = int(latest_weather['current_conditions'] ['temperature'])
      outtemp = '{0:.1f}'.format(outtempraw) + chr(223) +"C"
      cc = latest_weather['current_conditions']['text']
      outhumidity = latest_weather['current_conditions']['humidity'] + "%"

    date = time.strftime("%d/%m/%Y")
    sensortemperature = '{0:.2f}'.format(sensortemp) + chr(223) + "C"
    sensorhumidity = '{0:.0f}'.format(shumidity) + "%"
    tt = '{0:.1f}'.format(target_temp) + chr(223) + "C"
    tts = '{0:.1f}'.format(target_temp_setting) + chr(223) + "C"

    mylcd.lcd_display_string(htrstatus.ljust(10) + localtime[-13:-8].rjust(10),1)
    mylcd.lcd_display_string(tts.center(10) + "(" + tt.center(8) + ")", 2)
#    mylcd.lcd_display_string(tts.center(20), 2)
    mylcd.lcd_display_string(sensortemperature.ljust(10) + outtemp.rjust(10), 3)
    mylcd.lcd_display_string(sensorhumidity.ljust(10) + outhumidity.rjust(10), 4)
    return

def drawweather():
# Draw mode 1 (weather screen)
    global latest_weather,forecast_day,stemp
    localtime = time.asctime(time.localtime(time.time()))

    if stemp == None:
       sensortemp = 0
    else:
       sensortemp = stemp

    if latest_weather == 0:
      for i in range(0,11):
        print ("waiting for external weather info")
        time.sleep(1)
        if latest_weather != 0:
          break

    if latest_weather == 0:
      outtemp = '---' + chr(223) +"C"
      cc = "N/A"
      outhumidity = "---%"
 
    outtempraw = int(latest_weather['current_conditions'] ['temperature'])
    outtemp = '{0:.1f}'.format(outtempraw) + chr(223) +"C"
    cc = latest_weather['current_conditions']['text']
    outhumidity = int(latest_weather['current_conditions']['humidity'])
    dayofweek = latest_weather['forecasts'][forecast_day]['day_of_week']
    date = latest_weather['forecasts'][forecast_day]['date']
    high = latest_weather['forecasts'][forecast_day]['high'] + chr(223) + "C" 
    low = latest_weather['forecasts'][forecast_day]['low'] + chr(223) + "C"
    sensortemperature = '{0:.1f}'.format(sensortemp) + chr(223) + "C"

    mylcd.lcd_display_string(dayofweek[0:3] + " " + date.ljust(6) +"  " + localtime[-13:-8].rjust(8))
    mylcd.lcd_display_string("High".center(9) + "|" + "Low".center(10), 2)
    mylcd.lcd_display_string(high.center(9) + "|" + low.center(10), 3)
    mylcd.lcd_display_string(sensortemperature.ljust(10) + outtemp.rjust(10), 4)
    return

def redraw():
    global uimode
    while True:
      if not toggledisplay:
        mylcd.lcd_clear()
        mylcd.backlight(0)
        return
      if uimode == 0:
        drawstatus()
      else:
        drawweather()
      time.sleep(refreshrate)
    

# Define rotary actions depending on current mode
def rotaryevent(event):
      global uimode

      if uimode == 0:
        global target_temp_setting
        tt = '{0:.1f}'.format(target_temp_setting) + chr(223) + "C"

        if event == 1:
            target_temp_setting += 0.1
            playtone(1)

        elif event == 2:
            target_temp_setting -= 0.1
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
schedulethread = threading.Thread(target=checkschedule)
sensorthread = threading.Thread(target=smoothsensordata, args=(2,5))
thermostatthread = threading.Thread(target=thermostat)
displaythread = threading.Thread(target=redraw)

weatherthread.setDaemon(True)
sensorthread.setDaemon(True)
thermostatthread.setDaemon(True)
schedulethread.setDaemon(True)

sensorthread.start()
schedulethread.start()
weatherthread.start()
displaythread.start()
time.sleep(5)
thermostatthread.start()

try:
  while run:
    time.sleep(1)
    pass  
except KeyboardInterrupt:
    pass
finally:
    toggledisplay=False
    displaythread.join()
    GPIO.cleanup()
    p.stop()
    print(datetime.datetime.now(), " program exited cleanly")


