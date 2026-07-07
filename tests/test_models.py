from take_note.models import FONT_SWATCHES, TRANSPARENCY_LEVELS


def test_font_swatches_include_black():
    assert "#000000" in FONT_SWATCHES


def test_transparency_levels_include_none_at_full_opacity():
    levels = dict(TRANSPARENCY_LEVELS)
    assert levels["None"] == 1.0
    assert all(0.0 <= value <= 1.0 for value in levels.values())
