import time
from rotary_class import RotaryEncoder
import RPi.GPIO as GPIO
import random

# Define GPIO inputs
PIN_A = 11
PIN_B = 13
BUTTON = 15

GPIO.setmode(GPIO.BOARD)
GPIO.setup(12, GPIO.OUT)

tone=GPIO.PWM(12, 2000)
tone.start(0)


# This is the event callback routine to handle events
def switch_event(event):
        if event == RotaryEncoder.CLOCKWISE:
          print ("--->>>")
        elif event == RotaryEncoder.ANTICLOCKWISE:
          print ("<<<---")
        elif event == RotaryEncoder.BUTTONDOWN:
          print ("  __   ")
        elif event == RotaryEncoder.BUTTONUP:
          print ("  [^]  ")

        tone.ChangeDutyCycle(100)
        time.sleep(0.02)
        tone.ChangeDutyCycle(0)
        return

# Define the switch
rswitch = RotaryEncoder(PIN_A,PIN_B,BUTTON,switch_event)




try:
  while 1:
    time.sleep(0.1)
except KeyboardInterrupt:
    pass
tone.stop()
GPIO.cleanup()
