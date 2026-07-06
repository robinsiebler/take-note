from __future__ import annotations

import logging
import time

from PySide6.QtCore import QThread, Signal

logger = logging.getLogger(__name__)

DEFAULT_KEY = "n"
DEFAULT_MODIFIERS = ("control", "mod1")  # Ctrl+Alt+N


class HotkeyListener(QThread):
    """Global hotkey via raw python-xlib XGrabKey.

    Relies on the app running through XWayland (QT_QPA_PLATFORM=xcb) so a
    real X11 connection/key-grab is available even on a Wayland session.
    `triggered` is emitted from this worker thread but Qt auto-delivers it
    as a queued connection to any main-thread slot, so no manual
    cross-thread marshaling is needed.
    """

    triggered = Signal()
    grab_failed = Signal()

    def __init__(self, key: str = DEFAULT_KEY, modifiers=DEFAULT_MODIFIERS, parent=None):
        super().__init__(parent)
        self.key = key
        self.modifiers = modifiers
        self._stop = False

    def stop(self):
        self._stop = True
        self.wait(1000)

    def run(self):
        try:
            from Xlib import X, XK, display
            from Xlib.error import BadAccess
        except ImportError:
            logger.warning("python-xlib not available; global hotkey disabled")
            self.grab_failed.emit()
            return

        try:
            disp = display.Display()
        except Exception:
            logger.warning("Could not open X display; global hotkey disabled")
            self.grab_failed.emit()
            return

        root = disp.screen().root
        root.change_attributes(event_mask=X.KeyPressMask)

        keysym = XK.string_to_keysym(self.key.upper())
        keycode = disp.keysym_to_keycode(keysym)

        mod_map = {
            "control": X.ControlMask,
            "mod1": X.Mod1Mask,  # Alt
            "shift": X.ShiftMask,
        }
        base_mods = 0
        for name in self.modifiers:
            base_mods |= mod_map[name]

        # NumLock/CapsLock/ScrollLock are modifier bits too; X won't deliver
        # the event if one is held unless every combination is also grabbed.
        ignored_combos = [0, X.LockMask, X.Mod2Mask, X.LockMask | X.Mod2Mask]

        def _raise(err):
            raise err

        grabbed_any = False
        for ignore in ignored_combos:
            try:
                # grab_key() only queues the request; python-xlib's default
                # error handler for an already-owned combo just prints "X
                # protocol error: ..." to stderr and swallows it rather than
                # raising. Passing onerror + calling sync() routes any
                # pending BadAccess through our own callback instead, so it
                # actually surfaces as an exception right here.
                root.grab_key(
                    keycode, base_mods | ignore, True, X.GrabModeAsync, X.GrabModeAsync,
                    onerror=_raise,
                )
                disp.sync()
                grabbed_any = True
            except BadAccess:
                logger.warning("Hotkey combo unavailable for one modifier-lock variant")

        disp.flush()

        if not grabbed_any:
            self.grab_failed.emit()
            disp.close()
            return

        while not self._stop:
            if disp.pending_events():
                event = disp.next_event()
                if event.type == X.KeyPress:
                    self.triggered.emit()
            else:
                time.sleep(0.05)

        try:
            root.ungrab_key(keycode, X.AnyModifier)
        except Exception:
            pass
        disp.close()
