from take_note import storage
from take_note.models import Board, Note, Settings


def test_save_and_load_roundtrip(tmp_path):
    path = tmp_path / "notes.json"
    board = Board(id="board-1", name="Work", x=10, y=20, w=400, h=300)
    notes = [
        Note(id="note-1", html="<b>hi</b>", color="#fff59d", x=10, y=20, w=200, h=150),
        Note(id="note-2", html="on board", color="#a5d6a7", x=5, y=5, board_id="board-1"),
    ]
    settings = Settings(default_color="#a5d6a7", launch_at_login=True, hotkey="Ctrl+Alt+M")

    storage.save_all(notes, [board], settings, path=path)
    loaded_notes, loaded_boards, loaded_settings = storage.load_all(path=path)

    assert loaded_notes == notes
    assert loaded_boards == [board]
    assert loaded_settings == settings


def test_load_missing_file_returns_empty(tmp_path):
    notes, boards, settings = storage.load_all(path=tmp_path / "nope.json")
    assert notes == []
    assert boards == []
    assert settings == Settings()


def test_load_corrupt_file_does_not_raise(tmp_path):
    path = tmp_path / "notes.json"
    path.write_text("{not valid json")

    notes, boards, settings = storage.load_all(path=path)

    assert notes == []
    assert boards == []
    assert settings == Settings()
    assert (tmp_path / "notes.json.bak").exists()
