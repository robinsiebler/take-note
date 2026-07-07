from take_note import autostart


def test_enable_creates_desktop_file(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    assert not autostart.is_enabled()
    autostart.enable()

    desktop_file = tmp_path / "autostart" / "take-note.desktop"
    assert desktop_file.exists()
    assert autostart.is_enabled()

    content = desktop_file.read_text()
    assert "Type=Application" in content
    assert "Name=Take Note!" in content
    assert "Exec=" in content


def test_disable_removes_desktop_file(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    autostart.enable()
    assert autostart.is_enabled()

    autostart.disable()
    assert not autostart.is_enabled()


def test_disable_when_not_enabled_does_not_raise(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    assert not autostart.is_enabled()
    autostart.disable()  # should be a no-op, not raise
