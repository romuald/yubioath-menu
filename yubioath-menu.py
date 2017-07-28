#!/usr/bin/env python
from __future__ import unicode_literals, print_function

import re
import os
import io
import sys
import cgi

from subprocess import Popen, PIPE


try:
    import gtk
except ImportError:
    # python3 -> gruik compat
    from gi import pygtkcompat

    pygtkcompat.enable_gtk(version='3.0')


FILTER = []
LAST_EVENT_TIME = 0

def get_yubidata():
    cmd = Popen(['yubioath'], stdout=PIPE)

    for line in cmd.stdout:
        label, token = line.strip().rsplit(' ', 1)
        yield label.strip(), token


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
        if len(visible) == 1 and visible[0] is not menu.no_match:
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
        if item is menu.no_match:
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


def main():
    menu = gtk.Menu()

    no_match = gtk.MenuItem('')
    no_match.set_sensitive(False)
    menu.append(no_match)
    menu.no_match = no_match

    for label, token in get_yubidata():
        item = gtk.MenuItem(label)
        item.origin = label
        item.token = token
        item.connect('activate', on_menu_select)

        menu.append(item)

    menu.connect('hide', gtk.main_quit)
    menu.connect('key-release-event', on_key_press)
    menu.show_all()

    no_match.hide()

    menu.popup(parent_menu_shell=None,
               parent_menu_item=None,
               func=None,
               data=None,
               button=1,
               activate_time=0)

    gtk.main()

if __name__ == '__main__':
    main()
