# tests/test_config.py
from code_reviewer.config import load_config, ensure_utf8_stdout


def test_load_config_reads_env(monkeypatch):
    monkeypatch.setenv("ZHIPU_API_KEY", "k")
    cfg = load_config(env_file="/does/not/exist")
    assert cfg.zhipu_api_key == "k"
    assert cfg.model == "glm-4"


def test_load_config_deepseek(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "ds")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "ds")
    cfg = load_config(env_file="/does/not/exist")
    assert cfg.deepseek_api_key == "ds"
