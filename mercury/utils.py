from RPi import GPIO

import atexit
import copy
import json
import logging
import serial
import time

from logging import critical, error, warning, info, debug
from os import environ, path


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

    except:
        error("Failed to start serial connection.  The program will exit.")
        raise

    else:
        atexit.register(ser.close)
        return ser


def log_thread_start(func, thread):
    func("Started thread %s [%s]."
         % (thread.name, thread.native_id))


def get_config_file():
    '''Determine config file location.
    This code will use the config file indicated by $MERCURY_CONFIG,
    otherwise it defaults to a sensible path in $XDG_CONFIG_HOME,
    and if this is also unset, it defers to ~/.config/mercury.
    '''
    config_file = environ.get('MERCURY_CONFIG')

    if config_file is None:
        base_path = environ.get('XDG_CONFIG_HOME',
                                path.expanduser('~/.config'))
        config_file = path.join(base_path, 'mercury')

    info("Using config file: %s" % config_file)
    return config_file


def load_settings(config_file):
    with open(config_file, 'r') as f:
        config = json.load(f)

    return config


# Save config data
def save_settings(config, config_file, setpoint):
    '''Save configuration data'''

    savesetpoint = '{0:.2f}'.format(setpoint)
    saveconfig = copy.copy(config)
    saveconfig['setpoint'] = savesetpoint

    with open(config_file, 'w') as f:
        json.dump(saveconfig, f)

    info("Settings saved to %s. Setpoint: %s°C"
         % (config_file, str(savesetpoint)))


def setup_playtone(speaker_pin, magic_number=600):
    try:
        GPIO.setup(speaker_pin, GPIO.OUT)

        p = GPIO.PWM(speaker_pin, magic_number)
        p.start(0)
    except:
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
