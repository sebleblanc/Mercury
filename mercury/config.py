from configparser import ConfigParser
from logging import error, warning, info, debug
from os import environ, path


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
        config_file = path.join(base_path, 'mercury.cfg')

    info("Using config file: %s" % config_file)
    return config_file


def load_settings(config_file):
    config_defaults = {'Setpoint': '20'}
    config = ConfigParser(defaults=config_defaults)
    default_setpoint = config['DEFAULT']['Setpoint']

    if path.isfile(config_file):
        debug("Loading settings from %s..." % config_file)
        config.read(config_file)
    else:
        warning("Config file not found.")

    if not config.has_section('User'):
        config.add_section('User')
    if not config.has_option('User', 'Setpoint'):
        config.set('User', 'Setpoint', default_setpoint)

    try:
        config.getfloat('User', 'setpoint')
    except BaseException as e:
        error("Invalid setpoint value in config file. (%s)"
              % e)
        config.set('User', 'Setpoint', default_setpoint)
    return config


def save_settings(config, config_file, setpoint):
    '''Save configuration data'''

    setpoint_float = '{0:.2f}'.format(setpoint)
    setpoint_to_save = str(setpoint_float)

    config['User']['Setpoint'] = setpoint_to_save

    with open(config_file, 'w') as f:
        config.write(f)
    info("Settings saved to %s. Setpoint: %s°C"
         % (config_file, setpoint_to_save))
