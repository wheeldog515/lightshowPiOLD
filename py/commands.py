#!/usr/bin/env python
#
# Licensed under the BSD license.  See full license in LICENSE file.
# http://www.lightshowpi.com/
#
# Author: Todd Giles (todd@lightshowpi.com)
#
# Initial commands implemented by Chris Usey (chris.usey@gmail.com)
"""Commmand definition file.

Enabled commands must be defined in the configuration file. Each command must also have a
matching function defined in this file with a name in the form 'def cmd_commandname(user, args)'.
For example, the command help would have a matching function definition for 'def cmd_help(user,
args)'. The user argument will include the cell number of the user who made the request (if the
command is received via sms) and the 'args' argument is a string containing all the text in the
command sent (e.g. an sms message) after the command name itself has already been stripped.
So following the 'help' example, if a user with the cell phone number 1 (123) 456-7890 texted
'help me please!!!' then the function cmd_help will be called with arguments user = '+11234567890:',
and args = ' me please!!!'.

The function should return a string that will then be sent back to the user in some fashion (e.g.
in a return text message if via sms). Return an empty string if you'd rather no message be sent in
response to the command.

To install the command, simply instantiate an instance of Command for the command you've created
(see examples below). Note that new commands may be defined in their own files if desired (i.e. no
need to define all commands in this file).
"""

import logging
import re
import subprocess


# The base command class. The class keeps track of all commands instantiated, so to install a new
# command, simply instantiate a new instance of it.
class Command(object):
    """
    The base command class.
    This class keeps track of all commands instantiated, so to install
    a new command, simply instantiate a new instance of that command.
    """

    commands = {}

    def __init__(self, name, func):
        self.name = name.lower()
        if not self.name in _CMD_NAMES:
            raise ValueError(name + ' command not defined in configuration file')
        if self.name in Command.commands:
            logging.warn(name + 'command is defined more than once, using last definition')
        self.func = func
        Command.commands[self.name] = self

    def execute(self, user, args):
        """
        Execute this command for the specified user with given arguments,
        returning a message to be sent to the user after the command has
        finished
        """
        return self.func(user, args)


# Attempt to execute a command for the specified user.
def execute(command, user):
    """
    Attempt to execute a command for the specified user with given
    arguments, returning a message to be sent to the user after
    the command has finished

    :rtype : object, executed command
    :param command: function, function to execute
    :param user: string, specified user
    """

    # Determine the name of the command and arguments from the full
    # command (taking into account aliases).
    name = ''
    args = ''
    for command_name in _CMD_NAMES:
        if bool(re.match(command_name, command, re.I)):
            name = command_name
            args = command[len(command_name):]
        else:
            try:
                for command_alias in _CONFIG[command_name + '_aliases']:
                    if bool(re.match(command_alias, command, re.I)):
                        name = command_name
                        args = command[len(command_alias):]
                        break
            except KeyError:
                pass  # No aliases defined, that's fine - keep looking
        if name:
            break

    # If no command found, assume we're executing the default command
    if not name:
        name = _CONFIG['default_command']
        args = command

    # Verify this command is installed
    if not name in Command.commands:
        raise ValueError(name
                         + ' command must be installed by calling Command(\''
                         + name + '\', <handler>)')

    # Verify the user has permission to execute this command
    if not cm.has_permission(user, name):
        return _CONFIG['unauthorized_response'].format(cmd=name, user=user)

    # Check to see if the command issued should be throttled
    if cm.is_throttle_exceeded(name, user):
        return _CONFIG['throttle_limit_reached_response'].format(cmd=name, user=user)

    # Execute the command
    return Command.commands[name].execute(user, args.strip())


def cmd_help(*args):
    """
    Returns a list of available commands for the requesting user.

    :rtype : string, help message for args
    :param args: list, [specified user, arguments for command]
   """
    user = args[0]
    help_msg = "Commands:\n"
    for cmd in _CMD_NAMES:
        if cm.has_permission(user, cmd):
            cmd_description = cm.sms_config[cmd + '_description']
            if cmd_description:
                help_msg += cmd_description + "\n"
    return help_msg


# TODO(todd): Add paging support for large playlist (Issue #22)
def cmd_list(*args):
    """
    Lists all the songs from the current playlist.

    :rtype : list, list of songs
    :param args: list, [specified user, arguments for command]
    """

    songlist = ['Vote by texting the song #:\n']
    division = 0
    index = 1
    for song in cm.songs():
        songlist[division] += str(index) + ' - ' + song[0] + '\n'
        index += 1
        if (index - 1) % 4 == 0:
            division += 1
            songlist.append('')
    return songlist


def cmd_play(*args):
    """
    Interrupts whatever is going on, and plays the requested song.

    :rtype : string, play song response
    :param args: list, [specified user, arguments for command]
    """
    args = args[1]
    if len(args) == 0 or not args.isdigit():
        cm.update_state('play_now', -1)
        return 'Skipping straight ahead to the next show!'
    else:
        song = int(args)
        if song < 1 or song > len(cm.songs()):
            return 'Sorry, the song you requested ' + args + ' is out of range :('
        else:
            cm.update_state('play_now', song)
            return '"' + cm.songs()[song - 1][0] + '" coming right up!'


def cmd_volume(*args):
    """
    Changes the system volume.

    :rtype : string, volume request result
    :param args: list, [specified user, arguments for command]
    """
    args = args[1]
    # Sanitize the input before passing to volume script
    if '-' in args:
        sanitized_cmd = '-'
    elif '+' in args:
        sanitized_cmd = '+'
    elif args.isdigit():
        vol = int(args)
        if vol < 0 or vol > 100:
            return 'volume must be between 0 and 100'
        sanitized_cmd = str(vol)
    else:
        return cm.sms_config['volume_description']

    # Execute the sanitized command and handle result
    volscript = cm.HOME_DIR + '/bin/vol'
    output, error = subprocess.Popen(volscript + ' ' + sanitized_cmd,
                                     shell=True, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE).communicate()
    if error:
        logging.warn('volume request failed: ' + str(error))
        return 'volume request failed'
    else:
        return 'volume = ' + str(output)


# Casts a vote for the next song to be played.
def cmd_vote(*args):
    """
    Casts a vote for the next song to be played

    :rtype : string, unknown command response
    :param args: list, [specified user, arguments for command]
    """
    user = args[0]
    args = args[1]
    if args.isdigit():
        song_num = int(args)
        if user != 'Me' and 0 < song_num <= len(cm.songs()):
            song = cm.songs()[song_num - 1]
            song[2].add(user)
            logging.info('Song requested: ' + str(song))
            return 'Thank you for requesting "' + song[0] \
                   + '", we\'ll notify you when it starts!'
    else:
        return cm.sms_config['unknown_command_response']


def setup(config):
    global cm, _CONFIG, _CMD_NAMES
    cm = config
    _CONFIG = cm.sms_config
    _CMD_NAMES = _CONFIG['commands']
    
    Command('help', cmd_help)
    Command('list', cmd_list)
    Command('play', cmd_play)
    Command('volume', cmd_volume)
    Command('vote', cmd_vote)
