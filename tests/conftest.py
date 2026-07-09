from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


_exitstatus = 0


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session, exitstatus):
    global _exitstatus
    _exitstatus = exitstatus


def pytest_unconfigure(config):
    """os._exit() skips Python's own interpreter teardown (garbage
    collection, module/type finalization) entirely, rather than risking
    it. Needed because that teardown intermittently segfaults on this
    Python 3.14 + PySide6 6.11 combination (confirmed via coredumpctl:
    SIGSEGV in python3.14, always *after* pytest's own "N passed" summary
    had already printed, never during actual test execution) — a known
    class of issue where very new CPython releases changed something in
    object/type cleanup that Shiboken's C++ bindings haven't fully caught
    up with yet.

    Deliberately in pytest_unconfigure, not pytest_sessionfinish: the
    terminal reporter's own pytest_sessionfinish is what prints the final
    "N passed" summary line, but confirmed empirically that pytest's
    output capturing isn't released back to the real terminal until
    *after* the whole pytest_sessionfinish hook chain returns — a
    trylast=True sessionfinish hook (tried first) still silently ate that
    summary line, even after also flushing stdout/stderr, because it was
    firing before that release happened. pytest_unconfigure runs later,
    right before the process would exit normally, once collected."""
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(_exitstatus)
