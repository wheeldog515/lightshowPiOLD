"""Py_curses_editor

Python curses text editor module. Provides a configurable pop-up window for entering text, passwords, etc.

Posted by Scott Hansen <firecat4153@gmail.com>

Other Contributors:

Yuri D'Elia <yuri.delia@eurac.edu> (Unicode/python2 code from tabview)

-----------------------------------------------------------------------
This is a modified version, some feature have been disabled or changed
for use with lightshowpi.  The original software can be obtained from

https://github.com/firecat53/py_curses_editor

The below Copyright and License appllies to Py_curses_editor, and 
not to lightshowpi.
-----------------------------------------------------------------------


Copyright (c) 2015, Scott Hansen <firecat4153@gmail.com>

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

import curses
import curses.ascii
import locale
import string
import sys
from textwrap import wrap


if sys.version_info.major < 3:
    # Python 2.7 shim
    str = unicode

    def CTRL(key):
        return curses.ascii.ctrl(bytes(key))

    def addstr(*args):
        scr, args = args[0], list(args[1:])
        x = 2 if len(args) > 2 else 0
        args[x] = args[x].encode(sys.stdout.encoding)
        return scr.addstr(*args)

else:
    # Python 3 wrappers
    def CTRL(key):
        return curses.ascii.ctrl(key)

    def addstr(*args):
        scr, args = args[0], args[1:]
        return scr.addstr(*args)


class Editor(object):
    """ Basic python curses text editor class.

    Can be used for multi-line editing.

    Text will be wrapped to the width of the editing window, so there will be
    no scrolling in the horizontal direction. For now, there's no line
    wrapping, so lines will have to be wrapped manually.

    Args:
        stdscr:         the curses window object
        title:          title text
        inittext:       inital text content string
        win_location:   tuple (y,x) for location of upper left corner
        win_size:       tuple (rows,cols) size of the editor window
        box:            True/False whether to outline editor with a box
        max_text_rows:  maximum rows allowed for text.
                            Default=0 (unlimited)
                            If initext is longer than max_text_rows, extra
                            lines _will be truncated_!
        pw_mode:        True/False. Whether or not to show text entry
                            (e.g. for passwords)

    Returns:
        text:   text string

    Usage: (from non-curses application)
        import editor
        editor.editor(box=False, inittext="Hi", win_location=(5, 5))

    Usage: (from curses application with a defined curses window object)
        from editor.editor import Editor
        Editor(stdscr, win_size=(1,80), pw_mod=True, max_text_size=1)()

    Keybindings:

    F1                  Show popup help menu
    F2 or Ctrl-x        Save and Quit
    Enter               Enter new line, or Save and Quit (single line mode)
    F3 or ESC           Cancel (no save)
    Cursor keys         Movement
    Ctrl-n/p Ctrl-f/b   Up/down right/left
    Home/End Ctrl-a/e   Beginning or End of current line
    PageUp/PageDown     PageUp/PageDown
    Delete Ctrl-d       Delete character under cursor
    Backspace Ctrl-h    Delete character to left
    Ctrl-k/u            Delete to end/beginning of-line
    """

    def __init__(self, scr, title="", inittext="", win_location=(0, 0),
                 win_size=(20, 80), box=True, max_text_size=0, max_text_rows=0, pw_mode=False):
        self.scr = scr
        self.title = title + "    "
        if sys.version_info.major < 3:
            enc = locale.getpreferredencoding() or 'utf-8'
            self.title = str(self.title, encoding=enc)
            inittext = str(inittext, encoding=enc)
        self.box = box
        self.max_text_rows = max_text_rows
        self.pw_mode = pw_mode
        if self.pw_mode is True:
            curses.curs_set(0)
        else:
            curses.curs_set(1)
        self.resize_flag = False
        self.win_location_y, self.win_location_x = win_location
        self.win_size_orig_y, self.win_size_orig_x = win_size
        self.win_size_y = self.win_size_orig_y
        self.win_size_x = self.win_size_orig_x
        self.win_init()
        self.box_init()
        self.text_init(inittext)
        self.keys_init()
        self.display()

    def __call__(self):
        self.run()
        curses.flushinp()
        return "\n".join(self.text)

    def box_init(self):
        """Clear the main screen and redraw the box and/or title

        """
        self.scr.refresh()
        self.stdscr.clear()
        self.stdscr.refresh()
        quick_help = "(F1: Help, F2: Save, F3: Cancel)"
        if self.box is True:
            self.boxscr.clear()
            self.boxscr.box()
            if self.title:
                addstr(self.boxscr, 1, 1, self.title, curses.A_BOLD)
                addstr(self.boxscr, quick_help, curses.A_STANDOUT)
            self.boxscr.refresh()
        elif self.title:
            self.boxscr.clear()
            addstr(self.boxscr, 0, 0, self.title, curses.A_BOLD)
            addstr(self.boxscr, quick_help, curses.A_STANDOUT)
            self.boxscr.refresh()

    def text_init(self, text):
        """Transform text string into a list of strings, wrapped to fit the
        window size. Sets the dimensions of the text buffer.

        """
        t = text.split('\n')
        # Use win_size_x - 1 so addstr has one more cell at the end to put the
        # cursor
        t = [wrap(i, self.win_size_x - 1) for i in t]
        self.text = []
        for line in t:
            # This retains any empty lines
            if line:
                self.text.extend(line)
            else:
                self.text.append("")
        if self.text:
            # Sets size for text buffer...may be larger than win_size!
            self.buffer_cols = max(self.win_size_x,
                                   max([len(i) for i in self.text]))
            self.buffer_rows = max(self.win_size_y, len(self.text))
        self.text_orig = list(self.text)
        if self.max_text_rows:
            # Truncates initial text if max_text_rows < len(self.text)
            self.text = self.text[:self.max_text_rows]
        self.buf_length = len(self.text[self.buffer_idx_y])

    def keys_init(self):
        """Define methods for each key.

        """
        self.keys = {
            curses.KEY_BACKSPACE:           self.backspace,
            CTRL('h'):                      self.backspace,
            curses.KEY_DOWN:                self.down,
            CTRL('n'):                      self.down,
            curses.KEY_END:                 self.end,
            CTRL('e'):                      self.end,
            curses.KEY_ENTER:               self.insert_line_or_quit,
            curses.KEY_HOME:                self.home,
            CTRL('a'):                      self.home,
            curses.KEY_DC:                  self.del_char,
            CTRL('d'):                      self.del_char,
            curses.KEY_LEFT:                self.left,
            CTRL('b'):                      self.left,
            curses.KEY_NPAGE:               self.page_down,
            curses.KEY_PPAGE:               self.page_up,
            curses.KEY_RIGHT:               self.right,
            CTRL('f'):                      self.right,
            curses.KEY_UP:                  self.up,
            CTRL('p'):                      self.up,
            curses.KEY_F1:                  self.help,
            curses.KEY_F2:                  self.quit,
            curses.KEY_F3:                  self.quit_nosave,
            curses.KEY_RESIZE:              self.resize,
            CTRL('x'):                      self.quit,
            CTRL('u'):                      self.del_to_bol,
            CTRL('k'):                      self.del_to_eol,
            curses.ascii.DEL:               self.backspace,
            curses.ascii.NL:                self.insert_line_or_quit,
            curses.ascii.LF:                self.insert_line_or_quit,
            curses.ascii.BS:                self.backspace,
            curses.ascii.ESC:               self.quit_nosave,
            curses.ascii.ETX:               self.close,
            "\n":                           self.insert_line_or_quit,
            -1:                             self.resize,
        }

    def win_init(self):
        """Set initial editor window size parameters, and reset them if window
        is resized.

        """
        # self.cur_pos is the current y,x position of the cursor relative to
        # the visible area of the box
        self.cur_pos_y = 0
        self.cur_pos_x = 0
        # y_offset controls the up-down scrolling feature
        self.y_offset = 0
        # Position of the cursor relative to the upper left corner of the data
        self.buffer_idx_y = 0
        self.buffer_idx_x = 0
        # Make sure requested window size is < available window size
        self.max_win_size_y, self.max_win_size_x = self.scr.getmaxyx()
        # Adjust max_win_size for maximum possible offsets
        # (e.g. if there is a title and/or a box)
        if self.box and self.title:
            self.max_win_size_y = max(0, self.max_win_size_y - 3)
            self.max_win_size_x = max(0, self.max_win_size_x - 2)
        elif self.box:
            self.max_win_size_y = max(0, self.max_win_size_y - 2)
            self.max_win_size_x = max(0, self.max_win_size_x - 2)
        elif self.title:
            self.max_win_size_y = max(0, self.max_win_size_y - 1)
        self._win_scr_init()
        self.stdscr.keypad(1)

    def _win_scr_init(self):
        """Initialize the curses window objects  (called from win_init)

            self.stdscr - the text display area
            self.boxscr - for the box outline and title, if applicable

        """
        # Keep the input box inside the physical window
        if (self.win_size_y > self.max_win_size_y or
                self.win_size_y < self.win_size_orig_y):
            self.win_size_y = self.max_win_size_y
        if (self.win_size_x > self.max_win_size_x or
                self.win_size_x < self.win_size_orig_x):
            self.win_size_x = self.max_win_size_x
        # Validate win_location settings
        if self.win_size_x + self.win_location_x >= self.max_win_size_x:
            self.win_location_x = max(0, self.max_win_size_x -
                                      self.win_size_x)
        if self.win_size_y + self.win_location_y >= self.max_win_size_y:
            self.win_location_y = max(0, self.max_win_size_y -
                                      self.win_size_y)
        # Create an extra window for the box outline and/or title, if required
        x_off = y_off = loc_off_y = loc_off_x = 0
        if self.box:
            # Compensate for the box lines
            y_off += 2
            x_off += 2
            # The box is drawn outside the initially called win_location
            loc_off_y += 1
            loc_off_x += 1
        if self.title:
            y_off += 1
            loc_off_y += 1
        if self.box is True or self.title:
            # Make box/title screen bigger than actual text area (stdscr)
            self.boxscr = self.scr.subwin(self.win_size_y + y_off,
                                          self.win_size_x + x_off,
                                          self.win_location_y,
                                          self.win_location_x)
            self.stdscr = self.boxscr.subwin(self.win_size_y,
                                             self.win_size_x,
                                             self.win_location_y + loc_off_y,
                                             self.win_location_x + loc_off_x)
        else:
            self.stdscr = self.scr.subwin(self.win_size_y,
                                          self.win_size_x,
                                          self.win_location_y,
                                          self.win_location_x)

    def left(self):
        if self.cur_pos_x > 0:
            self.cur_pos_x = self.cur_pos_x - 1

    def right(self):
        if self.cur_pos_x < self.win_size_x:
            self.cur_pos_x = self.cur_pos_x + 1

    def up(self):
        if self.cur_pos_y > 0:
            self.cur_pos_y = self.cur_pos_y - 1
        else:
            self.y_offset = max(0, self.y_offset - 1)

    def down(self):
        if (self.cur_pos_y < self.win_size_y - 1 and
                self.buffer_idx_y < len(self.text) - 1):
            self.cur_pos_y = self.cur_pos_y + 1
        elif self.buffer_idx_y == len(self.text) - 1:
            pass
        else:
            self.y_offset = min(self.buffer_rows - self.win_size_y,
                                self.y_offset + 1)

    def end(self):
        self.cur_pos_x = self.buf_length

    def home(self):
        self.cur_pos_x = 0

    def page_up(self):
        self.y_offset = max(0, self.y_offset - self.win_size_y)

    def page_down(self):
        self.y_offset = min(self.buffer_rows - self.win_size_y - 1,
                            self.y_offset + self.win_size_y)
        # Corrects negative offsets
        self.y_offset = max(0, self.y_offset)

    def insert_char(self, c):
        """Given an integer character, insert that character in the current
        line. Stop when the maximum line length is reached.

        """
        if c not in string.printable:
            return
        line = list(self.text[self.buffer_idx_y])
        line.insert(self.buffer_idx_x, c)
        if len(line) < self.win_size_x:
            self.text[self.buffer_idx_y] = "".join(line)
            self.cur_pos_x += 1

    def insert_line_or_quit(self):
        """Insert a new line at the cursor. Wrap text from the cursor to the
        end of the line to the next line. If the line is a single line, saves
        and exits.

        """
        if self.max_text_rows == 1:
            # Save and quit for single-line entries
            return False
        if len(self.text) == self.max_text_rows:
            return
        line = list(self.text[self.buffer_idx_y])
        newline = line[self.cur_pos_x:]
        line = line[:self.cur_pos_x]
        self.text[self.buffer_idx_y] = "".join(line)
        self.text.insert(self.buffer_idx_y + 1, "".join(newline))
        self.buffer_rows = max(self.win_size_y, len(self.text))
        self.cur_pos_x = 0
        self.down()

    def backspace(self):
        """Delete character under cursor and move one space left.

        """
        line = list(self.text[self.buffer_idx_y])
        if self.cur_pos_x > 0:
            if self.cur_pos_x <= len(line):
                # Just backspace if beyond the end of the actual string
                del line[self.buffer_idx_x - 1]
            self.text[self.buffer_idx_y] = "".join(line)
            self.cur_pos_x -= 1
        elif self.cur_pos_x == 0:
            # If at BOL, move cursor to end of previous line
            # (unless already at top of file)
            # If current or previous line is empty, delete it
            if self.y_offset > 0 or self.cur_pos_y > 0:
                self.cur_pos_x = len(self.text[self.buffer_idx_y - 1])
            if not self.text[self.buffer_idx_y]:
                if len(self.text) > 1:
                    del self.text[self.buffer_idx_y]
            elif not self.text[self.buffer_idx_y - 1]:
                del self.text[self.buffer_idx_y - 1]
            self.up()
        self.buffer_rows = max(self.win_size_y, len(self.text))
        # Makes sure leftover rows are visually cleared if deleting rows from
        # the bottom of the text.
        # self.stdscr.clear()

    def del_char(self):
        """Delete character under the cursor.

        """
        line = list(self.text[self.buffer_idx_y])
        if line and self.cur_pos_x < len(line):
            del line[self.buffer_idx_x]
        self.text[self.buffer_idx_y] = "".join(line)

    def del_to_eol(self):
        """Delete from cursor to end of current line. (C-k)

        """
        line = list(self.text[self.buffer_idx_y])
        line = line[:self.cur_pos_x]
        self.text[self.buffer_idx_y] = "".join(line)

    def del_to_bol(self):
        """Delete from cursor to beginning of current line. (C-u)

        """
        line = list(self.text[self.buffer_idx_y])
        line = line[self.cur_pos_x:]
        self.text[self.buffer_idx_y] = "".join(line)
        self.cur_pos_x = 0

    def quit(self):
        return False

    def quit_nosave(self):
        self.text = self.text_orig
        return False

    def help(self):
        """Display help text popup window.

        """
        help_txt = """
        Save and exit                               : F2 or Ctrl-x
                                       (Enter if single-line entry)
        Exit without saving                         : F3 or ESC
        Cursor movement                             : Arrow keys
        Move to beginning of line                   : Home
        Move to end of line                         : End
        Page Up/Page Down                           : PgUp/PgDn
        Backspace/Delete one char left of cursor    : Backspace
        Delete 1 char under cursor                  : Del
        Insert line at cursor                       : Enter
        Delete to end of line                       : Ctrl-k
        Delete to beginning of line                 : Ctrl-u
        Help                                        : F1
        """
        curses.curs_set(0)
        txt = help_txt.split('\n')
        lines = min(self.max_win_size_y, len(txt) + 2)
        cols = min(self.max_win_size_x, max([len(i) for i in txt]) + 6)
        # Only print help text if the window is big enough
        try:
            popup = curses.newwin(lines, cols, self.win_location_y + 2, self.win_location_x + 4)
            addstr(popup, 1, 1, help_txt)
            popup.box()
        except:
            pass
        else:
            while not popup.getch():
                pass
        finally:
            # Turn back on the cursor
            if self.pw_mode is False:
                curses.curs_set(1)
            # flushinp Needed to prevent spurious F1 characters being written
            # to line
            curses.flushinp()
            self.box_init()

    def resize(self):
        pass

    def run(self):
        """Main program loop.

        """
        try:
            while True:
                self.stdscr.move(self.cur_pos_y, self.cur_pos_x)
                loop = self.get_key()
                if loop is False:
                    break
                self.buffer_idx_y = self.cur_pos_y + self.y_offset
                self.buf_length = len(self.text[self.buffer_idx_y])
                if self.cur_pos_x > self.buf_length:
                    self.cur_pos_x = self.buf_length
                self.buffer_idx_x = self.cur_pos_x
                self.display()
        except KeyboardInterrupt:
            self.text = self.text_orig
        try:
            curses.curs_set(0)
        except:
            print('Invisible cursor not supported.')
        return "\n".join(self.text)

    def display(self):
        """Display the editor window and the current contents.

        """
        s = self.text[self.y_offset:self.y_offset + self.win_size_y]
        self.stdscr.clear()
        for y, line in enumerate(s):
            self.stdscr.move(y, 0)
            if not self.pw_mode:
                addstr(self.stdscr, y, 0, line)
        self.stdscr.refresh()
        if self.box:
            self.boxscr.refresh()
        self.scr.refresh()

    def close(self):
        self.text = self.text_orig
        curses.endwin()
        curses.flushinp()
        return False

    def get_key(self):
        c = self.stdscr.getch()
        # 127 is a hack to make sure the Backspace key works properly
        if 0 < c < 256 and c != 127:
            c = chr(c)
        try:
            loop = self.keys[c]()
        except KeyError:
            self.insert_char(c)
            loop = True
        return loop


def main(stdscr, **kwargs):
    return Editor(stdscr, **kwargs)()


def editor(**kwargs):
    if sys.version_info.major < 3:
        lc_all = locale.getlocale(locale.LC_ALL)
        locale.setlocale(locale.LC_ALL, '')
    else:
        lc_all = None
    try:
        return curses.wrapper(main, **kwargs)
    finally:
        if lc_all is not None:
            locale.setlocale(locale.LC_ALL, lc_all)
