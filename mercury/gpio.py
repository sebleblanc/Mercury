from RPi import GPIO
from rotary_class import RotaryEncoder

import atexit

from logging import critical, info, debug

ROTARY_A = 7
ROTARY_B = 11
BUTTON = 13

GPIO_DEFAULT_INPUTS = {
    'RotaryA': ROTARY_A,
    'RotaryB': ROTARY_B,
    'Button': BUTTON,
    # 'Reset', 22,
}

GPIO_DEFAULT_OUTPUTS = {}

_DEFAULT = object()


def setup_gpio(inputs=_DEFAULT, outputs=_DEFAULT):
    if inputs is _DEFAULT:
        inputs = GPIO_DEFAULT_INPUTS

    if outputs is _DEFAULT:
        outputs = GPIO_DEFAULT_OUTPUTS

    debug('Setting GPIO modes...')

    atexit.register(GPIO.cleanup)

    try:
        GPIO.setmode(GPIO.BOARD)

        for x in inputs:
            GPIO.setup(inputs[x], GPIO.IN)

        for x in outputs:
            GPIO.setup(outputs[x], GPIO.OUT)

    except:
        critical('GPIO init failed.  The program will exit.')
        raise

    # Inputs
    msg = ' '.join('{}={}'.format(key, value)
                   for key, value in inputs.items())

    info('Set GPIO inputs: %s' % msg)

    # Outputs
    msg = ' '.join('{}={}'.format(key, value)
                   for key, value in outputs.items())
    info('Set GPIO outputs: %s' % msg)


# This is the event callback routine to handle events
def switch_event(callback, event):
    if event == RotaryEncoder.CLOCKWISE:
        callback(1)
    elif event == RotaryEncoder.ANTICLOCKWISE:
        callback(2)
