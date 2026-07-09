from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def pytest_sessionfinish(session, exitstatus):
    """Every test result has already been captured and reported by this
    point — os._exit() skips Python's own interpreter teardown (garbage
    collection, module/type finalization) entirely, rather than risking
    it. Needed because that teardown intermittently segfaults on this
    Python 3.14 + PySide6 6.11 combination (confirmed via coredumpctl:
    SIGSEGV in python3.14, always *after* pytest's own "N passed" summary
    had already printed, never during actual test execution) — a known
    class of issue where very new CPython releases changed something in
    object/type cleanup that Shiboken's C++ bindings haven't fully caught
    up with yet."""
    os._exit(exitstatus)
