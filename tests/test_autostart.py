from take_note import autostart


def test_enable_prefers_which_over_sys_executable(tmp_path, monkeypatch):
    """A `pip install --user` puts the console script in ~/.local/bin,
    not next to sys.executable's system Python (see PR: autostart wrote
    /usr/bin/take-note, which doesn't exist, breaking launch-at-login)."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr(autostart.sys, "executable", "/usr/bin/python3")
    monkeypatch.setattr(
        autostart.shutil, "which", lambda name: "/home/user/.local/bin/take-note"
    )

    autostart.enable()

    content = (tmp_path / "autostart" / "take-note.desktop").read_text()
    assert "Exec=/home/user/.local/bin/take-note\n" in content


def test_enable_falls_back_to_sys_executable_when_not_on_path(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr(autostart.sys, "executable", "/home/user/.venv/bin/python")
    monkeypatch.setattr(autostart.shutil, "which", lambda name: None)

    autostart.enable()

    content = (tmp_path / "autostart" / "take-note.desktop").read_text()
    assert "Exec=/home/user/.venv/bin/take-note\n" in content


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
