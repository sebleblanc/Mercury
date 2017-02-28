from __future__ import print_function
import time, pywapi, json, string, threading, csv, datetime, os, signal, sys
import I2C_LCD_driver as i2c_charLCD
from rotary_class import RotaryEncoder
from bme280 import readBME280All 
import RPi.GPIO as GPIO

# Define GPIO inputs
rotaryA = 7 
rotaryB = 11
rotarybutton = 13
resetbutton = 22

# Define GPIO outputs
relay1 = 16	# --stage 1 heat (W1)
relay2 = 18	# --stage 2 heat (W2)
relay3 = 15	# --fan override (G)
speaker = 12

# Reset button event
def reset_event(resetbutton):
    global drawlist
    time.sleep(0.010)
    if GPIO.input(resetbutton):
      playtone(3)
      mylcd.__init__()
      time.sleep(5)
    else:
      drawlist[0],drawlist[1],drawlist[2],drawlist[3],drawlist[4]=True,True,True,True,True
      playtone(4)
      time.sleep(3)
    return

GPIO.setmode(GPIO.BOARD)
GPIO.setup(rotaryA, GPIO.IN)
GPIO.setup(rotaryB, GPIO.IN)
GPIO.setup(rotarybutton, GPIO.IN)
GPIO.setup(resetbutton, GPIO.IN, pull_up_down = GPIO.PUD_UP)
GPIO.setup(relay1, GPIO.OUT, initial=GPIO.HIGH)
GPIO.setup(relay2, GPIO.OUT, initial=GPIO.HIGH)
GPIO.setup(relay3, GPIO.OUT, initial=GPIO.HIGH)
GPIO.setup(speaker, GPIO.OUT)
GPIO.add_event_detect(resetbutton, GPIO.BOTH, callback=reset_event, bouncetime=80)

# Start char LCD
mylcd = i2c_charLCD.lcd()
mylcd.backlight(1)

# Start PWM speaker
p = GPIO.PWM(speaker, 600) 
p.start(0)


# Defaults
setpoint = 20.5      # in celsius
sensortimeout = 300
temp_tolerance = 0.9	
frefreshrate = 0.01 		# in seconds
target_temp = setpoint

# todo - Load saved data 

# Initialiaze variables
tt_in,setback,uimode,forecast_day,latest_weather,spressure,shumidity = 0,0,0,0,0,0,0
blinker,run,toggledisplay = True,True,True
htrstate = ['Off', 'Low Heat', 'Full Heat', 'Fan only']
drawlist = [True, True, True, True, True]
htrstatus = htrstate[0]

sensorchecktime = datetime.datetime.now()
stemp = False
while not stemp:
  try:
    stemp,spressure,shumidity = readBME280All()
  except:
    print (datetime.datetime.now(),"WARNING: sensor failure")
    time.sleep(1)
  if (sensorchecktime-datetime.datetime.now()).total_seconds() >= 10:
    print (datetime.datetime.now(),"ERROR: Timed out waiting for sensor data -- exiting!")
    htrtoggle(0)
    run = False
lhs = [datetime.datetime.now(), htrstatus,  stemp] 	# endtime, last state, last temp

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

# Get weather from weather API
def getweather():  
    global latest_weather
    while True:
      try:
        #print (datetime.datetime.now(),"updating weather data...")
        latest_weather = pywapi.get_weather_from_weather_com('CAXX2224:1:CA', units = 'metric' )
        time.sleep(3)
      except:
        print (datetime.datetime.now(),"ERROR: weather update failure")
      finally:
        #print (datetime.datetime.now(),"weather updated from weather.com")
        drawlist[4] = True
        time.sleep(900)

# Average sensor readings: takes number of samples(samples) over a period of time (refresh)
def smoothsensordata(samples,refresh):  
    global stemp,spressure,shumidity,sensortimeout
    sensortime = datetime.datetime.now()
    while True:
      t,p,h = 0,0,0
      now = datetime.datetime.now()
      try:
        stemp,spressure,shumidity = readBME280All()
        for a in range(0, samples):
          temp,pressure,humidity = readBME280All()
          t,p,h=t+temp,p+pressure,h+humidity
          time.sleep(refresh/samples)
        stemp,spressure,shumidity=t/samples,p/samples,h/samples
        sensortime = now
      except:
        print (datetime.datetime.now(),"WARNING: sensor failure")
        if (now-sensortime).total_seconds() >= sensortimeout:
          print (datetime.datetime.now(),"ERROR: Timed out waiting for sensor data -- exiting!")
          htrtoggle(0)
          run = False
      finally:
        drawlist[3] = True 
        time.sleep(5)

def checkschedule():	# 0:MON 1:TUE 2:WED 3:THU 4:FRI 5:SAT 6:SUN
    global setback, target_temp, setpoint
    while True:
      awaytemp = -1.5
      sleepingtemp = -0.5

      now = datetime.datetime.now()
      weekday = now.weekday()
      hour = now.hour + 1		# react an hour in advance
    
      workdays=range(0,4)		# workdays
      workhours=range(6,17)
      customwd=range(4,5) 		# custom workday(s)
      customwdhrs=range(6,14)

      if weekday in workdays:
        whrs = workhours
      elif weekday in customwd:
        whrs = customwdhrs
      else:
        whrs = []
        setback = 0
      if hour in whrs:
        setback = awaytemp
      elif hour+1 in whrs:		# temp boost in the morning
        setback = 1
      else:
        setback = 0
      target_temp = setpoint + setback
      drawlist[2] = True
      time.sleep(300)

def htrtoggle(state):
    global htrstatus, stemp, htrstate, lhs, drawlist, target_temp
    now = datetime.datetime.now()
    if state == 0:
        GPIO.output(relay2, GPIO.HIGH)		# Just to be safe, always turn off stage 2 first
        GPIO.output(relay1, GPIO.HIGH)		# 
        GPIO.output(relay3, GPIO.HIGH)
        htrstatus = htrstate[0]
    elif state == 1:
        GPIO.output(relay2, GPIO.HIGH)
        GPIO.output(relay1, GPIO.LOW)
        GPIO.output(relay3, GPIO.HIGH)
        htrstatus = htrstate[1]
    elif state == 2:
        GPIO.output(relay1, GPIO.LOW)
        GPIO.output(relay2, GPIO.LOW)
        GPIO.output(relay3, GPIO.HIGH)
        htrstatus = htrstate[2]
    elif state == 3:
        GPIO.output(relay3, GPIO.LOW)	# turn override fan on before shutting off heater fan (to avoid shutting fan off for split-second)
        GPIO.output(relay2, GPIO.HIGH)
        GPIO.output(relay1, GPIO.HIGH)
        htrstatus = htrstate[3]
        
    drawlist[0] = True		# -> redraw the screen and remember/reset time, heater state, and temperature
    print (now, '{0:.2f}'.format(stemp) + "°C", "->", '{0:.2f}'.format(target_temp) + "°C.  Was", lhs[1] + ", setting to", htrstatus + ".")
    lhs=[now, htrstatus, stemp]

def thermostat():
    global run, target_temp, setback, stemp, temp_tolerance, htrstatus, htrstate, lhs
    stage1min = 0.01		# minimum threshold (in °C/hour) under which we switch to stage 2
    stage2max = 0.5		# maximum threshold (in °C/hour) over which we switch to stage 1
    time.sleep(5)
    stage1timeout=360		# time to wait before checking if we should change states
    stage2timeout=480
    fantimeout=80
    idletimeout=600
    updatetimeout=180		# stdout updates

    while run:
      now = datetime.datetime.now()
      tdelta = now - lhs[0]
      seconds = tdelta.total_seconds()
      lasttime = lhs[0]
      lasttemp = lhs[2]
      status_string = '{0:.2f}'.format(stemp-lasttemp) +  "°C since " + lasttime.strftime("%H:%M:%S") + " (" + '{0:.2f}'.format((stemp-lasttemp)/seconds*3600) + "°C/hr)"

      if stemp >= target_temp:			# Shut off the heater if temperature reached, 
        if htrstatus !=  htrstate[0] and htrstatus != htrstate[3]: 		# unless the heater is already off (so we can continue to increase time delta counter to check timeouts)
           print (now, "Temperature reached.")  # use fan to cool off elements
           print (now, status_string)
           htrtoggle(3)
        
      elif htrstatus == htrstate[1]:		# Project temperature increase, if we will hit target temperature
        print (('{0:.1f}'.format(seconds%stage1timeout)), "    ", end='\r')
        if seconds%stage1timeout <= 1:		#	If heating too slowly -> go to stage 2
          if stemp + (stemp - lasttemp) > target_temp:		
            print (now, "Predicted target temperature. ")
            print (now, status_string)
          elif (stemp - lasttemp)*seconds < stage1min*3600:	
            print (now, "Heating too slowly: (min=", stage1min, "°C/hr)") 
            print (now, status_string)
            htrtoggle(2)

      elif htrstatus == htrstate[2]:
        print ('{0:.1f}'.format(seconds%stage2timeout), "    ", end='\r')
        if seconds%stage2timeout <= 1:		#       If heating too quickly -> stage 1.
          if stemp + (stemp - lasttemp) > target_temp:
            print (now, "Predicted target temperature.")
            print (now, status_string)
            htrtoggle(1)
          elif stemp - lasttemp >= stage2max:			
            print (now, "Heating too quickly: (min=", stage2max, "°C/hr)") 
            print (now, status_string)
            htrtoggle(1)

      elif htrstatus == htrstate[3]:		# Stay on for a while, then turn off.
        print ('{0:.1f}'.format(seconds%fantimeout), "    ", end='\r')
        if seconds >= fantimeout:
            print (now, status_string)
            htrtoggle(0)

      elif htrstatus == htrstate[0]:		# If temperature falls under the threshold, turn on at high heat to start
        print ('{0:.1f}'.format(seconds%idletimeout), "    ", end='\r')
        if stemp < target_temp - temp_tolerance:
          print (now, "Temperature more than", str(temp_tolerance) + "°C below setpoint.")
          print (now, status_string)
          htrtoggle(2)
        if seconds%idletimeout <= 1:
          print (now, status_string)
      if seconds%updatetimeout <= 1: 
        print (now, status_string)
      else:
        print ('{0:.1f}'.format(seconds%idletimeout), "    ", end='\r')

      wait_time = (seconds%1)
      time.sleep(1.5-wait_time)		# sleep until next half second
      
def drawstatus(element):	# Draw mode 0 (status screen)
#    print ("refreshing screen element ", element)
    global latest_weather, stemp, shumidity, target_temp, setpoint, htrstatus, displayed_time, blinker
								# 0 - Heater Status
    if element == 0:
      mylcd.lcd_display_string(htrstatus.ljust(10),1)
								# 1 - Time
    elif element == 1:
      displayed_time = datetime.datetime.now()
      hour = displayed_time.hour
      minute = displayed_time.minute
      localtime = str(displayed_time)[11:16]
      mylcd.lcd_display_string(str(localtime).rjust(10),1, 10)
      if drawlist[1] == 2:			# blink colon off
        if blinker == False:
          mylcd.lcd_display_string(" ",1, 17)
          blinker = True
        else:					# blink colon back on
          mylcd.lcd_display_string(":",1, 17)
          blinker = False
								# 2 - Temperature setting
    elif element == 2:
      tt = '{0:.1f}'.format(target_temp) + chr(223) + "C"
      tts = '{0:.1f}'.format(setpoint) + chr(223) + "C"
      mylcd.lcd_display_string(tts.center(10) + "(" + tt.center(8) + ")", 2)
								# 3 - Sensor data
    elif element == 3:
      if stemp == None:
         sensortemp = 0
      else:
         sensortemp = stemp
      sensortemperature = '{0:.2f}'.format(sensortemp) + chr(223) + "C"
      sensorhumidity = '{0:.0f}'.format(shumidity) + "%"
      mylcd.lcd_display_string(sensortemperature.ljust(10),3)
      mylcd.lcd_display_string(sensorhumidity.ljust(10), 4)
								# 4 - Weathercom data
    elif element == 4:
      if latest_weather == 0:
        outtemp = '-.-' + chr(223) +"C"
        cc = "N/A"
        outhumidity = "---%"
      else:
        outtempraw = int(latest_weather['current_conditions'] ['temperature'])
        outtemp = '{0:.1f}'.format(outtempraw) + chr(223) +"C"
        cc = latest_weather['current_conditions']['text']
        outhumidity = latest_weather['current_conditions']['humidity'] + "%"

      mylcd.lcd_display_string(outtemp.rjust(10), 3, 10)
      mylcd.lcd_display_string(outhumidity.rjust(10), 4, 10)
    return

# Draw mode 1 (weather screen)
def drawweather():
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

    mylcd.lcd_display_string(dayofweek[0:3] + " " + date.ljust(6), 1)
    mylcd.lcd_display_string("High".center(9) + "|" + "Low".center(10), 2)
    mylcd.lcd_display_string(high.center(9) + "|" + low.center(10), 3)
    mylcd.lcd_display_string(sensortemperature.ljust(10) + outtemp.rjust(10), 4)
    return

def redraw():
    global uimode, drawlist, displayed_time, blinker
    while True:
      if not toggledisplay:
          mylcd.lcd_clear()
          mylcd.backlight(0)
          return
      elif uimode == 0:
          for i in range(0, len(drawlist)):
            if drawlist[i]:
              drawstatus(i)
              drawlist[i] = False
              time.sleep(0.01)
      else:
          drawweather()

      now = datetime.datetime.now()

      if (now - displayed_time) > datetime.timedelta(seconds = 30):
          drawlist[1] = True
      elif (now - displayed_time) >= datetime.timedelta(seconds = 1):
        drawlist[1] = 2
    time.sleep(refreshrate)
    
def ui_input():
  global tt_in, setpoint, setback, target_temp, drawlist
  if setpoint+tt_in >= 0 <= 30:
    setpoint += tt_in
  tt_in=0
  target_temp = setpoint + setback
  drawlist[2] = True    

# Define rotary actions depending on current mode
def rotaryevent(event):
      ui_inputthread = threading.Thread(target=ui_input)
      ui_inputthread.setDaemon(True)
      global uimode, drawlist
      if uimode == 0:
        global tt_in
        if event == 1:
            tt_in += 0.05
            playtone(1)

        elif event == 2:
            tt_in -= 0.05
            playtone(2)
        ui_input()

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
        global uimode, drawlist
        if event == RotaryEncoder.CLOCKWISE:
            rotaryevent(1)
        elif event == RotaryEncoder.ANTICLOCKWISE:
            rotaryevent(2)
        elif event == RotaryEncoder.BUTTONUP:
            if uimode == 0:
              uimode = 1
            else:
              uimode = 0
              drawlist[0],drawlist[2],drawlist[3],drawlist[4]=True,True,True,True
            playtone(3)
        elif event == RotaryEncoder.BUTTONDOWN:
            playtone(4)
        return

# Define the switch
rswitch = RotaryEncoder(rotaryA,rotaryB,rotarybutton,switch_event)


schedulethread = threading.Thread(target=checkschedule)
sensorthread = threading.Thread(target=smoothsensordata, args=(5,2))  # (no. of samples, period time)
thermostatthread = threading.Thread(target=thermostat)
displaythread = threading.Thread(target=redraw)

weatherthread = threading.Thread(target=getweather)
weatherthread.setDaemon(True)
sensorthread.setDaemon(True)
thermostatthread.setDaemon(True)
schedulethread.setDaemon(True)

sensorthread.start()
schedulethread.start()
weatherthread.start()
displaythread.start()
time.sleep(4)
thermostatthread.start()

while run:
  time.sleep(0.5)

print ("Aborting...")

if htrstatus != htrstate[0]:
  print("Cooling down elements before turning off blower...")
  htrtoggle(3)
  time.sleep(80)

toggledisplay=False
displaythread.join()
GPIO.cleanup()
p.stop()
print(datetime.datetime.now(), "EXIT program exited.")
