"""Temporary comparison placement using the already required X11 library."""
import ctypes
import ctypes.util


class Windows:
    def __init__(self):
        self.x=ctypes.CDLL(ctypes.util.find_library('X11') or 'libX11.so.6')
        self.x.XOpenDisplay.argtypes=[ctypes.c_char_p];self.x.XOpenDisplay.restype=ctypes.c_void_p
        self.x.XDefaultRootWindow.argtypes=[ctypes.c_void_p];self.x.XDefaultRootWindow.restype=ctypes.c_ulong
        self.x.XCloseDisplay.argtypes=[ctypes.c_void_p]
        self.x.XFree.argtypes=[ctypes.c_void_p]
        self.x.XQueryTree.argtypes=[ctypes.c_void_p,ctypes.c_ulong,ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.c_ulong),ctypes.POINTER(ctypes.POINTER(ctypes.c_ulong)),ctypes.POINTER(ctypes.c_uint)]
        class Hint(ctypes.Structure):
            _fields_=[('name',ctypes.c_void_p),('klass',ctypes.c_void_p)]
        self.hint=Hint
        self.x.XGetClassHint.argtypes=[ctypes.c_void_p,ctypes.c_ulong,ctypes.POINTER(Hint)]
        self.x.XGetGeometry.argtypes=[ctypes.c_void_p,ctypes.c_ulong,ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_uint),
            ctypes.POINTER(ctypes.c_uint),ctypes.POINTER(ctypes.c_uint),ctypes.POINTER(ctypes.c_uint)]
        self.x.XMoveWindow.argtypes=[ctypes.c_void_p,ctypes.c_ulong,ctypes.c_int,ctypes.c_int]
        self.x.XFlush.argtypes=[ctypes.c_void_p]
        self.error_type=ctypes.CFUNCTYPE(ctypes.c_int,ctypes.c_void_p,ctypes.c_void_p)
        self.error_callback=self.error_type(lambda *_:0)
        self.x.XSetErrorHandler.argtypes=[ctypes.c_void_p];self.x.XSetErrorHandler.restype=ctypes.c_void_p
        self.previous_error_handler=self.x.XSetErrorHandler(ctypes.cast(self.error_callback,ctypes.c_void_p))
        self.display=self.x.XOpenDisplay(None)
        if not self.display:raise RuntimeError('Cannot open X11 for preview comparison')

    def klass(self,window):
        hint=self.hint()
        if not self.x.XGetClassHint(self.display,window,ctypes.byref(hint)):return None
        try:return tuple(ctypes.string_at(p).decode() if p else '' for p in [hint.name,hint.klass])
        finally:
            for p in [hint.name,hint.klass]:
                if p:self.x.XFree(p)

    def find(self,klass):
        root=ctypes.c_ulong();parent=ctypes.c_ulong();children=ctypes.POINTER(ctypes.c_ulong)();n=ctypes.c_uint()
        if not self.x.XQueryTree(self.display,self.x.XDefaultRootWindow(self.display),ctypes.byref(root),
                ctypes.byref(parent),ctypes.byref(children),ctypes.byref(n)):return []
        try:return [int(children[i]) for i in range(n.value) if self.klass(children[i])==klass]
        finally:
            if children:self.x.XFree(children)

    def geometry(self,window):
        root=ctypes.c_ulong();x=ctypes.c_int();y=ctypes.c_int();w=ctypes.c_uint();h=ctypes.c_uint();b=ctypes.c_uint();d=ctypes.c_uint()
        if not self.x.XGetGeometry(self.display,window,ctypes.byref(root),ctypes.byref(x),ctypes.byref(y),
                ctypes.byref(w),ctypes.byref(h),ctypes.byref(b),ctypes.byref(d)):raise RuntimeError('Cannot read comparison window')
        return dict(x=x.value,y=y.value,width=w.value,height=h.value)

    def move(self,window,x,y):
        self.x.XMoveWindow(self.display,window,x,y);self.x.XFlush(self.display)

    def close(self):
        if self.display:
            self.x.XCloseDisplay(self.display);self.display=None
            self.x.XSetErrorHandler(self.previous_error_handler)


def comparison_position(old,new,head,gap):
    intersects=(old['x']<new['x']+new['width'] and new['x']<old['x']+old['width']
                and old['y']<new['y']+new['height'] and new['y']<old['y']+old['height'])
    if not intersects:return None
    y=new['y']+new['height']+gap
    if y+old['height']>head['y']+head['height']:
        raise RuntimeError('Two comparison windows cannot fit without overlapping')
    return {'x':old['x'],'y':y}
