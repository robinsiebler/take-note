from __future__ import annotations

import logging
import os
import time

from PySide6.QtCore import QThread, Signal

logger = logging.getLogger(__name__)

# ICCCM WM_STATE property values (not the newer EWMH _NET_WM_STATE atom
# list) — the classic, more universally-maintained way window managers
# and apps report minimized ("Iconic") vs. normal.
WM_STATE_NORMAL = 1
WM_STATE_ICONIC = 3


def list_windows() -> list[tuple[int, str]]:
    """Enumerate top-level windows via EWMH's _NET_CLIENT_LIST, returning
    (window_id, title) pairs for the "Stick to Window…" picker.

    Skips windows with no title and windows owned by this same process
    (_NET_WM_PID, matched against os.getpid()) — so a note can't be stuck
    to itself or another note. _NET_WM_STATE_SKIP_TASKBAR (set on every
    note/board window via x11_wm.set_skip_taskbar) was tried first and
    looked like the natural fit, but confirmed directly via xprop-style
    inspection that KWin never actually echoes it back into a window's own
    _NET_WM_STATE — it's seemingly taskbar-widget-only, not reflected
    anywhere queryable. _NET_WM_PID is unaffected by that and reliable.
    """
    try:
        from Xlib import display
    except ImportError:
        logger.warning("python-xlib not available; cannot list windows")
        return []

    try:
        disp = display.Display()
    except Exception:
        logger.warning("Could not open X display; cannot list windows")
        return []

    try:
        root = disp.screen().root
        net_client_list = disp.intern_atom("_NET_CLIENT_LIST")
        net_wm_name = disp.intern_atom("_NET_WM_NAME")
        net_wm_pid = disp.intern_atom("_NET_WM_PID")
        utf8_string = disp.intern_atom("UTF8_STRING")
        own_pid = os.getpid()

        client_list = root.get_full_property(net_client_list, 0)
        if client_list is None:
            return []

        windows = []
        for window_id in client_list.value:
            win = disp.create_resource_object("window", window_id)

            pid_prop = win.get_full_property(net_wm_pid, 0)
            if pid_prop is not None and len(pid_prop.value) > 0 and pid_prop.value[0] == own_pid:
                continue

            name_prop = win.get_full_property(net_wm_name, utf8_string)
            if name_prop is None or not name_prop.value:
                continue
            raw_title = name_prop.value
            title = raw_title.decode("utf-8", "replace") if isinstance(raw_title, bytes) else raw_title
            if not title:
                continue

            windows.append((window_id, title))
        return windows
    finally:
        disp.close()


def is_window_iconic(window_id: int) -> bool:
    """A one-shot check of a window's *current* WM_STATE, for the moment a
    note is first stuck to an already-minimized window — WindowWatcher's
    own signals only fire on *future* state changes, so without this the
    note would stay visible until the next unrelated minimize/restore."""
    try:
        from Xlib import display
    except ImportError:
        return False

    try:
        disp = display.Display()
    except Exception:
        return False

    try:
        win = disp.create_resource_object("window", window_id)
        wm_state_atom = disp.intern_atom("WM_STATE")
        prop = win.get_full_property(wm_state_atom, 0)
        return prop is not None and len(prop.value) > 0 and prop.value[0] == WM_STATE_ICONIC
    except Exception:
        return False
    finally:
        disp.close()


class WindowWatcher(QThread):
    """Watches one external window for minimize/restore/close via raw
    python-xlib — same approach as hotkey.HotkeyListener (a dedicated X11
    connection and a polling event loop), since Qt has no cross-process
    window-state API of its own. `minimized`/`restored`/`closed` are
    emitted from this worker thread but Qt auto-delivers them as queued
    connections to any main-thread slot, so no manual cross-thread
    marshaling is needed (same as HotkeyListener.triggered)."""

    minimized = Signal()
    restored = Signal()
    closed = Signal()

    def __init__(self, window_id: int, parent=None):
        super().__init__(parent)
        self.window_id = window_id
        self._stop = False

    def stop(self):
        self._stop = True
        self.wait(1000)

    def run(self):
        try:
            from Xlib import X, display
        except ImportError:
            logger.warning("python-xlib not available; cannot watch window")
            return

        try:
            disp = display.Display()
        except Exception:
            logger.warning("Could not open X display; cannot watch window")
            return

        try:
            win = disp.create_resource_object("window", self.window_id)
            wm_state_atom = disp.intern_atom("WM_STATE")

            try:
                win.change_attributes(event_mask=X.PropertyChangeMask | X.StructureNotifyMask)
                disp.sync()
            except Exception:
                # Window was already gone by the time we tried to watch it.
                self.closed.emit()
                return

            while not self._stop:
                if disp.pending_events():
                    ev = disp.next_event()
                    if ev.type == X.DestroyNotify:
                        self.closed.emit()
                        return
                    if ev.type == X.PropertyNotify and ev.atom == wm_state_atom:
                        prop = win.get_full_property(wm_state_atom, 0)
                        if prop is not None and len(prop.value) > 0:
                            state = prop.value[0]
                            if state == WM_STATE_ICONIC:
                                self.minimized.emit()
                            elif state == WM_STATE_NORMAL:
                                self.restored.emit()
                else:
                    time.sleep(0.1)
        finally:
            disp.close()
