# !/usr/bin/env python2
#
# Licensed under the BSD license.  See full license in LICENSE file.
# http://www.lightshowpi.com/
#
# Author: Tom Enos
# A modified version of
# http://stackoverflow.com/a/14205494/1852928

"""
Configuration editor for the lightshow.

Configuration files are all located in the <homedir>/config directory. This file contains tools to
edit these configuration files.

Please refer to default.cfg in the config directory for a discription of the values
unsed in the configuration

A new file will be created named "new_configuration.cfg"
The default.cfg and your current override.cfg filess are unmodified. 
You must rename this file to overrides.cfg or copy and past in the contents of
this file to use it to override the lightshow configuration
Or
You can move this file to the directory of your music files and rename it as
name_of_music_file.ext.cfg (or copy and past into your current per-song config file) 
to use it as a per-song configuration file
examples
ovenrake_deck-the-halls.mp3.cfg
evilwezil_carol-of-the-bells.mp3.cfg

# NOTE: This editor writes all the configs from the default.cfg and your changes
#       You can delete any of the entries that you do not need from this file.
#       It is also advised that you manualy review this file before using it for
#       unintentional changes you might have made.
"""


import collections
import ConfigParser
import curses
import curses.panel
import json
import os
import pprint
import sys

import configuration_manager
from editor import Editor


class Panels(object):
    def __init__(self, items, stdscreen, info):
        self.info = info
        self.window = stdscreen.subwin(30, 40, 4, 4)
        self.window.erase()
        self.window.keypad(1)
        
        self.panel = curses.panel.new_panel(self.window)
        self.panel.hide()
        curses.panel.update_panels()

        self.position = 0
        self.items = items
        self.skip = None
        
    def navigate(self, n):
        last = self.position
        self.position += n
        if self.position == self.skip and last + 1 == self.skip:
                self.position += n
        elif self.position == self.skip and last - 1 == self.skip:
            self.position += n

        if self.position < 0:
            self.position = len(self.items) - 1
        elif self.position >= len(self.items):
            self.position = 0
        self.info(self.items[self.position][0], self.items[self.position][1], self.items[self.position][2])
            

    def display(self):
        self.panel.show()
        self.window.clear()
        self.info(self.items[self.position][0], self.items[self.position][1], self.items[self.position][2])

        while True:
            self.window.refresh()
            curses.doupdate()
            for index, item in enumerate(self.items):
                if index == self.position:
                    mode = curses.A_REVERSE
                else:
                    mode = curses.A_NORMAL

                if item[0] in ["Save settings", "Return to preavious menu", "Exit Editor"]:
                    msg = item[0]

                elif item[0] is None:
                    msg = "-" * 39
                    self.skip = index
                   
                else:
                    if item[1] == "":
                        msg = 'Edit %s' % item[0]
                    else:
                        msg = 'Edit %s' % item[1]
                    
                self.window.addstr(1 + index, 1, msg, mode)

            key = self.window.getch()
            
            if key in [curses.KEY_ENTER, ord('\n')]:
                if self.position == len(self.items) - 1:
                    break
                else:
                    if self.items[self.position][1] != "":
                        self.items[self.position][-1](self, self.position)
                    else:
                        self.items[self.position][-1]()

            elif key == 27:
                break

            elif key == curses.KEY_UP:
                self.navigate(-1)
                
            elif key == curses.KEY_DOWN:
                self.navigate(1)
                
        self.window.clear()
        self.panel.hide()
        curses.panel.update_panels()
        curses.doupdate()

    
class ConfigEditor(object):

    def __init__(self, stdscreen):
        self.screen = stdscreen
        try:
            curses.curs_set(0)
        except:
            pass
        
        self.panels = list()
        self.screen.box()
        self.screen.addstr(2, 2, "Lightshowpi Configuration Editor")
        self.info_box = curses.newwin(37, 80, 4, 45)
        self.info_box.erase()
        self.info_box.box()
        self.info_box_inner = self.info_box.subwin(35, 78, 5, 46)
        self.info_box_inner.erase()
        self.info_box_inner.keypad(1)
        
        self.info_panel = curses.panel.new_panel(self.info_box)
        self.info_panel_inner = curses.panel.new_panel(self.info_box_inner)
        self.info_panel.show()
        self.info_panel_inner.show()
        
        main_menu_items = list()
        
        sections = cm.CONFIG.sections()
        
        for section in sections:
            self.create_submenu(section)
            main_menu_items.append([section, "", "", getattr(self, section + "_menu").display])
        
        main_menu_items.append((None, "", "", ""))
        main_menu_items.append(("Save settings", "", "", self.save))
        main_menu_items.append(("Exit Editor", "", "", "exit"))
        main_menu = Panels(main_menu_items, self.screen, self.info)
        main_menu.display()
        
    def create_submenu(self, section):
        section_list = section + "_items"
        setattr(self, section_list, list())
        section_object = getattr(self, section_list)

        options = cm.CONFIG.options(section)

        for option in options:
            value = cm.CONFIG.get(section, option)
            section_object.append([section, option, value, self.edit])
            
        section_object.append((None, "", "", ""))
        section_object.append(("Return to preavious menu", "", "", "exit"))
        setattr(self, section + "_menu", Panels(section_object, self.screen, self.info))
        self.panels.append(getattr(self, section + "_menu"))

    def save(self):
        cm.save_config()
        self.info_box_inner.clear()
        self.info_box.box()
        self.info_box_inner.addstr(1, 1, "Settings Saved")
        j_string = ["devices","preshow_configuration","postshow_configuration"]
        row = 2
        save = False
        for panel in self.panels:
            for option in range(len(panel.items) - 2):
                this = panel.items[option]
                section = this[0]
                option = this[1]
                value = this[2]
                if value != cm.CONFIG.get(section, option):
                    save = True
                    if option in j_string:
                        pass
                        #value = json.loads(value)
                        #value = pprint.pformat(value, indent=4)
                    cm.CONFIG.set(section, option, value)
                    self.info_box_inner.addstr(row, 1, "section: {0} option: {1} has changed".format(section, option))
                    row += 1
        if save:
            cm.save_config()
        else:
            self.info_box_inner.addstr(1, 1, "Config file unchanged")
        save = False
        curses.panel.update_panels()
        self.screen.refresh()
        
    def edit(self, this_option, position):
        section = this_option.items[position][0]
        option = this_option.items[position][1]
        value = this_option.items[position][2]
        new_value = Editor(self.screen,
                           inittext=value,
                           title=option,
                           win_location=(20,45),
                           win_size=(18,78),
                           pw_mode=False,
                           max_text_rows=0,
                           max_text_size=1)()
        value = str(new_value)
        this_option.items[position][2] = value
        self.info(section, option, value)

    def info(self, section, option, value):
        self.info_box_inner.clear()
        self.info_box.box()
        
        if option == "":
            if section in ["Exit Editor", "Save settings", "Return to preavious menu"]:
                self.info_box_inner.addstr(1, 1, str(section))
            else:
                self.info_box_inner.addstr(1, 1, "Edit %s section" % section)
        else:
            self.info_box_inner.addstr(1, 1, "Section: " + section)
            self.info_box_inner.addstr(3, 1, "Option: " + option)
            
            if '\n' in value:
                value = json.loads(value)
                value = pprint.pformat(value, indent=4)
            self.info_box_inner.addstr(5, 1, "Current Value: " + value)

        curses.panel.update_panels()
        self.screen.refresh()

if __name__ == '__main__':
    cm = configuration_manager.Configuration()
    curses.wrapper(ConfigEditor)    
