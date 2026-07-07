import logging

import Xlib.display

from take_note import x11_wm


def _raise(*args, **kwargs):
    raise Exception("cannot connect to display")


def test_set_stays_on_top_does_not_raise_when_display_unavailable(monkeypatch, caplog):
    monkeypatch.setattr(Xlib.display, "Display", _raise)
    caplog.set_level(logging.WARNING)

    x11_wm.set_stays_on_top(12345, True)  # must not raise

    assert "Could not open X display" in caplog.text


def test_set_skip_taskbar_does_not_raise_when_display_unavailable(monkeypatch, caplog):
    monkeypatch.setattr(Xlib.display, "Display", _raise)
    caplog.set_level(logging.WARNING)

    x11_wm.set_skip_taskbar(12345, True)  # must not raise

    assert "Could not open X display" in caplog.text
