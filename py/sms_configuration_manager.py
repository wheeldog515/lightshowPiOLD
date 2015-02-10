#!/usr/bin/env python
#
# Licensed under the BSD license.  See full license in LICENSE file.
# http://www.lightshowpi.com/
#
# Author: Todd Giles (todd@lightshowpi.com)
# Author: Tom Enos

# TODO(todd): Add a main and allow running configuration manager alone to view the current
#                  configuration, and potentially edit it.
"""
Configuration management for the sms control of the lightshow.

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

HOME_DIR = os.getenv("SYNCHRONIZED_LIGHTS_HOME")
if not HOME_DIR:
    if not "raspberrypi" in os.uname():
        d = os.path.dirname(os.path.abspath(__file__))
        
        HOME_DIR = d[:d.rfind('/')]
    else:
        print("Need to setup SYNCHRONIZED_LIGHTS_HOME environment variable, "
            "see readme")
        sys.exit()
    
CONFIG_DIR = HOME_DIR + '/config'
LOG_DIR = HOME_DIR + '/logs'


def _as_list(list_str, delimiter=','):
    """
    Return a list of items from a delimited string (after stripping whitespace).

    :rtype : list, made from string
    :param list_str: string, string to convert to list
    :param delimiter: string, delimiter for list
    """
    return [str.strip(item) for item in list_str.split(delimiter)]

class Configuration(object):

    def __init__(self):
        self.HOME_DIR = HOME_DIR
        self.CONFIG_DIR = HOME_DIR + '/config'
        self.LOG_DIR = HOME_DIR + '/logs'
        
        self._SMS_CONFIG = dict()
        self._WHO_CAN = dict()
        self._SONG_LIST = list()
        
        self.CONFIG = ConfigParser.RawConfigParser(allow_no_value=True)
        self.CONFIG.readfp(open(self.CONFIG_DIR + '/defaults.cfg'))
        self.CONFIG.read([self.CONFIG_DIR + '/overrides.cfg', '/home/pi/.lights.cfg',
                    os.path.expanduser('~/.lights.cfg')])

        # Load application state configuration file from CONFIG directory.
        self.STATE = ConfigParser.RawConfigParser()
        self.STATE_SECTION = 'do_not_modify'
        self.STATE_FILENAME = self.CONFIG_DIR + '/state.cfg'

        # Ensure state file has been created
        if not os.path.isfile(self.STATE_FILENAME):
            open(self.STATE_FILENAME, 'a').close()
        self.load_state()
        self.sms()

    def sms(self):
        """
        Retrieves and validates sms configuration

        :rtype : dictionary, items in config section
        """
        self.playlist_path = self.CONFIG.get('lightshow', 'playlist_path').replace('$SYNCHRONIZED_LIGHTS_HOME', HOME_DIR)
        
        for key, value in self.CONFIG.items('sms'):
            self._SMS_CONFIG[key] = value

        self._WHO_CAN['all'] = set()

        # Commands
        self._SMS_CONFIG['enable'] = self.CONFIG.getboolean('sms', 'enable')
        self._SMS_CONFIG['commands'] = _as_list(self._SMS_CONFIG['commands'])
        for cmd in self._SMS_CONFIG['commands']:
            try:
                self._SMS_CONFIG[cmd + '_aliases'] = _as_list(self._SMS_CONFIG[cmd + '_aliases'])
            except:
                self._SMS_CONFIG[cmd + '_aliases'] = []
            self._WHO_CAN[cmd] = set()

        # Groups / Permissions
        self._SMS_CONFIG['groups'] = _as_list(self._SMS_CONFIG['groups'])
        self._SMS_CONFIG['throttled_groups'] = dict()
        for group in self._SMS_CONFIG['groups']:
            try:
                self._SMS_CONFIG[group + '_users'] = _as_list(self._SMS_CONFIG[group + '_users'])
            except:
                self._SMS_CONFIG[group + '_users'] = []
            try:
                self._SMS_CONFIG[group + '_commands'] = _as_list(self._SMS_CONFIG[group + '_commands'])
            except:
                self._SMS_CONFIG[group + '_commands'] = []
            for cmd in self._SMS_CONFIG[group + '_commands']:
                for user in self._SMS_CONFIG[group + '_users']:
                    self._WHO_CAN[cmd].add(user)

            # Throttle
            try:
                throttled_group_definitions = _as_list(self._SMS_CONFIG[group + '_throttle'])
                throttled_group = dict()
                for definition in throttled_group_definitions:
                    definition = definition.split(':')
                    if len(definition) != 2:
                        warnings.warn(group + "_throttle definitions should be in the form "
                                    + "[command]:<limit> - " + ':'.join(definition))
                        continue
                    throttle_command = definition[0]
                    throttle_limit = int(definition[1])
                    throttled_group[throttle_command] = throttle_limit
                self._SMS_CONFIG['throttled_groups'][group] = throttled_group
            except:
                warnings.warn("Throttle definition either does not exist or is configured "
                            "incorrectly for group: " + group)

        # Blacklist
        self._SMS_CONFIG['blacklist'] = _as_list(self._SMS_CONFIG['blacklist'])


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
            pass  # Ok, it's already there
        self.STATE.set(self.STATE_SECTION, name, value)
        with open(self.STATE_FILENAME, 'wb') as state_fp:
            fcntl.lockf(state_fp, fcntl.LOCK_EX)
            self.STATE.write(state_fp)
            fcntl.lockf(state_fp, fcntl.LOCK_UN)

    def has_permission(self, user, cmd):
        """
        Returns True iff a user has permission to execute the given command

        :rtype : boolean, is the user blacklisted
        :param user: string, user in user list
        :param cmd: string command in command list
        """
        blacklisted = user in self._SMS_CONFIG['blacklist']
        return not blacklisted and (user in self._WHO_CAN['all']
                                    or 'all' in self._WHO_CAN[cmd]
                                    or user in self._WHO_CAN[cmd])

    def is_throttle_exceeded(self, cmd, user):
        """
        Returns True if the throttle has been exceeded and False otherwise

        :rtype : boolean, True is throttle has been exceeded
        :param cmd: string, user in user list
        :param user: string command in command list
        """
        # Load throttle STATE
        self.load_state()
        throttle_state = ast.literal_eval(self.get_state('throttle', '{}'))
        process_command_flag = -1

        # Analyze throttle timing
        current_time_stamp = datetime.datetime.now()
        throttle_time_limit = self._SMS_CONFIG['throttle_time_limit_seconds']
        throttle_start_time = datetime.datetime.strptime(
            throttle_state['throttle_timestamp_start'], '%Y-%m-%d %H:%M:%S.%f') \
            if "throttle_timestamp_start" in throttle_state else current_time_stamp
        throttle_stop_time = throttle_start_time + datetime.timedelta(seconds=int(throttle_time_limit))

        # Compare times and see if we need to reset the throttle STATE
        if (current_time_stamp == throttle_start_time) or (throttle_stop_time < current_time_stamp):
            # There is no time recorded or the time has
            # expired reset the throttle STATE
            throttle_state = dict()
            throttle_state['throttle_timestamp_start'] = str(current_time_stamp)
            self.update_state('throttle', throttle_state)

        # ANALYZE THE THROTTLE COMMANDS AND LIMITS
        all_throttle_limit = -1
        cmd_throttle_limit = -1

        # Check to see what group belongs to starting with the first group declared
        throttled_group = None
        for group in self._SMS_CONFIG['groups']:
            user_list = self._SMS_CONFIG[group + "_users"]
            if user in user_list:
                # The user belongs to this group, check if there
                # are any throttle definitions
                if group in self._SMS_CONFIG['throttled_groups']:
                    # The group has throttle commands defined,
                    # now check if the command is defined
                    throttled_commands = self._SMS_CONFIG['throttled_groups'][group]

                    # Check if all command exists
                    if "all" in throttled_commands:
                        all_throttle_limit = int(throttled_commands['all'])

                    # Check if the command passed is defined
                    if cmd in throttled_commands:
                        cmd_throttle_limit = int(throttled_commands[cmd])

                    # A throttle definition was found,
                    # we no longer need to check anymore groups
                    if all_throttle_limit != -1 or cmd_throttle_limit != -1:
                        throttled_group = group
                        break

        # Process the throttle settings that were found for the throttled group
        if not throttled_group:
            # No throttle limits were found for any group
            return False
        else:
            # Throttle limits were found, check them against throttle STATE limits
            group_throttle_state = \
                throttle_state[throttled_group] if throttled_group in throttle_state else {}
            group_throttle_cmd_limit = \
                int(group_throttle_state[cmd]) if cmd in group_throttle_state else 0

        # Check to see if we need to apply "all"
        if all_throttle_limit != -1:
            group_throttle_all_limit = \
                int(group_throttle_state['all']) if 'all' in group_throttle_state else 0

            # Check if "all" throttle limit has been reached
            if group_throttle_all_limit < all_throttle_limit:
                # Not Reached, bump throttle and record
                group_throttle_all_limit += 1
                group_throttle_state['all'] = group_throttle_all_limit
                throttle_state[throttled_group] = group_throttle_state
                process_command_flag = False
            else:
                # "all" throttle has been reached we
                # dont want to process anything else
                return True

        # Check to see if we need to apply "cmd"
        if cmd_throttle_limit != -1:
            if group_throttle_cmd_limit < cmd_throttle_limit:
                # Not reached, bump throttle
                group_throttle_cmd_limit += 1
                group_throttle_state[cmd] = group_throttle_cmd_limit
                throttle_state[throttled_group] = group_throttle_state
                process_command_flag = False

        # Record the updated_throttle STATE and return
        self.update_state('throttle', throttle_state)

        return process_command_flag

