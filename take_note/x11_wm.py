from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# KWin tracks both the standard EWMH "above" state and its own legacy
# _NET_WM_STATE_STAYS_ON_TOP extension atom, set together whenever Qt
# applies WindowStaysOnTopHint. Confirmed via repeated xprop testing that
# touching only _NET_WM_STATE_ABOVE leaves the window still pinned — KWin
# keeps treating it as "stays on top" as long as this second atom remains.
_ABOVE_ATOM_NAMES = ("_NET_WM_STATE_ABOVE", "_NET_WM_STATE_STAYS_ON_TOP")

# Hides the window from the taskbar/pager/task-switcher independent of
# window TYPE. Notes used to rely on Qt.Tool (window type Utility) for this,
# but confirmed via _NET_CLIENT_LIST_STACKING that KWin keeps Utility-type
# windows in an elevated stacking layer above Normal windows regardless of
# state hints — which broke a genuinely optional Always-on-Top toggle.
# Switching to Qt.Window (Normal type) fixes the layering, so hiding from
# these three surfaces has to be done explicitly via state hints instead.
# _NET_WM_STATE_SKIP_TASKBAR/SKIP_PAGER only cover the taskbar and pager
# widgets — KWin's Alt-Tab switcher is a separate surface with its own
# KDE-specific opt-out atom, confirmed present in _NET_SUPPORTED.
_SKIP_TASKBAR_ATOM_NAMES = (
    "_NET_WM_STATE_SKIP_TASKBAR",
    "_NET_WM_STATE_SKIP_PAGER",
    "_KDE_NET_WM_STATE_SKIP_SWITCHER",
)


def _send_state_client_message(window_id: int, enabled: bool, atom_names: tuple[str, ...]) -> None:
    """Sends one EWMH _NET_WM_STATE client message per atom to the
    already-mapped window, rather than using Qt's setWindowFlags() (which
    destroys and recreates the native window under the hood).

    Confirmed via repeated xprop testing: the *first* setWindowFlags()
    application of a state-related hint (at construction time) works, but
    toggling it off and then back on again through further setWindowFlags()
    calls silently fails to restore it — the property comes back empty even
    after a full second of settling time, so it isn't a timing race, just
    an unreliable path for a live re-toggle. Sending the state change as a
    message per the EWMH spec (what window managers actually expect for
    changing an already-mapped window's state) is reliable.
    """
    try:
        from Xlib import X, display
        from Xlib.protocol import event
    except ImportError:
        logger.warning("python-xlib not available; cannot change window state")
        return

    try:
        disp = display.Display()
    except Exception:
        logger.warning("Could not open X display; cannot change window state")
        return

    try:
        root = disp.screen().root
        win = disp.create_resource_object("window", window_id)
        net_wm_state = disp.intern_atom("_NET_WM_STATE")

        for atom_name in atom_names:
            atom = disp.intern_atom(atom_name)
            client_event = event.ClientMessage(
                window=win,
                client_type=net_wm_state,
                data=(32, [1 if enabled else 0, atom, 0, 1, 0]),
            )
            mask = X.SubstructureRedirectMask | X.SubstructureNotifyMask
            root.send_event(client_event, event_mask=mask)
        disp.flush()
    finally:
        disp.close()


def set_stays_on_top(window_id: int, enabled: bool) -> None:
    _send_state_client_message(window_id, enabled, _ABOVE_ATOM_NAMES)


def set_skip_taskbar(window_id: int, enabled: bool) -> None:
    _send_state_client_message(window_id, enabled, _SKIP_TASKBAR_ATOM_NAMES)
