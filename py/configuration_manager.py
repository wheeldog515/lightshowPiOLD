# !/usr/bin/env python
#
# Licensed under the BSD license.  See full license in LICENSE file.
# http://www.lightshowpi.com/
#
# Author: Todd Giles (todd@lightshowpi.com)
# Author: Tom Enos
"""
Configuration management for the lightshow.

Configuration files are all located in the <homedir>/config directory. This file contains tools to
manage these configuration files.
"""

import ConfigParser

try:
    import fcntl
except ImportError:
    import portalocker as fcntl

import json
import logging
import os
import platform
import sys
from collections import defaultdict
from collections import OrderedDict as dict

# The home directory and configuration directory for the application.
HOME_DIR = os.getenv("SYNCHRONIZED_LIGHTS_HOME")
if not HOME_DIR:
    if not "raspberrypi" in platform.uname():
        d = os.path.dirname(os.path.abspath(__file__))

        x = os.path.split(os.path.abspath(__file__))[0]

        p = x.split(os.sep)
        p = p[:-1]
        p1 = os.sep.join(p)
        HOME_DIR = p1

        #sys.exit(0)
    else:
        print("Need to setup SYNCHRONIZED_LIGHTS_HOME environment variable, "
              "see readme")
        sys.exit()

CONFIG_DIR = os.path.join(HOME_DIR, 'config')
LOG_DIR = os.path.join(HOME_DIR, 'logs')


class Configuration(object):
    def __init__(self):
        self.HOME_DIR = HOME_DIR
        self.CONFIG_DIR = os.path.join(HOME_DIR, 'config')
        self.LOG_DIR = os.path.join(HOME_DIR, 'logs')
        self.hardware_config = dict()
        self.network_config = dict()
        self.lightshow_config = dict()
        self.audio_processing_config = dict()
        self._SONG_LIST = None
        self.CONFIG = ConfigParser.RawConfigParser(allow_no_value=True)

        self.load_configs()

        # Load application state configuration file from CONFIG directory.
        self.STATE = ConfigParser.RawConfigParser()
        self.STATE_SECTION = 'do_not_modify'
        self.STATE_FILENAME = os.path.join(self.CONFIG_DIR, 'state.cfg')
        # Ensure state file has been created
        if not os.path.isfile(self.STATE_FILENAME):
            open(self.STATE_FILENAME, 'a').close()
        self.load_state()
        
    def save_config(self):
        with open(self.CONFIG_DIR + '/new_configuration.cfg', 'wb') as configfile:
            self.CONFIG.write(configfile)

    def set_option(self, section, option, value):
        self.CONFIG.set(str(section), str(option), str(value))

    def load_configs(self, per_song=None):
        """
        Load configuration file

        loads defaults from config directory, and then
        overrides from the same directory cfg file, then from /home/pi/.lights.cfg
        and then from ~/.lights.cfg (which will be the root's home).
        if per_song is specified loads these configs also

        :param per_song: string, path and filename of per song config
        """
        self.hardware_config = dict()
        self.network_config = dict()
        self.lightshow_config = dict()
        self.audio_processing_config = dict()

        default = os.path.join(self.CONFIG_DIR, 'defaults.cfg')
        overrides = os.path.join(self.CONFIG_DIR, 'overrides.cfg')

        self.CONFIG = ConfigParser.RawConfigParser(allow_no_value=True)
        self.CONFIG.readfp(open(default))
        self.CONFIG.read([overrides, '/home/pi/.lights.cfg',
                          os.path.expanduser('~/.lights.cfg')])
        if per_song:
            self.CONFIG.read([per_song])

        self.hardware()
        self.network()
        self.lightshow()
        self.audio_processing()

    def hardware(self):
        """
        Retrieves the hardware configuration

        loading and parsing it from a file if necessary.
        """
        for key, value in self.CONFIG.items('hardware'):
            self.hardware_config[key] = value

        self.hardware_config['gpio_pins'] = \
            [int(pin) for pin in self.hardware_config['gpio_pins'].split(',')]

        self.hardware_config['active_low_mode'] = self.CONFIG.getboolean('hardware',
                                                                         'active_low_mode')
        self.hardware_config['gpiolen'] = len(self.hardware_config['gpio_pins'])

        self.hardware_config['pin_modes'] = self.hardware_config['pin_modes'].split(',')
        if len(self.hardware_config['pin_modes']) == 1:
            self.hardware_config['pin_modes'] = \
                [self.hardware_config['pin_modes'][0] for _ in
                 range(self.hardware_config['gpiolen'])]
        else:
            if len(self.hardware_config['pin_modes']) < self.hardware_config['gpiolen']:
                length_to_extend = self.hardware_config['gpiolen'] - len(
                    self.hardware_config['pin_modes'])
                self.hardware_config['pin_modes'].extend(['onoff' for _ in range(length_to_extend)])
                logging.warn("not enough pins specified, extending list")
            elif len(self.hardware_config['pin_modes']) > self.hardware_config['gpiolen']:
                self.hardware_config['pin_modes'] = \
                    self.hardware_config['pin_modes'][:self.hardware_config['gpiolen']]
                logging.warn("to many pins, truncing list")

        self.hardware_config['pwm_range'] = int(self.hardware_config['pwm_range'])

        # Devices
        devices = dict()

        try:
            devices = json.loads(self.hardware_config['devices'])
        except (ValueError, TypeError) as error:
            logging.error("devices not defined or not in JSON format." + str(error))

        self.hardware_config['devices'] = devices

    def network(self):
        """
        Retrieves the network configuration

        loading and parsing it from a file if necessary.
        """
        for key, value in self.CONFIG.items('network'):
            self.network_config[key] = value
        self.network_config['port'] = self.CONFIG.getint('network', 'port')

        if len(self.network_config['channels']) == 0:
            channels = [_ for _ in range(self.hardware_config['gpiolen'])]
        else:
            channels = [str.strip(item) for item in self.network_config['channels'].split(",")]

        temp = defaultdict(list)

        for channel in range(len(channels)):
            temp[int(channels[channel])].append(int(channel))
        temp = dict(temp)

        self.network_config['channels'] = temp

    def lightshow(self):
        """
        Retrieve the lightshow configuration

        loading and parsing it from a file as necessary.
        """
        for key, value in self.CONFIG.items('lightshow'):
            self.lightshow_config[key] = value

        self.lightshow_config['audio_in_channels'] = self.CONFIG.getint('lightshow',
                                                                        'audio_in_channels')

        self.lightshow_config['audio_in_sample_rate'] = \
            self.CONFIG.getint('lightshow', 'audio_in_sample_rate')

        self.lightshow_config['always_on_channels'] = \
            [int(channel) for channel in self.lightshow_config['always_on_channels'].split(',')]

        self.lightshow_config['always_off_channels'] = \
            [int(channel) for channel in self.lightshow_config['always_off_channels'].split(',')]

        self.lightshow_config['invert_channels'] = \
            [int(channel) for channel in self.lightshow_config['invert_channels'].split(',')]

        self.lightshow_config['playlist_path'] = \
            self.lightshow_config['playlist_path'].replace('$SYNCHRONIZED_LIGHTS_HOME', HOME_DIR)

        self.lightshow_config['randomize_playlist'] = \
            self.CONFIG.getboolean('lightshow', 'randomize_playlist')

        # setup up preshow
        preshow = None
        if self.lightshow_config['preshow_configuration'] and not self.lightshow_config[
                'preshow_script']:
            try:
                preshow = json.loads(self.lightshow_config['preshow_configuration'])
            except (ValueError, TypeError) as e:
                logging.error("Preshow_configuration not defined or not in JSON format." + str(e))
        else:
            if os.path.isfile(self.lightshow_config['preshow_script']):
                preshow = self.lightshow_config['preshow_script']

        self.lightshow_config['preshow'] = preshow

        # setup postshow
        postshow = None
        if self.lightshow_config['postshow_configuration'] and not self.lightshow_config[
                'postshow_script']:
            try:
                postshow = json.loads(self.lightshow_config['postshow_configuration'])
            except (ValueError, TypeError) as e:
                logging.error("Postshow_configuration not defined or not in JSON format." + str(e))
        else:
            if os.path.isfile(self.lightshow_config['postshow_script']):
                postshow = self.lightshow_config['postshow_script']

        self.lightshow_config['postshow'] = postshow

    def audio_processing(self):
        """
        Retrieve the audio_processing configuration

        loading and parsing it from a file as necessary.
        """
        for key, value in self.CONFIG.items('audio_processing'):
            self.audio_processing_config[key] = value

        self.audio_processing_config['min_frequency'] = float(self.audio_processing_config['min_frequency'])
        self.audio_processing_config['max_frequency'] = float(self.audio_processing_config['max_frequency'])

        if self.audio_processing_config['custom_channel_mapping']:
            self.audio_processing_config['custom_channel_mapping'] = \
                [int(channel) for channel in self.audio_processing_config['custom_channel_mapping'].split(',')]
        else:
            self.audio_processing_config['custom_channel_mapping'] = 0

        if self.audio_processing_config['custom_channel_frequencies']:
            self.audio_processing_config['custom_channel_frequencies'] = \
                [int(channel) for channel in
                 self.audio_processing_config['custom_channel_frequencies'].split(',')]
        else:
            self.audio_processing_config['custom_channel_frequencies'] = 0

        self.audio_processing_config['fm'] = self.CONFIG.getboolean('audio_processing', 'fm')

        self.audio_processing_config['chunk_size'] = int(self.audio_processing_config['chunk_size'])
        if self.audio_processing_config['chunk_size'] % 8 != 0:
            self.audio_processing_config['chunk_size'] = 2048
            logging.warn('chunk_size must be a multiple of 8, defaulting to 2048')

    def per_song_config(self, song=None):
        """
        Trigger reloading the configs with per song configuration
        
        :param song: string, path and filename of per song config
        """
        self.load_configs(song)

    def songs(self, playlist_file=None):
        """
        Retrieve the song list

        :rtype : list of lists, playlist data
        :param playlist_file: string, path and filename of playlist
        """
        if playlist_file is not None:
            with open(playlist_file, 'r') as playlist_fp:
                fcntl.lockf(playlist_fp, fcntl.LOCK_SH)
                playlist = []
                for song in playlist_fp.readlines():
                    song = song.strip().split('\t')
                    if not 2 <= len(song) <= 4:
                        logging.warn('Invalid playlist enrty.  Each line should be in the form: '
                                     '<song name><tab><path to song>')
                        continue
                    song[1] = song[1].replace('$SYNCHRONIZED_LIGHTS_HOME', HOME_DIR)
                    playlist.append(song)
                fcntl.lockf(playlist_fp, fcntl.LOCK_UN)

            self._SONG_LIST = playlist

        return self._SONG_LIST

    def update_songs(self, playlist_file, playlist):
        """
        Update the song list

        :param playlist_file: string, path and filename of playlist
        :param playlist: list of lists, playlist data
        """
        with open(playlist_file, 'w') as playlist_fp:
            fcntl.lockf(playlist_fp, fcntl.LOCK_EX)
            for song in playlist:
                playlist_fp.write('\t'.join(song) + "\r\n")
            fcntl.lockf(playlist_fp, fcntl.LOCK_UN)
        self._SONG_LIST = playlist

    def set_songs(self, song_list):
        """
        Sets the list of songs

        :param song_list: list of lists, playlist data
        """
        self._SONG_LIST = song_list

    ##############################
    # Application State Utilities
    ##############################

    def load_state(self):
        """Force the state to be reloaded form disk."""
        with open(self.STATE_FILENAME) as state_fp:
            fcntl.lockf(state_fp, fcntl.LOCK_SH)
            self.STATE.readfp(state_fp, self.STATE_FILENAME)
            fcntl.lockf(state_fp, fcntl.LOCK_UN)

    def get_state(self, name, default=''):
        """
        Get application state

        Return the value of a specific application state variable, or the specified
        default if not able to load it from the state file
        :rtype : string, specific application state variable or default
        :param name: string, section name
        :param default: object, value to return if not able to load it from the state file
        """
        try:
            return self.STATE.get(self.STATE_SECTION, name)
        except:
            return default

    def update_state(self, name, value):
        """
        Update the application state (name / value pair)

        :param name: string, section name
        :param value: int or string, value to store in application state
        """
        value = str(value)
        logging.info('Updating application state {%s: %s}', name, value)
        try:
            self.STATE.add_section(self.STATE_SECTION)
        except ConfigParser.DuplicateSectionError:
            # Ok, it's already there
            pass

        self.STATE.set(self.STATE_SECTION, name, value)
        with open(self.STATE_FILENAME, 'wb') as state_fp:
            fcntl.lockf(state_fp, fcntl.LOCK_EX)
            self.STATE.write(state_fp)
            fcntl.lockf(state_fp, fcntl.LOCK_UN)
   