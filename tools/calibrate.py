from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Gdk
import cairo
import subprocess
import numpy
import pickle
from scipy.interpolate import griddata
from argparse import ArgumentParser
from sys import stdout
import os.path

ap = ArgumentParser()
ap.add_argument('--use', type=file, default=None)
ap.add_argument('--dump', dest='dump', type=lambda f: file(f, mode='w'), default=None)
ap.add_argument('--output', dest='output', type=lambda f: file(f, mode='w'), default=stdout)
ap.add_argument('--plot', dest='plot', default=None)
ap.add_argument('devid')

class Wacom(object):
    def __init__(self, dev):
        self.dev = dev
        trybin = os.path.join(os.path.dirname(__file__), 'xsetwacom')
        if os.path.exists(trybin):
            self.bin = trybin
        else:
            self.bin = "xsetwacom"

    @property
    def area(self):
        return [
            int(v) for v in self.get_property("Area")
            ]
    @area.setter
    def area(self, area):
        if area is None:
            self.set_property("ResetArea")
        else:
            self.set_property("Area", *area)
    def clear_calibration(self):
        self.set_property("CalibrationGrid")

    def get_property(self, name):
        result = subprocess.check_output([self.bin, "--get", str(self.dev), name])    
        return result.replace('\n', '').split(' ')
    def set_property(self, name, *value):
        subprocess.check_output([self.bin, "--set", str(self.dev), name] + [str(v) for v in value]) 

class Store(object):
    def __init__(self, devw, devh):
        """ mapping from (devw, devh) -> (1, 1) """
        self.devw = devw
        self.devh = devh
        self.scrp = [
            (0, 0),
            (0, 1),
            (1, 0),
            (1, 1)]

        self.devp = [
            (0, 0),
            (0, devh),
            (devw, 0),
            (devw, devh)]
    
    def __len__(self):
        return len(self.scrp) - 4

    def pop(self):
        """ remove last calibration pair, return the scr position """
        if len(self) == 0:
            raise ValueError('popped too many times')
        self.devp.pop()
        return self.scrp.pop()

    def push(self, scrp, devp):
        self.scrp.append(scrp)
        self.devp.append(devp)

    def predict(self, devp):
        """ return the calibration from devp to scrp """
        allscrp = numpy.array(self.scrp)
        intpx = griddata(self.devp, allscrp[..., 0], devp, method='linear')
        intpy = griddata(self.devp, allscrp[..., 1], devp, method='linear')
        return numpy.array((intpx, intpy)).T.copy()
        
class UI(Gtk.DrawingArea):
    __gsignals__ = {
        'aborted': (GObject.SIGNAL_RUN_FIRST, None, ()),
        'finished': (GObject.SIGNAL_RUN_FIRST, None, ()),
    }

    def __init__(self, store, devxmin, devymin, devxmax, devymax):
        Gtk.DrawingArea.__init__(self)
        self.cursor = Gdk.Cursor(Gdk.CursorType.CROSSHAIR)

        self.store = store
        self.devw = store.devw
        self.devh = store.devh
        self.devxmin = devxmin
        self.devymin = devymin
        self.devxmax = devxmax
        self.devymax = devymax
        self.set_can_focus(True)
        self.add_events(
                    Gdk.EventMask.EXPOSURE_MASK |
                    Gdk.EventMask.ENTER_NOTIFY_MASK |
                    Gdk.EventMask.LEAVE_NOTIFY_MASK |
                    Gdk.EventMask.BUTTON_RELEASE_MASK |
                    Gdk.EventMask.BUTTON_PRESS_MASK |
                    Gdk.EventMask.KEY_PRESS_MASK |
                    Gdk.EventMask.POINTER_MOTION_MASK 
                    )
        self.cross_position = None
        self.text = "Click to start"
        self.stylus_position = (0, 0)
        self.points = []
    @property
    def screen_size(self):
        scr = self.get_screen()
        sw = scr.get_width()
        sh = scr.get_height()
        return sw, sh

    def do_realize(self):
        Gtk.DrawingArea.do_realize(self)

    def do_enter_notify_event(self, event):
        win = self.get_window()
        old = win.get_cursor()
        self.get_window().set_cursor(self.cursor)
        self.cursor = old

    def do_leave_notify_event(self, event):
        win = self.get_window()
        old = win.get_cursor()
        self.get_window().set_cursor(self.cursor)
        self.cursor = old
        
    def do_size_request(self, requisition):
        requisition.height = 100
        requisition.width = 100

    def do_size_allocate(self, alloc):
        Gtk.DrawingArea.do_size_allocate(self, alloc)

    def do_motion_notify_event(self, event):
        x, y = event.get_root_coords()
        x, y = self._todev(x, y)
        self.stylus_position = (x, y)
        self.queue_draw()
        
    def do_button_press_event(self, event): 
        x, y = event.get_root_coords()
        x, y = self._todev(x, y)
        self.stylus_position = (x, y)
        if event.button == 1:
            cp = self.store.predict(self.stylus_position)
            self.cross_position = cp
        self.queue_draw()

    def do_button_release_event(self, event): 
        x, y = event.get_root_coords()
        x, y = self._todev(x, y)
        self.stylus_position = (x, y)
        if event.button == 1:
            self.store.push(self.cross_position, self.stylus_position)
        self.queue_draw()

    def do_key_press_event(self, event):
        sw, sh = self.screen_size
        if event.state & Gdk.ModifierType.SHIFT_MASK:
            step = 5.0
        else:
            step = 1.0

        if event.keyval == Gdk.KEY_Escape:
            self.emit('finished')
        elif event.keyval == Gdk.KEY_Up:
            self.cross_position[1] -= step / sh
        elif event.keyval == Gdk.KEY_Down:
            self.cross_position[1] += step / sh
        elif event.keyval == Gdk.KEY_Left:
            self.cross_position[0] -= step / sw
        elif event.keyval == Gdk.KEY_Right:
            self.cross_position[0] += step / sw 
        self.queue_draw()

    def _todev(self, x, y):
        """ convert screen coord to dev coord """
        sw, sh = self.screen_size
        devx = 1.0 * x / sw * (self.devxmax - self.devxmin) + self.devxmin
        devy = 1.0 * y / sh * (self.devymax - self.devymin) + self.devymin
        return devx, devy

    def do_draw(self, context):

        # do not use screen size for ease of debugging
        width = self.get_allocated_width()
        height = self.get_allocated_height()
        context.push_group()
        fgcolor = (1, 1, 1, 1)
        bgcolor = (0, 0, 0, 1)
        crosscolor = (0, 1, 0, 1)

        border_color = (1, 1, 1, 0.5)
        stylus_color = (0, 0, 1, 1.0)
        picked_color = (0, 1, 1, 0.5)

        # the background 
        context.set_source_rgba(*bgcolor)
        context.rectangle(0, 0, width, height)
        context.fill()

        # main label text
        context.select_font_face("monospace", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        context.set_font_size(48)
        xb, yb, ltw, lth, xa, ya = context.text_extents(self.text)
        context.set_source_rgba(*fgcolor)
        context.move_to(width / 2 - ltw / 2, height / 2 - lth / 2)
        context.show_text(self.text)

        # current dev pos
        context.set_font_size(28)
        text = 'Stylus Reading: %05d, %05d' % self.stylus_position
        xb, yb, ptw, pth, xa, ya = context.text_extents(text)
        context.set_source_rgba(*stylus_color)
        ptw = ((ptw // 10) + 1) * 10
        pth = ((pth // 10) + 1) * 10
        context.move_to(width / 2 - ptw / 2, height / 2 + lth )
        context.show_text(text)

        if self.cross_position is not None:
            x, y = self.cross_position
            sw, sh = self.screen_size
            x *= sw
            y *= sh
            self.draw_cross(context, crosscolor, x, y, 10, 1)
            # current scr pos
            context.set_font_size(28)
            ct = '%5g %5g' % (x, y)
            xb, yb, stw, sth, xa, ya = context.text_extents(ct)
            context.set_source_rgba(*fgcolor)
            context.move_to(width / 2 - stw / 2, height / 2 + lth + pth)
            context.show_text(ct)

        for pt in self.store.scrp:
            sw, sh = self.screen_size
            x, y = pt
            x *= sw
            y *= sh
            self.draw_cross(context, crosscolor, x, y, 4, 1)
            
        context.set_source(context.pop_group())
        context.paint()

    def draw_cross(self, context, color, x, y, size, linewidth):
        context.set_source_rgba(*color)
        context.set_line_width(linewidth)
        context.move_to(x-size, y)
        context.line_to(x+size, y)
        context.stroke()
        context.move_to(x, y-size)
        context.line_to(x, y+size)
        context.stroke()
        context.arc(x, y, size * 0.5, 0, 2 * numpy.pi)
        context.stroke()

class MyMainLoop(object):
    exception = None
    finish = False
    @classmethod
    def quit_with_exception(kls, exception):
        kls.exception = exception
        kls.finish = True
    @classmethod
    def quit(kls):
        kls.finish = True
    def __new__(kls):
        while not kls.finish:
            if not Gtk.main_iteration ():
                    break
            if kls.exception:
                raise kls.exception
class RewindableIter(object):
    def __init__(self, l):
        self.l = l
        self.i = 0
    def __iter__(self):
        return self
    def rewind(self):
        self.i = self.i - 1
        if self.i < 0:
            raise Exception("Too much rewinding")
    def next(self):
        rt = self.l[self.i]
        self.i = self.i + 1
        if self.i == len(self.l):
            raise StopIteration
        return rt

def myunique(a):
    """ unique along the first axis """
    b = numpy.ascontiguousarray(a).view(numpy.dtype((numpy.void, a.dtype.itemsize * a.shape[1])))
    _, idx = numpy.unique(b, return_index=True)
    unique_a = a[idx]
    return unique_a

def measure(wacom, store):
    wacom.area = None
    devxmin, devymin, devxmax, devymax = wacomdev.area
    if store is None:
        store = Store(devxmax, devymax)

    wacom.area = devxmin, devymin, devxmax, devymax
    devxmin, devymin, devxmax, devymax = wacomdev.area

    w = Gtk.Window()
    ui = UI(store, devxmin, devymin, devxmax, devymax)
    ui.show()
    w.add(ui)

    def aborted(calib):
        MyMainLoop.quit_with_exception(
            Exception("aborted!"))

    def finished(calib):
        MyMainLoop.quit()

    w.connect('destroy', aborted)
    ui.connect('aborted', aborted)
    ui.connect('finished', finished)

    w.show()
    # must be after show.
    w.fullscreen()
    MyMainLoop()

    return store

ns = ap.parse_args()
wacomdev = Wacom(ns.devid)

if ns.use is not None:
    store = pickle.load(ns.use)
else:
    store = None
measure(wacomdev, store)

if ns.dump is not None:
    pickle.dump(store, ns.dump)

grid = numpy.concatenate(
    [numpy.linspace(0, 0.1, 20, endpoint=False),
    numpy.linspace(0.1, 0.9, 20, endpoint=True),
    1.0 - numpy.linspace(0, 0.1, 20, endpoint=False)[::-1]])

devxgrid = numpy.int64(store.devw * grid)
devygrid = numpy.int64(store.devh * grid)
devxygrid = numpy.array([(x, y) for y in devygrid for x in devxgrid])
scrxy = store.predict(devxygrid)
scrxy = scrxy.reshape(len(devygrid), len(devxgrid), 2)
lines = []
lines.append(', '.join(['%d' % x for x in devxgrid]))
lines.append(', '.join(['%d' % y for y in devygrid]))
for row in scrxy:
    lines.append(', '.join(['%g, %g' % (p[0], p[1]) for p in row]))
ns.output.write(';\n'.join(lines) + '\n')

if ns.plot:
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    fig = Figure(figsize=(8, 8), dpi=200)
    ax = fig.add_subplot(111)
    ax.plot(*scrxy.reshape(-1, 2).T, marker=',', ls='none')
    canvas = FigureCanvasAgg(fig)
    fig.savefig(ns.plot)
