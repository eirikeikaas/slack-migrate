import os

os.environ.setdefault("SLACK_BOT_TOKEN", "xoxb-test")
os.environ.setdefault("SLACK_SIGNING_SECRET", "secret")
os.environ.setdefault("SLACK_USER_TOKEN", "xoxp-test")

import pytest
from unittest.mock import MagicMock

# slack_bolt.App calls auth.test on construction; stub it before api is imported.
import slack_bolt
slack_bolt.App = MagicMock()


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "cache").mkdir()
    from slack_migrate import api
    monkeypatch.setattr(api, "app", MagicMock())
    monkeypatch.setattr(api, "admin_client", MagicMock())
    monkeypatch.setattr(api, "CACHE_DIR", tmp_path / "cache")
    return api
