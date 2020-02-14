import atexit
import copy
import json
import logging
import time

from os import environ, path

from RPi import GPIO


def setup_logging(**kwargs):
    '''Setup logging so that it includes timestamps.'''

    kwargs.setdefault('level', logging.INFO)
    kwargs.setdefault('format', '%(levelname)-8s %(message)s')
    kwargs.setdefault('datefmt', '%Y-%m-%d %H:%M:%S')

    logging.basicConfig(**kwargs)

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

    logging.info("Using config file: %s" % config_file)
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

    logging.info("Settings saved to %s. Setpoint: %s°C"
                 % (config_file, str(setpoint)))


def setup_playtone(speaker_pin, magic_number=600):
    try:
        GPIO.setup(speaker_pin, GPIO.OUT)

        p = GPIO.PWM(speaker_pin, magic_number)
        p.start(0)
    except:
        logging.critical('Could not initialize PWM')
        raise

    playtone.p = p
    atexit.register(destroy_playtone, p)


def destroy_playtone(p):
    p.stop()


def playtone(tone):
    p = getattr(playtone, 'p', None)

    if not p:
        logging.error('Speaker must be initialized before use!')
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
