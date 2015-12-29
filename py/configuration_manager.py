#!/usr/bin/env python
#
# Licensed under the BSD license.  See full license in LICENSE file.
# http://www.lightshowpi.com/
#
# Author: Todd Giles (todd@lightshowpi.com)
#
# Refactor the configuration manager into a configuration manager class (to remove
# the extensive use of globals currently used).
# Add a main and allow running configuration manager alone to view the current
# configuration, and potentially edit it.
"""Configuration management for the lightshow.

Configuration files are all located in the <homedir>/config directory. This file contains tools to
manage these configuration files.
"""
# The home directory and configuration directory for the application.

import ConfigParser
import ast
import datetime
import fcntl
import logging
import os
import sys
import warnings
import json


HOME_DIR = os.getenv("SYNCHRONIZED_LIGHTS_HOME")
if not HOME_DIR:
    print("Need to setup SYNCHRONIZED_LIGHTS_HOME environment variable, "
          "see readme")
    sys.exit()
CONFIG_DIR = HOME_DIR + '/config'
LOG_DIR = HOME_DIR + '/logs'

# Load configuration file, loads defaults from config directory, and then
# overrides from the same directory cfg file, then from /home/pi/.lights.cfg
# and then from ~/.lights.cfg (which will be the root's home).
CONFIG = ConfigParser.RawConfigParser(allow_no_value=True)
CONFIG.readfp(open(CONFIG_DIR + '/defaults.cfg'))
CONFIG.read([CONFIG_DIR + '/overrides.cfg', '/home/pi/.lights.cfg',
             os.path.expanduser('~/.lights.cfg')])


def _as_dict(section):
    """Return a dictionary from a configuration section."""
    return dict(x for x in CONFIG.items(section))


def _as_list(list_str, delimiter=','):
    """Return a list of items from a delimited string (after stripping whitespace)."""
    return [str.strip(item) for item in list_str.split(delimiter)]


# Retrieve hardware configuration
_HARDWARE_CONFIG = {}


def hardware():
    """Retrieves the hardware configuration, loading and parsing it from a file if necessary."""
    global _HARDWARE_CONFIG
    if len(_HARDWARE_CONFIG) == 0:
        _HARDWARE_CONFIG = _as_dict('hardware')

        """Devices"""
        devices = dict()

        try:
            devices = json.loads(_HARDWARE_CONFIG['devices'])
        except Exception as e:
            logging.error("devices not defined or not in JSON format." + str(e))

        _HARDWARE_CONFIG["devices"] = devices

    return _HARDWARE_CONFIG


# Retrieve light show configuration
_LIGHTSHOW_CONFIG = {}


def lightshow():
    """Retrieves the lightshow configuration, loading and parsing it from a file if necessary."""
    global _LIGHTSHOW_CONFIG
    if len(_LIGHTSHOW_CONFIG) == 0:
        _LIGHTSHOW_CONFIG = _as_dict('lightshow')

        _LIGHTSHOW_CONFIG['audio_in_channels'] = CONFIG.getint('lightshow', 'audio_in_channels')
        _LIGHTSHOW_CONFIG['audio_in_sample_rate'] = CONFIG.getint('lightshow',
                                                                  'audio_in_sample_rate')

        preshow = dict()
        preshow['transitions'] = []

        """ Check to see if we are using the DEPRECATED preshow setting first,
        if not, use the new preshow_configuration setting"""
        if 'preshow' in _LIGHTSHOW_CONFIG:
            logging.error("[DEPRECATED: preshow] the preshow option has been DEPRECATED in "
                          "favor of preshow_configuration, please update accordingly")
            # Parse out the preshow and replace it with the preshow CONFIG
            # consiting of transitions to on or off for various durations.
            for transition in _as_list(_LIGHTSHOW_CONFIG['preshow']):
                try:
                    transition = transition.split(':')
                    if len(transition) == 0 or (len(transition) == 1 and len(transition[0]) == 0):
                        continue
                    if len(transition) != 2:
                        logging.error("[DEPRECATED:preshow] Preshow transition definition should be"
                                      " in the form [on|off]:<duration> - " + ':'.join(transition))
                        continue
                    transition_config = dict()
                    transition_type = str(transition[0]).lower()
                    if transition_type not in ['on', 'off']:
                        logging.error("[DEPRECATED: preshow] Preshow transition transition_"
                                      "type must either 'on' or 'off': " + transition_type)
                        continue
                    transition_config['type'] = transition_type
                    transition_config['duration'] = float(transition[1])
                    preshow['transitions'].append(transition_config)
                except Exception as e:
                    logging.error("[DEPRECATED: preshow] Invalid preshow transition "
                                  "definition: " + ':'.join(transition))
                    logging.error(e)
        elif 'preshow_configuration' in _LIGHTSHOW_CONFIG:
            try:
                temp = json.loads(_LIGHTSHOW_CONFIG['preshow_configuration']) 
                if temp:
                    preshow = temp
            except Exception as e:
                logging.error("Preshow_configuration not defined or not in JSON format." + str(e))
        
        _LIGHTSHOW_CONFIG['preshow'] = preshow

    return _LIGHTSHOW_CONFIG
