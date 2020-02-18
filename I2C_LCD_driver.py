# -*- coding: utf-8 -*-
# Original code found at:
# https://gist.github.com/DenisFromHR/cc863375a6e19dce359d

"""
Compiled, mashed and generally mutilated 2014-2015 by Denis Pleic
Made available under GNU GENERAL PUBLIC LICENSE

# Modified Python I2C library for Raspberry Pi
# as found on http://www.recantha.co.uk/blog/?p=4849
# Joined existing 'i2c_lib.py' and 'lcddriver.py' into a single library
# added bits and pieces from various sources
# By DenisFromHR (Denis Pleic)
# 2015-02-10, ver 0.1

"""

import smbus
from time import sleep


# i2c bus (0 -- original Pi, 1 -- Rev 2 Pi)
I2CBUS = 1

# LCD Address
ADDRESS = 0x27


class I2CDevice:
    def __init__(self, addr, port=I2CBUS):
        self.addr = addr
        self.bus = smbus.SMBus(port)

    def write_cmd(self, cmd):
        '''Write a single command'''

        self.bus.write_byte(self.addr, cmd)
        sleep(0.0001)

    def write_cmd_arg(self, cmd, data):
        '''Write a command and argument'''

        self.bus.write_byte_data(self.addr, cmd, data)
        sleep(0.0001)

    def write_block_data(self, cmd, data):
        '''Write a block of data'''

        self.bus.write_block_data(self.addr, cmd, data)
        sleep(0.0001)

    def read(self):
        '''Read a single byte'''

        return self.bus.read_byte(self.addr)

    def read_data(self, cmd):
        '''Read'''

        return self.bus.read_byte_data(self.addr, cmd)

    def read_block_data(self, cmd):
        '''Read a block of data'''

        return self.bus.read_block_data(self.addr, cmd)


# commands
LCD_CLEARDISPLAY = 0x01
LCD_RETURNHOME = 0x02
LCD_ENTRYMODESET = 0x04
LCD_DISPLAYCONTROL = 0x08
LCD_CURSORSHIFT = 0x10
LCD_FUNCTIONSET = 0x20
LCD_SETCGRAMADDR = 0x40
LCD_SETDDRAMADDR = 0x80

# flags for display entry mode
LCD_ENTRYRIGHT = 0x00
LCD_ENTRYLEFT = 0x02
LCD_ENTRYSHIFTINCREMENT = 0x01
LCD_ENTRYSHIFTDECREMENT = 0x00

# flags for display on/off control
LCD_DISPLAYON = 0x04
LCD_DISPLAYOFF = 0x00
LCD_CURSORON = 0x02
LCD_CURSOROFF = 0x00
LCD_BLINKON = 0x01
LCD_BLINKOFF = 0x00

# flags for display/cursor shift
LCD_DISPLAYMOVE = 0x08
LCD_CURSORMOVE = 0x00
LCD_MOVERIGHT = 0x04
LCD_MOVELEFT = 0x00

# flags for function set
LCD_8BITMODE = 0x10
LCD_4BITMODE = 0x00
LCD_2LINE = 0x08
LCD_1LINE = 0x00
LCD_5x10DOTS = 0x04
LCD_5x8DOTS = 0x00

# flags for backlight control
LCD_BACKLIGHT = 0x08
LCD_NOBACKLIGHT = 0x00

En = 0b00000100  # Enable bit
Rw = 0b00000010  # Read/Write bit
Rs = 0b00000001  # Register select bit


class LCD:
    def __init__(self):
        self.device = I2CDevice(ADDRESS)

        self.write(0x03)
        self.write(0x03)
        self.write(0x03)
        self.write(0x02)

        self.write(LCD_FUNCTIONSET | LCD_2LINE | LCD_5x8DOTS | LCD_4BITMODE)
        self.write(LCD_DISPLAYCONTROL | LCD_DISPLAYON)
        self.write(LCD_CLEARDISPLAY)
        self.write(LCD_ENTRYMODESET | LCD_ENTRYLEFT)
        sleep(0.2)

    def strobe(self, data):
        '''clocks EN to latch command'''

        self.device.write_cmd(data | En | LCD_BACKLIGHT)
        sleep(.0005)
        self.device.write_cmd(((data & ~En) | LCD_BACKLIGHT))
        sleep(.0001)

    def write_four_bits(self, data):
        self.device.write_cmd(data | LCD_BACKLIGHT)
        self.strobe(data)

    def write(self, cmd, mode=0):
        '''write a command to lcd'''

        self.write_four_bits(mode | (cmd & 0xF0))
        self.write_four_bits(mode | ((cmd << 4) & 0xF0))

    def write_char(self, charvalue, mode=1):
        '''write a character to lcd (or character rom)

        0x09: backlight | RS=DR< works!

        '''
        self.write_four_bits(mode | (charvalue & 0xF0))
        self.write_four_bits(mode | ((charvalue << 4) & 0xF0))

    def display_string(self, string, line=1, pos=0):
        '''put string function with optional char positioning'''

        if line == 1:
            pos_new = pos
        elif line == 2:
            pos_new = 0x40 + pos
        elif line == 3:
            pos_new = 0x14 + pos
        elif line == 4:
            pos_new = 0x54 + pos

        self.write(0x80 + pos_new)

        for char in string:
            self.write(ord(char), Rs)

    def clear(self):
        '''clear lcd and set to home'''

        self.write(LCD_CLEARDISPLAY)
        self.write(LCD_RETURNHOME)

    def backlight(self, state):
        '''define backlight on/off

            on = lcd.backlight(1)
            off= lcd.backlight(0)
        '''
        if state == 1:
            self.device.write_cmd(LCD_BACKLIGHT)
        elif state == 0:
            self.device.write_cmd(LCD_NOBACKLIGHT)

    def load_custom_chars(self, fontdata):
        '''add custom characters (0 - 7)'''

        self.write(0x40)
        for char in fontdata:
            for line in char:
                self.write_char(line)
