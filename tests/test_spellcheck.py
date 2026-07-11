from __future__ import annotations

import pytest

from take_note import spellcheck


def test_word_at_finds_word_containing_the_offset():
    text = "hello wrold today"
    assert spellcheck._word_at(text, offset=8) == (6, 11, "wrold")


def test_word_at_handles_apostrophes():
    text = "don't stop"
    assert spellcheck._word_at(text, offset=2) == (0, 5, "don't")


def test_word_at_returns_none_outside_any_word():
    text = "hello wrold today"
    assert spellcheck._word_at(text, offset=5) is None  # the space
    assert spellcheck._word_at(text, offset=99) is None


def test_degrades_gracefully_when_enchant_unavailable(monkeypatch):
    """Deterministic regardless of whether pyenchant happens to be
    installed in the environment running this test — simulates the
    "optional dependency not present" path directly rather than needing
    to actually uninstall anything."""
    monkeypatch.setattr(spellcheck, "enchant", None)
    monkeypatch.setattr(spellcheck, "_dict", None)
    monkeypatch.setattr(spellcheck, "_dict_checked", False)

    assert spellcheck.is_available() is False
    assert spellcheck.check("thisisdefinitelymisspelled") is True  # fails open
    assert spellcheck.suggest("helllo") == []


def test_check_and_suggest_handle_empty_string(monkeypatch):
    monkeypatch.setattr(spellcheck, "enchant", None)
    monkeypatch.setattr(spellcheck, "_dict", None)
    monkeypatch.setattr(spellcheck, "_dict_checked", False)

    assert spellcheck.check("") is True
    assert spellcheck.suggest("") == []


@pytest.fixture(autouse=True)
def _reset_dict_cache():
    """The module-level dict cache must not leak between tests — several
    tests monkeypatch spellcheck.enchant/_dict directly rather than
    through the fixture, but this still guards any test that doesn't."""
    yield
    spellcheck._dict = None
    spellcheck._dict_checked = False


def test_real_dictionary_checks_known_words():
    # Scoped to this test (not module-level) so it's the only one skipped
    # when the optional dependency isn't installed — the tests above must
    # still run regardless, since they test the degrade-gracefully path.
    pytest.importorskip("enchant")
    assert spellcheck.is_available() is True
    assert spellcheck.check("hello") is True
    assert spellcheck.check("helllo") is False


def test_real_dictionary_suggests_corrections():
    pytest.importorskip("enchant")
    assert "hello" in spellcheck.suggest("helllo")
