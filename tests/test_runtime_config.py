import json

import pytest

from server import runtime_config


@pytest.fixture(autouse=True)
def reset_loader(monkeypatch):
    monkeypatch.setattr(runtime_config, "_loaded_secret_id", None)
    for key in ("ATLAS_RUNTIME_SECRET_ID", "GROQ_API_KEY", "GROQ_MODEL", "ATLAS_ACCESS_TOKEN"):
        monkeypatch.delenv(key, raising=False)


def test_local_mode_does_not_call_aws(monkeypatch):
    monkeypatch.setattr(runtime_config, "_boto3", lambda: pytest.fail("AWS must not be called"))
    assert runtime_config.load_runtime_secrets() is False


def test_runtime_json_loads_through_iam_without_overwriting_explicit_env(monkeypatch):
    calls = []

    class Secrets:
        def get_secret_value(self, **kwargs):
            calls.append(kwargs)
            return {"SecretString": json.dumps({
                "GROQ_API_KEY": "from-secret-manager",
                "GROQ_MODEL": "secret-model",
                "ATLAS_ACCESS_TOKEN": "a" * 32,
                "UNAPPROVED_VALUE": "ignored",
            })}

    class AWS:
        def client(self, service, **kwargs):
            assert service == "secretsmanager"
            return Secrets()

    monkeypatch.setenv("ATLAS_RUNTIME_SECRET_ID", "/atlas/production/runtime")
    monkeypatch.setenv("GROQ_MODEL", "explicit-local-model")
    monkeypatch.setattr(runtime_config, "_boto3", lambda: AWS())
    assert runtime_config.load_runtime_secrets() is True
    assert calls == [{"SecretId": "/atlas/production/runtime"}]
    assert runtime_config.os.environ["GROQ_API_KEY"] == "from-secret-manager"
    assert runtime_config.os.environ["GROQ_MODEL"] == "explicit-local-model"
    assert "UNAPPROVED_VALUE" not in runtime_config.os.environ
    assert runtime_config.load_runtime_secrets() is True
    assert len(calls) == 1


def test_runtime_secret_requires_groq_key(monkeypatch):
    class Secrets:
        def get_secret_value(self, **_kwargs):
            return {"SecretString": '{"ATLAS_ACCESS_TOKEN":"long-enough-but-no-groq-key"}'}

    class AWS:
        def client(self, *_args, **_kwargs):
            return Secrets()

    monkeypatch.setenv("ATLAS_RUNTIME_SECRET_ID", "runtime")
    monkeypatch.setattr(runtime_config, "_boto3", lambda: AWS())
    with pytest.raises(RuntimeError, match="missing GROQ_API_KEY"):
        runtime_config.load_runtime_secrets()
