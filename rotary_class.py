#!/usr/bin/python
#-------------------------------------------------------------------------------
# FileName:     Rotary_Encoder-1a.py
# Purpose:      This program decodes a rotary encoder switch.
#

#
# Note:         All dates are in European format DD-MM-YY[YY]
#
# Author:       Paul Versteeg
#
# Created:      23-Nov-2015
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>
#-------------------------------------------------------------------------------

import RPi.GPIO as GPIO
from time import sleep

class RotaryEncoder:
  
  CLOCKWISE=1
  ANTICLOCKWISE=2
  BUTTONDOWN=3
  BUTTONUP=4

  # GPIO Ports

  def __init__(self,pinA,pinB,button,callback):
    
    self.pinA = pinA
    self.pinB = pinB
    self.button = button
    self.callback = callback    

    GPIO.setwarnings(True)

    # Use the Raspberry Pi BOARD pins
    GPIO.setmode(GPIO.BOARD)

    # define the Encoder switch inputs
    GPIO.setup(self.pinA, GPIO.IN) # pull-ups are too weak, they introduce noise
    GPIO.setup(self.pinB, GPIO.IN)
    GPIO.setup(self.button, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    # setup an event detection thread for the A encoder switch
    GPIO.add_event_detect(self.pinA, GPIO.RISING, callback=self.rotation_decode, bouncetime=2) # bouncetime in mSec

    # setup an event detection thread for the button switch
    GPIO.add_event_detect(self.button, GPIO.BOTH, callback=self.button_event, bouncetime=3) # bouncetime in mSec

    return


  def rotation_decode(self,switch):

    sleep(0.002) # extra 2 mSec de-bounce time

    # read both of the switches
    Switch_A = GPIO.input(self.pinA)
    Switch_B = GPIO.input(self.pinB)

    if (Switch_A == 1) and (Switch_B == 0) : # A then B ->
        #counter += 1
        #print ("direction -> ")
        event=self.CLOCKWISE
        self.callback(event)
      
          # at this point, B may still need to go high, wait for it
        while Switch_B == 0:
            Switch_B = GPIO.input(self.pinB)
        # now wait for B to drop to end the click cycle
        while Switch_B == 1:
            Switch_B = GPIO.input(self.pinB)
        
    elif (Switch_A == 1) and (Switch_B == 1): # B then A <-
        #counter -= 1
        #print ("direction <- ")
        event=self.ANTICLOCKWISE
        self.callback(event)

          # A is already high, wait for A to drop to end the click cycle
        while Switch_A == 1:
            Switch_A = GPIO.input(self.pinA)

    else: # discard all other combinations
        return

  # Push button event
  def button_event(self,button):
      if GPIO.input(button):
          event = self.BUTTONUP
      else:
          event = self.BUTTONDOWN
      self.callback(event)
      return

# Get a switch state
  def getSwitchState(self, switch):
    return GPIO.input(switch)
