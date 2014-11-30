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

    def predict(self, scrp):
        """ predict the devp of scrp based on measured points """
        devp = (griddata(self.scrp, self.devp[..., 0], scrp, method='linear'),
                griddata(self.scrp, self.devp[..., 1], scrp, method='linear'))
        return devp 

    def invert(self, devp):
        """ return the calibration from devp to scrp """
        allscrp = numpy.array(self.scrp)
        intpx = griddata(self.devp, allscrp[..., 0], devp, method='linear')
        intpy = griddata(self.devp, allscrp[..., 1], devp, method='linear')
        return numpy.array(zip(intpx, intpy))
        
class UI(Gtk.DrawingArea):
    __gsignals__ = {
        'aborted': (GObject.SIGNAL_RUN_FIRST, None, ()),
        'clicked': (GObject.SIGNAL_RUN_FIRST, None, (int, int)),
        'canceled': (GObject.SIGNAL_RUN_FIRST, None, ()),
        'started': (GObject.SIGNAL_RUN_FIRST, None, ()),
    }

    def __init__(self, store):
        Gtk.DrawingArea.__init__(self)
        self.cursor = Gdk.Cursor(Gdk.CursorType.BLANK_CURSOR)

        self.store = store
        self.devw = store.devw
        self.devh = store.devh

        self.add_events(
                    Gdk.EventMask.EXPOSURE_MASK |
                    Gdk.EventMask.ENTER_NOTIFY_MASK |
                    Gdk.EventMask.LEAVE_NOTIFY_MASK |
                    Gdk.EventMask.BUTTON_RELEASE_MASK |
                    Gdk.EventMask.BUTTON_PRESS_MASK |
                    Gdk.EventMask.POINTER_MOTION_MASK
                    )
        self.cross_position = None
        self.text = "Click to start"
        self.stylus_position = (0, 0)
        self.points = []

    def do_realize(self):
        Gtk.DrawingArea.do_realize(self)

    def do_enter_notify_event(self, event):
        win = self.get_window()
        old = win.get_cursor()
        self.get_window().set_cursor(self.cursor)
        self.cursor = old

    def do_key_press_event(self, event):
        if event.keyval == Gdk.KEY_Escape:
            self.emit('aborted')
        
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
        
    def do_button_release_event(self, event): 
        x, y = event.get_root_coords()
        if event.button == 3:
            self.emit('canceled')
        elif event.button == 1:
            if self.cross_position is None:
                self.emit('started')
            else:
                x, y = self._todev(x, y)
                self.emit('clicked', x, y)

    def _todev(self, x, y):
        """ convert screen coord to dev coord """
        scr = self.get_screen()
        sw = (scr.get_width() - 1)
        sh = (scr.get_height() - 1)
        devx = 1.0 * x / sw * self.devw
        devy = 1.0 * y / sh * self.devh
        return devx, devy

    def do_draw(self, context):
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
            x = x * (width - 1)
            y = y * (height - 1)
            self.draw_cross(context, crosscolor, x, y, 10, 1)
            # current scr pos
            context.set_font_size(28)
            ct = '%5g %5g' % (x, y)
            xb, yb, stw, sth, xa, ya = context.text_extents(ct)
            context.set_source_rgba(*fgcolor)
            context.move_to(width / 2 - stw / 2, height / 2 + lth + pth)
            context.show_text(ct)

        self.draw_stylus_pad(context, border_color, stylus_color, picked_color)
        context.set_source(context.pop_group())
        context.paint()

    def _stylus_reading_to_screen(self, x, y):
        width = self.get_allocated_width()
        height = self.get_allocated_height()
        vw = width / 2
        vh = height / 2
        vxp = width / 4
        vyp = height / 4
        ux = 1.0 * x / self.devw
        uy = 1.0 * y / self.devh
        x = vxp + vw * ux
        y = vyp + vh * uy
        return (x, y) 

    def draw_stylus_pad(self, context, border_color, stylus_color, picked_color):
        width = self.get_allocated_width()
        height = self.get_allocated_height()

        context.set_source_rgba(*border_color)
        x0, y0 = self._stylus_reading_to_screen(0, 0)
        x1, y1 = self._stylus_reading_to_screen(self.devw, self.devh)
        # draw the box
        context.set_line_width(1)
        context.rectangle(x0, y0, x1 - x0, y1 - y0)
        context.stroke()

        x, y = self._stylus_reading_to_screen(*self.stylus_position)
        self.draw_cross(context, stylus_color, x, y, 5, 1)

        for p in self.store.devp:
            x, y = self._stylus_reading_to_screen(*p)
            self.draw_cross(context, picked_color, x, y, 5, 1)


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

    def move_cross(self, x, y):
        self.cross_position = x, y
        self.text = ('SCR %g %g' % (x, y))
        self.queue_draw()

    def pixelize(self, points):
        scr = self.get_screen()
        sw = (scr.get_width() - 1)
        sh = (scr.get_height() - 1)

        points = numpy.array(points, copy=True, dtype='f8')
        points[:, 0] *= sw 
        points[:, 1] *= sh
        points = numpy.floor(points)
        points[:, 0] /= sw
        points[:, 1] /= sh
        return points

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
        print self.i
        self.i = self.i - 1
        if self.i < 0:
            raise Exception("Too much rewinding")
    def next(self):
        print self.i
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

def measure(wacom):
    wacom.area = None
    devxmin, devymin, devxmax, devymax = wacomdev.area

    store = Store(devxmax, devymax)

    w = Gtk.Window()
    ui = UI(store)
    ui.show()
    w.add(ui)

    corner = [0.0, 0.005, 0.01, 0.15, 0.02, 0.03, 0.04, 0.06, 0.08]
    def buildcorners(grid):
        x, y = numpy.meshgrid(grid, grid)
        x = x.ravel()
        y = y.ravel()
        corner = numpy.array(zip(x, y))
        points = numpy.concatenate([
            zip(x, y),
            zip(1. - x, y),
            zip(x, 1. - y),
            zip(1. - x, 1. - y),
            ]
        )
        return points
    c1 = buildcorners([0.0, 0.01])
#    c2 = buildcorners([0.0, 0.04, 0.08])
    points = numpy.concatenate([c1, c1], axis=0)
    points = myunique(points)
    points = ui.pixelize(points)

    iterator = RewindableIter(points)

    def started(calib):
        scrp = iterator.next()
        calib.move_cross(*scrp)

    def clicked(calib, x, y):
        store.push(calib.cross_position, (x, y))
        try:
            scrp = iterator.next()
            calib.move_cross(*scrp)
        except StopIteration:
            MyMainLoop.quit()
            return  

    def canceled(calib):
        if len(store) == 0: 
            return
        iterator.rewind()
        iterator.rewind()
        store.pop()
        scrp = iterator.next()
        calib.move_cross(*scrp)

    def aborted(calib):
        MyMainLoop.quit_with_exception(
            Exception("aborted!"))

    w.connect('destroy', aborted)
    ui.connect('started', started)
    ui.connect('clicked', clicked)
    ui.connect('canceled', canceled)
    ui.connect('aborted', aborted)

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
    store = measure(wacomdev)

if ns.dump is not None:
    pickle.dump(store, ns.dump)

grid = numpy.concatenate(
    [numpy.linspace(0, 0.1, 10, endpoint=False),
    numpy.linspace(0.1, 0.9, 8, endpoint=True),
    1.0 - numpy.linspace(0, 0.1, 10, endpoint=False)])

devxgrid = numpy.int64(store.devw * grid)
devygrid = numpy.int64(store.devh * grid)
devxygrid = numpy.array([(x, y) for y in devygrid for x in devxgrid])
scrxy = store.invert(devxygrid)
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
    fig = Figure()
    ax = fig.add_subplot(111)
    ax.plot(*scrxy.reshape(-1, 2).T, marker='.', ls='none')
    canvas = FigureCanvasAgg(fig)
    fig.savefig(ns.plot)
