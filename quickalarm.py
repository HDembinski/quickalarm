#!/usr/bin/python
from gi.repository import Gtk, GObject, Gst
from gi.repository import AppIndicator3 as appindicator
from datetime import datetime, timedelta
import os
import time
import signal
import sys
import threading
import warnings


class Alarm(object):

    class AudioSequence(threading.Thread):
        def __init__(self, parent):
            threading.Thread.__init__(self)
            self.parent = parent
            self.daemon = True
            self.do_stop = False

        def run(self):
            self.do_stop = False
            for j in xrange(5):
                for i in xrange(2):
                    if self.do_stop:
                        return
                    self.parent.startTone(440)
                    time.sleep(0.2)
                    self.parent.stopTone()
                    time.sleep(0.05)
                time.sleep(2)

        def stop(self):
            self.do_stop = True
            self.parent.stopTone()

    def __init__(self):
        self.src = Gst.ElementFactory.make("audiotestsrc", None)
        self.sink = Gst.ElementFactory.make("autoaudiosink", None)
        self.pipe = Gst.Pipeline()
        self.pipe.add(self.src)
        self.pipe.add(self.sink)
        self.src.link(self.sink)

    def startTone(self, freq):
        self.src.set_property("freq", freq)
        self.pipe.set_state(Gst.State.PLAYING)

    def stopTone(self):
        self.pipe.set_state(Gst.State.READY)    

    def showDialog(self, msg):
        dialog = Gtk.MessageDialog(None, 0,
                                   Gtk.MessageType.INFO,
                                   Gtk.ButtonsType.OK,
                                   title="Quick Alarm")
        dialog.format_secondary_text(msg)
        dialog.set_modal(True)
        dialog.set_keep_above(True)
        dialog.present()
        dialog.run()
        dialog.destroy()
        del dialog

    def __call__(self, time):
        seq = Alarm.AudioSequence(self)
        seq.start()
        msg = "It is %02i:%02i" % (time.hour, time.minute)
        self.showDialog(msg)
        if seq.isAlive():
            seq.stop()


class Timer(object):
    def __init__(self, timeout, action, *args):
        """Negative timeout means periodic restart."""
        def callback():
            action(*args)
            return timeout < 0
        self.source_id = GObject.timeout_add_seconds(abs(timeout), callback)

    def __del__(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            GObject.source_remove(self.source_id)


def now():
    t = time.localtime()
    now = datetime(t.tm_year, t.tm_mon, t.tm_mday,
                   t.tm_hour, t.tm_min, t.tm_sec)
    return now


def makeMenu(ind):
    t0 = now()
    ds = 60 - t0.second
    dm = int((t0.minute // 10 + 1) * 10) - t0.minute
    t = t0 + timedelta(minutes=dm - 1, seconds=ds)
    timeList = [t]
    def add(dm):
        t = timeList[-1] + timedelta(minutes=dm)
        timeList.append(t)
    while timeList[-1].minute != 0 or len(timeList) < 6:
        add(5)
    for i in xrange(12):
        add(10)
    for i in xrange(6):
        add(30)

    if ind.alarmTimer is None:
        ind.set_status(appindicator.IndicatorStatus.ACTIVE)
        tmark = t0
    else:
        ind.set_status(appindicator.IndicatorStatus.ATTENTION)
        tmark = ind.alarmTime

    menu = Gtk.Menu()
    for t in timeList:
        label = "%02i:%02i" % (t.hour, t.minute)
        if tmark == t:
            # glabel = menu_item.get_child()
            # glabel.set_markup("<b>" + glabel.get_text() + "</b>")
            # img = Gtk.Image.new_from_stock(Gtk.STOCK_NEW, 24)
            label = "[" + label + "]"
        menu_item = Gtk.ImageMenuItem(label)
        menu_item.connect("activate", startTimerAction, ind, t)
        menu_item.show()
        menu.append(menu_item)

    sep = Gtk.SeparatorMenuItem()
    sep.show()
    menu.append(sep)
    stop_item = Gtk.MenuItem("Stop")
    stop_item.connect("activate", stopAction, ind)
    stop_item.show()
    menu.append(stop_item)
    sep = Gtk.SeparatorMenuItem()
    sep.show()
    menu.append(sep)
    quit_item = Gtk.MenuItem("Quit")
    quit_item.connect("activate", quitAction)
    quit_item.show()
    menu.append(quit_item)
    ind.set_menu(menu)


def alarmAction(ind, time):
    ind.alarm(time)
    stopAction(None, ind)


def quitAction(menu_item):
    Gtk.main_quit()


def startTimerAction(menu_item, ind, t):
    t0 = now()
    dt = (t - t0).total_seconds()
    ind.alarmTimer = Timer(dt, alarmAction, ind, t)
    ind.alarmTime = t
    makeMenu(ind)


def stopAction(menu_item, ind):
    ind.alarmTimer = None
    ind.alarmTime = None
    makeMenu(ind)


if __name__ == "__main__":
    GObject.threads_init()
    Gst.init(sys.argv)

    signal.signal(signal.SIGINT, signal.SIG_DFL)
    ind = appindicator.Indicator.new(
        "quick-alarm",
        "empathy-available",
        appindicator.IndicatorCategory.APPLICATION_STATUS,
        )
    ind.set_attention_icon("empathy-extended-away")
    ind.set_status(appindicator.IndicatorStatus.ACTIVE)

    ind.alarm = Alarm()
    ind.alarmTimer = None
    ind.alarmTime = None
    makeMenu(ind)
    # periodically re-create menu every 1 min
    ind.menuTimer = Timer(-60, makeMenu, ind)

    Gtk.main()
