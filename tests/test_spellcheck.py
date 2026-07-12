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
    spellcheck.ignore("whatever")  # must not raise
    spellcheck.add_to_dictionary("whatever")  # must not raise


class _FakeDict:
    """A tiny in-memory stand-in for enchant.Dict — real Dict.add()
    persists to the user's actual personal word list on disk, which a
    test must never touch (same "verify in isolation, never against the
    real environment" lesson as pip install docs). This is enough to
    prove ignore()/add_to_dictionary() are wired to the right Dict
    methods without ever calling into real Enchant."""

    def __init__(self):
        self.session_words: set[str] = set()
        self.added_words: set[str] = set()

    def check(self, word):
        return word in self.session_words or word in self.added_words

    def suggest(self, word):
        return []

    def add_to_session(self, word):
        self.session_words.add(word)

    def add(self, word):
        self.added_words.add(word)


def test_ignore_makes_check_pass_for_that_word(monkeypatch):
    fake = _FakeDict()
    monkeypatch.setattr(spellcheck, "_dict", fake)
    monkeypatch.setattr(spellcheck, "_dict_checked", True)

    assert spellcheck.check("wrold") is False
    spellcheck.ignore("wrold")
    assert spellcheck.check("wrold") is True
    assert fake.session_words == {"wrold"}


def test_add_to_dictionary_makes_check_pass_for_that_word(monkeypatch):
    fake = _FakeDict()
    monkeypatch.setattr(spellcheck, "_dict", fake)
    monkeypatch.setattr(spellcheck, "_dict_checked", True)

    assert spellcheck.check("wrold") is False
    spellcheck.add_to_dictionary("wrold")
    assert spellcheck.check("wrold") is True
    assert fake.added_words == {"wrold"}


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
