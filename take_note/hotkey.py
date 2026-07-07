from __future__ import annotations

import logging
import time

from PySide6.QtCore import QThread, Signal

logger = logging.getLogger(__name__)

DEFAULT_KEY = "n"
DEFAULT_MODIFIERS = ("control", "mod1")  # Ctrl+Alt+N

# Maps QKeySequence's string modifier names (as produced by
# QKeySequence.toString(), e.g. "Ctrl+Alt+N") to our internal modifier
# names used below to build the X11 modifier mask.
_QT_MOD_NAMES = {
    "ctrl": "control",
    "alt": "mod1",
    "shift": "shift",
    "meta": "meta",  # Super/Windows key
}


def parse_shortcut(sequence: str) -> tuple[str, tuple[str, ...]]:
    """Parse a QKeySequence string like 'Ctrl+Alt+N' into a (key, modifiers)
    pair usable by HotkeyListener."""
    parts = [p.strip() for p in sequence.split("+") if p.strip()]
    if not parts:
        raise ValueError(f"Empty shortcut: {sequence!r}")
    *mod_parts, key = parts
    modifiers = tuple(
        _QT_MOD_NAMES[m.lower()] for m in mod_parts if m.lower() in _QT_MOD_NAMES
    )
    return key, modifiers


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
    grab_succeeded = Signal()

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
            "meta": X.Mod4Mask,  # Super/Windows key
        }
        base_mods = 0
        for name in self.modifiers:
            base_mods |= mod_map[name]

        # NumLock/CapsLock/ScrollLock are modifier bits too; X won't deliver
        # the event if one is held unless every combination is also grabbed.
        ignored_combos = [0, X.LockMask, X.Mod2Mask, X.LockMask | X.Mod2Mask]

        # grab_key() only queues the request; errors come back asynchronously.
        # python-xlib's own dispatcher (Xlib/protocol/rq.py,
        # call_error_handler) invokes onerror as handler(error, request) and
        # — this is the part that isn't obvious from the docs — catches
        # whatever the handler does with that call itself, logging it rather
        # than letting it propagate back through disp.sync(). So `raise err`
        # here never actually reaches an `except BadAccess` around sync():
        # the exception dies inside python-xlib's own try/except and
        # `grabbed_any` would incorrectly stay True even on a real conflict.
        # The reliable pattern is to have onerror just record the failure in
        # a plain variable and check that after sync() returns, with no
        # exception propagation involved at all.
        grab_failed_this_attempt = False

        def _record_failure(err, request=None):
            nonlocal grab_failed_this_attempt
            grab_failed_this_attempt = True

        grabbed_any = False
        for ignore in ignored_combos:
            grab_failed_this_attempt = False
            root.grab_key(
                keycode, base_mods | ignore, True, X.GrabModeAsync, X.GrabModeAsync,
                onerror=_record_failure,
            )
            disp.sync()
            if grab_failed_this_attempt:
                logger.warning("Hotkey combo unavailable for one modifier-lock variant")
            else:
                grabbed_any = True

        disp.flush()

        if not grabbed_any:
            self.grab_failed.emit()
            disp.close()
            return

        self.grab_succeeded.emit()

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
