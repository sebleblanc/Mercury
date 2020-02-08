from __future__ import print_function
from rotary_class import RotaryEncoder
from bme280 import readBME280All
from math import floor
from os import environ, path
import I2C_LCD_driver as i2c_charLCD
import RPi.GPIO as GPIO
import copy, time, requests, json, string, threading, csv, datetime, os, signal, sys, serial, struct

# Define GPIO inputs
rotaryA = 7
rotaryB = 11
rotarybutton = 13
resetbutton = 22

# Define GPIO outputs
speaker = 12

# Arduino Serial connect
ser = serial.Serial('/dev/ttyUSB0',  9600, timeout = 1)

# Get config file
#   This code will use the config file indicated by $MERCURY_CONFIG,
#   otherwise it defaults to a sensible path in $XDG_CONFIG_HOME,
#   and if this is also unset, it defers to ~/.config/mercury.
def get_config_file():
    config_file = environ.get('MERCURY_CONFIG')

    if config_file is None:
        base_path = environ.get('XDG_CONFIG_HOME', path.expanduser('~/.config'))
        config_file = path.join(base_path, 'mercury')

    return config_file

configfile = get_config_file()

# Save config data
def savesettings():
    global config, configfile, setpoint
    savesetpoint = '{0:.2f}'.format(setpoint)
    saveconfig = copy.copy(config)
    saveconfig['setpoint'] = savesetpoint
    with open(configfile, 'w') as f:
        json.dump(saveconfig, f)

# Reset button event
#def reset_event(resetbutton):
#    global drawlist
#    if GPIO.input(resetbutton):
#      mylcd.__init__()
#      time.sleep(2)
#      playtone(5)
#      time.sleep(1)
#      drawlist[0],drawlist[1],drawlist[2],drawlist[3],drawlist[4]=True,True,True,True,True
#    else:
#      playtone(1)
#    return

GPIO.setmode(GPIO.BOARD)
GPIO.setup(rotaryA, GPIO.IN)
GPIO.setup(rotaryB, GPIO.IN)
GPIO.setup(rotarybutton, GPIO.IN)
#GPIO.setup(resetbutton, GPIO.IN, pull_up_down = GPIO.PUD_UP)
GPIO.setup(speaker, GPIO.OUT)
#GPIO.add_event_detect(resetbutton, GPIO.BOTH, callback=reset_event, bouncetime=3000)

# Start char LCD
mylcd = i2c_charLCD.lcd()
mylcd.backlight(1)

# Start PWM speaker
p = GPIO.PWM(speaker, 600)
p.start(0)


# Defaults
setpoint = 20   # in celsius
sensortimeout = 300
heartbeatinterval = 30
temp_tolerance = 1.8
refreshrate = 0.01 		# in seconds
target_temp = setpoint

# Load saved data
with open(configfile, 'r') as f:
    config = json.load(f)
setpoint = float(config['setpoint'])
weatherapikey = config['weatherapikey']
locationid = config['locationid']

# Initialiaze variables
tt_in,setback,forecast_day,latest_weather,spressure,shumidity = 0,0,0,0,0,0
blinker,run,toggledisplay,refetch = True,True,True,True
htrstate = ['Off', 'Fan only', 'Low Heat', 'Full Heat']
htrstatus = htrstate[0]

drawlist = [True, True, True, True, True]
#	0 Heater status
#	1 Time
#	2 Setpoint
#	3 Sensor data
#	4 Weather data

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
  elif tone == 5:
    for i in range(0,3):
      playtone(3)
      time.sleep(0.1)

# Get weather from weather API
def getweather():
    global latest_weather, weatherapikey, locationid
    while True:
      try:
        #print (datetime.datetime.now(),"updating weather data...")
        owmurl='http://api.openweathermap.org/data/2.5/weather?appid=' + weatherapikey + '&id=' + locationid + '&units=metric'
        response=requests.get(owmurl)
        latest_weather=response.json()
        time.sleep(3)
      except:
        print (datetime.datetime.now(),"ERROR: weather update failure")
      finally:
        #print (datetime.datetime.now(),"weather updated from OpenWeatherMap")
        drawlist[4] = True
        time.sleep(900)

def fetchhtrstate():
  output = (chr(9+48)+'\n').encode("utf-8")
  #print ("writing out", output)
  ser.write(output)
  time.sleep(0.1)
  response = ser.readline()
  if response != '':
      state = (struct.unpack('>BBB', response)[0]-48)

  else:
      state = -1
  #print ("returning state", state)
  return state


def heartbeat():
    global htrstatus, htrstate, drawlist, stemp, lhs, target_temp, refetch, heartbeatinterval
    lastfetch = datetime.datetime.now()
    while True:
      while refetch:
        now = datetime.datetime.now()
        previousstatus = htrstatus
        getstatus = -1
        #print ("trying to refetch...")
        try:
          getstatus = fetchhtrstate()
          #print ("-- got status", getstatus)
          time.sleep(0.1)
          if getstatus > -1:
            lastfetch = datetime.datetime.now()
            if htrstatus == htrstate[getstatus]:
                #print(now, "-- no state change detected")
                pass
            else:
              drawlist[0] = True		# -> redraw the status part of screen and remember/reset time, heater state, and temperature
              htrstatus = htrstate[getstatus]
              print (now, '{0:.2f}'.format(stemp) + "°C", "->", '{0:.2f}'.format(target_temp) + "°C.  Was", previousstatus + ", now is", htrstatus + ".")
              lhs=[now, htrstatus, stemp]
          else:
            print (now, "-- ERROR: got invalid status",getstatus)
        except:
          print (now, "-- WARNING: failed to contact arduino!")
        finally:
            refetch = False
            time.sleep(2)

      while not refetch:
        now = datetime.datetime.now()
        if (now-lastfetch).total_seconds() >= heartbeatinterval:
          refetch = True
        else :
          time.sleep(2)

# Average sensor readings: takes number of samples(samples) over a period of time (refresh)
def smoothsensordata(samples,refresh):
    global stemp,spressure,shumidity,sensortimeout,run
    sensortime = datetime.datetime.now()
    while run:
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
          run = False
      finally:
        drawlist[3] = True
        time.sleep(5)

def checkschedule():	# 0:MON 1:TUE 2:WED 3:THU 4:FRI 5:SAT 6:SUN
    global setback, target_temp, setpoint, run
    while run:
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
    global htrstatus, htrstate, refetch, run
    refetch = True
    now = datetime.datetime.now()
    #print (now, "-- checking current status", refetch)
    while run and refetch:
        time.sleep(0.1)
        # add timouts here...
    now = datetime.datetime.now()
    if htrstatus == htrstate[state]:
        print(now, "-- WARNING: toggled",state, "but already set to", htrstatus)
    else:
        output = (chr(state+48)+'\n').encode("utf-8")
        ser.write(output)
        time.sleep(0.1)
        refetch = True
        #print (now, "-- sent state change to arduino:", state)
        #print ("waiting for refetch again...")
        while run and refetch:
          time.sleep(0.1)
        # ...and here...
        now = datetime.datetime.now()
        if htrstatus == htrstate[state]:
            print(now, "-- Toggle succeeded:",htrstatus)
        elif htrstatus == htrstate[1]:
            print(now, "-- Toggle resulted in:", htrstatus)
        else:
            print(now, "-- Toggle failed: got", htrstatus, "expected", htrstate[state])

def thermostat():
    global run, target_temp, setback, stemp, temp_tolerance, htrstatus, htrstate, lhs
    stage1min = 0.04		# minimum threshold (in °C/hour) under which we switch to stage 2
    stage2max = 0.5		# maximum threshold (in °C/hour) over which we switch to stage 1
    stage1timeout=10*60		# time (s) to wait before checking if we should change states
    stage1maxtime=60*60      # time until forced switch to stage 2
    stage2timeout=10*60
    fantimeout=0
    idletime=30*60       # time we shold hope to stay off for
    updatetimeout=600		# stdout updates and save settings

    displaythread.start()
    hvacthread.start()

    stemp = False
    sensorthread.start()
    while run and not stemp:
      time.sleep(1)

    while run and not htrstatus:
      time.sleep(1)

    lhs = [datetime.datetime.now(), htrstatus,  stemp] 	# endtime, last state, last temp

    schedulethread.start()
    weatherthread.start()
    ui_inputthread.start()

    time.sleep(3)

    while run:
      now = datetime.datetime.now()
      tdelta = now - lhs[0]
      seconds = tdelta.total_seconds()
      lasttime = lhs[0]
      lasttemp = lhs[2]
      status_string = htrstatus + ", " + '{0:.2f}'.format(stemp)+"°C , "+'{0:.2f}'.format(stemp-lasttemp) +  "°C since " + lasttime.strftime("%H:%M:%S") + " (" + '{0:.2f}'.format((stemp-lasttemp)/seconds*3600) + "°C/hr)"

			# Shut off the heater if temperature reached,
         		# unless the heater is already off (so we can continue to increase time delta counter to check timeouts)
      if stemp >= target_temp+(temp_tolerance/3) and htrstatus !=  htrstate[0] and htrstatus != htrstate[1]:
        print (now, "Temperature reached.")
        print (now, status_string)
        htrtoggle(0)

      elif htrstatus == htrstate[2]:		# Project temperature increase, if we will hit target temperature
#        print (int(stage1timeout-floor(seconds%stage1timeout)-1), "    Stage 1    ", end='\r')
        if seconds%stage1timeout <= 1:
          if stemp + (stemp - lasttemp) > target_temp:
            print (now, "Predicted target temperature in", '{0:.1f}'.format(stage1timeout/60), "minutes.")
            print (now, status_string)
          if seconds >= stage1maxtime:     # 	If we have been on stage 1 for too long -> go to stage 2
            print (now, "Low Heat is taking too long:",'{0:.2f}'.format(stemp - lasttemp),"°C since", lasttime.strftime("%H:%M:%S"), ", (", floor(seconds/60), "minutes ago.)")
            print (now, status_string)
            htrtoggle(3)
#          elif (stemp - lasttemp)*seconds < stage1min*3600:     # 	If heating too slowly -> go to stage 2
#            print (now, "Heating too slowly: (",(stemp - lasttemp)*seconds,"°C/hr ,min=", stage1min, "°C/hr)")
#            print (now, status_string)
#            htrtoggle(3)

      elif htrstatus == htrstate[3]:
#        print (int(stage2timeout-floor(seconds%stage2timeout)-1), "    Stage 2    ", end='\r')
        if seconds%stage2timeout <= 1:
          if stemp + (stemp - lasttemp) > target_temp:
            print (now, "Predicted target temperature in", floor(stage2timeout/60), "minutes.")
            print (now, status_string)
            #htrtoggle(2)
#          elif (stemp - lasttemp)*seconds >= stage2max*3600:    #       If heating too quickly -> stage 1.
#            print (now, "Heating too quickly: (", (stemp - lasttemp)*seconds, "°C/hr ,max=", stage2max, "°C/hr)")
#            print (now, status_string)
#            htrtoggle(2)

      elif htrstatus == htrstate[1]:
        pass
#        print (int(fantimeout-floor(seconds%fantimeout)-1), "    Fan    ", end='\r')
#        if seconds >= fantimeout:
#            print (now, status_string)
#            htrtoggle(0)

      elif htrstatus == htrstate[0] or htrstatus==htrstate[1]:		# If temperature falls under the threshold, turn on
            if stemp < target_temp - temp_tolerance:
              print (now, "Temperature more than", str(temp_tolerance) + "°C below setpoint.")
              if seconds > idletime:
                  htrtoggle(2)
              else:
                  htrtoggle(3)
              print (now, status_string)
      else:
        print (now, "ERROR: Bad heater status!", htrstatus, "not in", htrstate)

      if seconds%updatetimeout <= 1:
        print (now, status_string)
        savesettings()


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

      mylcd.lcd_display_string(tts.center(20), 2)
#      mylcd.lcd_display_string(tts.center(10) + "(" + tt.center(8) + ")", 2)
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
      try:
        outtempraw = int(latest_weather['main']['temp'])
        outtemp = '{0:.0f}'.format(outtempraw) + chr(223) +"C"
        cc = str(latest_weather['weather'][0]['description'])
        outhumidity = str(latest_weather['main']['humidity']) + "%"
      except:
        outtemp = '-.-' + chr(223) +"C"
        cc = "N/A"
        outhumidity = "---%"
      finally:
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

    outtempraw = int(latest_weather['main']['temp'])
    outtemp = '{0:.1f}'.format(outtempraw) + chr(223) +"C"
    cc = latest_weather['weather'][0]['description']
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
    global drawlist, displayed_time, blinker
    while True:
      if not toggledisplay:
          mylcd.lcd_clear()
          mylcd.backlight(0)
          return
      else:
          for i in range(0, len(drawlist)):
            if drawlist[i]:
              drawstatus(i)
              drawlist[i] = False
              time.sleep(0.01)

      now = datetime.datetime.now()

      if (now - displayed_time) > datetime.timedelta(seconds = 30):
          drawlist[1] = True
      elif (now - displayed_time) >= datetime.timedelta(seconds = 1):
        drawlist[1] = 2
    time.sleep(refreshrate)

def ui_input():
  global tt_in, setpoint, setback, target_temp, drawlist, run
  while True:
    if tt_in != 0:
      if setpoint+tt_in >= 0 <= 30:
          setpoint += tt_in
          target_temp = setpoint + setback
          drawlist[2] = True
      tt_in = 0
    time.sleep(0.3)

# Define rotary actions depending on current mode
def rotaryevent(event):
    global tt_in
    if event == 1:
        tt_in += 0.1
        playtone(1)
    elif event == 2:
        tt_in -= 0.1
        playtone(2)
    time.sleep(0.01)
    return

# This is the event callback routine to handle events
def switch_event(event):
        if event == RotaryEncoder.CLOCKWISE:
            rotaryevent(1)
        elif event == RotaryEncoder.ANTICLOCKWISE:
            rotaryevent(2)
        return

# Define the switch
rswitch = RotaryEncoder(rotaryA,rotaryB,rotarybutton,switch_event)

hvacthread = threading.Thread(target=heartbeat)
schedulethread = threading.Thread(target=checkschedule)
sensorthread = threading.Thread(target=smoothsensordata, args=(3,10))  # (no. of samples, period time)
thermostatthread = threading.Thread(target=thermostat)
ui_inputthread = threading.Thread(target=ui_input)
displaythread = threading.Thread(target=redraw)
weatherthread = threading.Thread(target=getweather)

weatherthread.setDaemon(True)
sensorthread.setDaemon(True)
hvacthread.setDaemon(True)
thermostatthread.setDaemon(True)
schedulethread.setDaemon(True)
ui_inputthread.setDaemon(True)

thermostatthread.start()

while run:
  time.sleep(0.5)

print ("Aborting...")

#if htrstatus != htrstate[0]:
#  print("Cooling down elements before turning off blower...")
#  htrtoggle(0)

savesettings()

toggledisplay=False
displaythread.join()
GPIO.cleanup()
ser.close()
p.stop()
print(datetime.datetime.now(), "EXIT: program exited.")
