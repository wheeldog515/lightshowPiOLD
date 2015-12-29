#!/usr/bin/env python
#
# Licensed under the BSD license.  See full license in LICENSE file.
# http://www.lightshowpi.com/
#
# Author: Todd Giles (todd@lightshowpi.com)
# Author: Chris Usey (chris.usey@gmail.com)
"""Preshow functionality for the lightshows.

Your lightshow can be configured to have a "preshow" before each individual song is
played.  See the default configuration file for more details on configuring your 
preshow.

Sample usage (to test your preshow configuration):
sudo python preshow.py
"""

import logging
import time

import configuration_manager as cm
import hardware_controller as hc


class Preshow:
    """The Preshow class handles all pre-show logic

    Typical usage to simply play the default configured preshow:

    Preshow().execute()
    """
    def __init__(self):
        self.config = cm.lightshow()['preshow']

    def set_config(self, config):
        """Set a new configuration to use for the preshow"""
        self.config = config
    
    def execute(self):
        """Execute the pre-show as defined by the current config"""
        for transition in self.config['transitions']:
            if transition['type'].lower() == 'on':
                hc.turn_on_lights(True)
            else:
                hc.turn_off_lights(True)

            logging.debug('Transition to ' + transition['type'] + ' for '
                          + str(transition['duration']) + ' seconds')

            if 'channel_control' in transition:
                channel_control = transition['channel_control']

                for key in channel_control.keys():
                    mode = key
                    channels = channel_control[key]

                    for channel in channels:
                        if mode == 'on':
                            hc.turn_on_light(int(channel) - 1, 1)
                        elif mode == 'off':
                            hc.turn_off_light(int(channel) - 1, 1)
                        else:
                            logging.error("Unrecognized channel_control mode defined in "
                                          "preshow_configuration " + str(mode))

            time.sleep(transition['duration'])


if __name__ == "__main__":
    Preshow().execute()
