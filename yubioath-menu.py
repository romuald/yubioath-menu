#!/usr/bin/env python
from __future__ import unicode_literals, print_function

import re
import os
import io
import sys
import cgi

from subprocess import Popen, PIPE

gtk = None
FILTER = []
LAST_EVENT_TIME = 0

def gtk_error(message):
    msg = gtk.MessageDialog(type=gtk.MESSAGE_ERROR,
                            flags=gtk.DIALOG_MODAL,
                            buttons=gtk.BUTTONS_OK)
    msg.set_markup(message)
    msg.run()


def error(message, fatal=False):
    if sys.stdin.isatty()or gtk is None:
        print(message, file=sys.stderr)
    else:
        gtk_error(message)

    if fatal:
        sys.exit(1)


def which(program):
    """Which witch?"""
    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            path = path.strip('"')
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file

    return None


try:
    from yubioath.core.ccid import open_scard
    from yubioath.core.controller import Controller as YubiController
except ImportError:
    open_scard = YubiController = None


try:
    import gtk
except ImportError:
    # python3 -> gruik compat
    try:
        from gi import pygtkcompat

        pygtkcompat.enable_gtk(version='3.0')
    except ImportError:
        pass


class NoCardFound(Exception):
    pass


def get_yubidata():
    cmd = Popen(['yubioath'], stdout=PIPE)

    for line in cmd.stdout:
        label, token = line.strip().rsplit(' ', 1)
        yield label.strip(), token

def get_yubidata():
    controller = YubiController()
    card = open_scard()

    if card is None:
        raise NoCardFound

    for cred, token in controller.read_creds(card, None, None, None):
        yield cred.name, token


def type_token(token, delay=0):
    if delay > 0:
        sleep(delay)
    cmd = Popen(['xdotool', 'type', '--file', '-'], stdin=PIPE)

    cmd.stdin.write(token.encode('utf-8'))
    cmd.stdin.flush()
    cmd.stdin.close()
    cmd.wait()


def on_menu_select(item):
    type_token(item.token)


def activate_by_gruik(menu):
    # simulate events to activate menu item since
    # xdotool + gtk event seems to break

    # Press Down
    ev = gtk.gdk.Event(gtk.gdk.KEY_PRESS)
    ev.send_event = True
    ev.time = 0
    ev.keyval = gtk.keysyms.Down
    ev.window = menu.get_window()
    ev.state = gtk.gdk.KEY_PRESS_MASK
    ev.hardware_keycode = 116  # Key Down
    ev.put()

    # Press Return
    ev = gtk.gdk.Event(gtk.gdk.KEY_PRESS)
    ev.send_event = True
    ev.time = 0
    ev.keyval = gtk.keysyms.Return
    ev.window = menu.get_window()
    ev.state = gtk.gdk.KEY_PRESS_MASK
    ev.hardware_keycode = 36  # Return
    ev.put()


def exit(*args):
    gtk.main_quit()


def get_visible_children(menu):
    return [item for item in menu.get_children() if item.get_visible()]


def on_key_press(menu, event):
    global LAST_EVENT_TIME

    # key-release events seems to be triggered twice
    if event.get_time() == LAST_EVENT_TIME:
        return
    LAST_EVENT_TIME = event.get_time()

    string = event.string

    if event.keyval == gtk.keysyms.BackSpace:
        FILTER[:] = []
    elif event.keyval in (gtk.keysyms.KP_Enter, gtk.keysyms.Return):
        # Enter, validate if only one match shown
        visible = get_visible_children(menu)
        if len(visible) == 1 and visible[0].get_sensitive():
            activate_by_gruik(menu)
        return
    elif len(string):
        FILTER.append(string)
    else:
        # unhandled key
        return

    match = False
    search = ''.join(FILTER)
    regsearch = re.compile('(%s)' % re.escape(cgi.escape(search)), re.I)

    for item in menu.get_children():
        if not item.get_sensitive():
            continue

        clabel = cgi.escape(item.origin)
        if regsearch.search(clabel):
            if search != '':
                markup = regsearch.sub('<b>\\1</b>', clabel)
            else:
                markup = clabel

            item.get_child().set_markup(markup)
            item.show()
            match = True
        else:
            item.get_child().set_markup(clabel)
            item.hide()

    if match:
        menu.no_match.hide()
    else:
        menu.no_match.get_child().set_markup('<i>No match for %s</i>' %
                                             cgi.escape(search))
        menu.no_match.show()


def checkup():
    """Check global import / binary availability"""

    if gtk is None:
        error('Unable to import python GTK module, aborting', True)

    if YubiController is None:
        error('Unable to import python yubioath module. Is it installed?',
              True)

    if which('xdotool') is None:
        error('Unable to find the xdotool binary, aborting', True)


def main():
    checkup()

    menu = gtk.Menu()

    menu.no_match = gtk.MenuItem('')
    menu.no_match.set_sensitive(False)
    menu.append(menu.no_match)

    no_yubikey= gtk.MenuItem('')
    no_yubikey.set_sensitive(False)
    no_yubikey.get_child().set_markup('<b>No Yubikey found</b>')
    menu.append(no_yubikey)

    try:
        for label, token in get_yubidata():
            item = gtk.MenuItem(label)
            item.origin = label
            item.token = token
            item.connect('activate', on_menu_select)
            item.show()

            menu.append(item)
    except NoCardFound:
        no_yubikey.show()

    menu.connect('hide', gtk.main_quit)
    menu.connect('key-release-event', on_key_press)

    menu.popup(parent_menu_shell=None,
               parent_menu_item=None,
               func=None,
               data=None,
               button=1,
               activate_time=0)

    gtk.main()

if __name__ == '__main__':
    main()
