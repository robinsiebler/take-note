import pytest

from take_note.hotkey import parse_shortcut


def test_parse_shortcut_ctrl_alt():
    key, modifiers = parse_shortcut("Ctrl+Alt+N")
    assert key == "N"
    assert modifiers == ("control", "mod1")


def test_parse_shortcut_meta_alt():
    key, modifiers = parse_shortcut("Meta+Alt+N")
    assert key == "N"
    assert modifiers == ("meta", "mod1")


def test_parse_shortcut_no_modifiers():
    key, modifiers = parse_shortcut("N")
    assert key == "N"
    assert modifiers == ()


def test_parse_shortcut_multiple_modifiers_preserves_order():
    key, modifiers = parse_shortcut("Ctrl+Shift+Alt+F1")
    assert key == "F1"
    assert modifiers == ("control", "shift", "mod1")


def test_parse_shortcut_unknown_modifier_silently_dropped():
    key, modifiers = parse_shortcut("Fn+N")
    assert key == "N"
    assert modifiers == ()


def test_parse_shortcut_empty_raises():
    with pytest.raises(ValueError):
        parse_shortcut("")
