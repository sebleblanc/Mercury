from RPi import GPIO

import atexit
import logging
import serial
import time


from functools import wraps
from logging import critical, error, info, debug
from threading import current_thread as get_current_thread


def try_function(on_failure, method, *args, **kwargs):
    '''Attempt to run method, passing arguments *args and **kwargs. If it
    fails, defer to on_failure callback

    '''

    try:
        method(*args, **kwargs)
    except Exception:
        logging.exception("Failed to run function %s.%s"
                          % (method.__module__, method.__name__))
        on_failure()


def setup_logging(**kwargs):
    '''Setup logging so that it includes timestamps.'''

    kwargs.setdefault('force', True)
    kwargs.setdefault('level', logging.INFO)
    kwargs.setdefault('format', '%(levelname)-8s %(message)s')
    kwargs.setdefault('datefmt', '%Y-%m-%d %H:%M:%S')

    logging.basicConfig(**kwargs)


def setup_serial(device='/dev/ttyUSB0', baudrate=9600):
    debug("Getting heater serial connection...")

    try:
        ser = serial.Serial(device, baudrate, timeout=1)
        info("Heater connected via serial connection.")

    except BaseException:
        error("Failed to start serial connection.  The program will exit.")
        raise

    else:
        atexit.register(ser.close)
        return ser


def logged_thread_start(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        thread = get_current_thread()
        info("Started thread %s [%s]."
             % (thread.name, thread.native_id))
        return func(*args, **kwargs)

    return wrapper


def setup_playtone(speaker_pin, magic_number=600):
    try:
        GPIO.setup(speaker_pin, GPIO.OUT)

        p = GPIO.PWM(speaker_pin, magic_number)
        p.start(0)
    except BaseException:
        critical('Could not initialize PWM')
        raise

    playtone.p = p
    atexit.register(destroy_playtone, p)


def destroy_playtone(p):
    p.stop()


def playtone(tone):
    p = getattr(playtone, 'p', None)

    if not p:
        error('Speaker must be initialized before use!')
        return

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
        for i in range(0, 3):
            playtone(3)
            time.sleep(0.1)
