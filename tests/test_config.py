from filenotes.config import load_config


def test_defaults_when_no_file(tmp_path, monkeypatch):
    monkeypatch.setenv("FILENOTES_CONFIG", str(tmp_path / "missing.toml"))
    monkeypatch.delenv("FILENOTES_RECENT_COUNT", raising=False)
    assert load_config()["recent_count"] == 5


def test_reads_file(tmp_path, monkeypatch):
    cfg = tmp_path / "config.toml"
    cfg.write_text("recent_count = 8\n")
    monkeypatch.setenv("FILENOTES_CONFIG", str(cfg))
    monkeypatch.delenv("FILENOTES_RECENT_COUNT", raising=False)
    assert load_config()["recent_count"] == 8


def test_env_overrides_file(tmp_path, monkeypatch):
    cfg = tmp_path / "config.toml"
    cfg.write_text("recent_count = 8\n")
    monkeypatch.setenv("FILENOTES_CONFIG", str(cfg))
    monkeypatch.setenv("FILENOTES_RECENT_COUNT", "2")
    assert load_config()["recent_count"] == 2


def test_malformed_config_falls_back(tmp_path, monkeypatch):
    cfg = tmp_path / "config.toml"
    cfg.write_text("recent_count = not_a_number\n")
    monkeypatch.setenv("FILENOTES_CONFIG", str(cfg))
    monkeypatch.delenv("FILENOTES_RECENT_COUNT", raising=False)
    assert load_config()["recent_count"] == 5


def test_embed_images_defaults_off(tmp_path, monkeypatch):
    monkeypatch.setenv("FILENOTES_CONFIG", str(tmp_path / "missing.toml"))
    monkeypatch.delenv("FILENOTES_EMBED_IMAGES", raising=False)
    assert load_config()["embed_images"] is False


def test_embed_images_from_file_and_env(tmp_path, monkeypatch):
    cfg = tmp_path / "config.toml"
    cfg.write_text("embed_images = true\n")
    monkeypatch.setenv("FILENOTES_CONFIG", str(cfg))
    monkeypatch.delenv("FILENOTES_EMBED_IMAGES", raising=False)
    assert load_config()["embed_images"] is True
    # Env wins over the file.
    monkeypatch.setenv("FILENOTES_EMBED_IMAGES", "no")
    assert load_config()["embed_images"] is False
