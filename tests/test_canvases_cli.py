import json
import os
from unittest.mock import patch
from click.testing import CliRunner
from slack_migrate.cli import cli

CANVASES = [{"id": "F1", "title": "Plan", "channel_id": None, "created": 1}]


def test_fetch_csv_creates_data_dir():
    with patch("slack_migrate.methods.canvases.fetch_canvases", return_value=CANVASES):
        result = CliRunner().invoke(cli, ["canvases", "fetch", "--csv"])
    assert result.exit_code == 0
    assert "F1,Plan" in open("data/canvases.csv").read()
    assert "total 1" in result.output


def test_download_writes_files_and_manifest():
    with patch("slack_migrate.methods.canvases.fetch_canvases", return_value=CANVASES), \
            patch("slack_migrate.methods.canvases.download_canvas_content",
                  return_value="<h1>Plan</h1>"):
        result = CliRunner().invoke(cli, ["canvases", "download"])
    assert result.exit_code == 0
    assert os.path.exists("data/canvases/F1.html")
    assert json.load(open("data/canvases/manifest.json"))["F1"]["title"] == "Plan"


def _seed():
    os.makedirs("data/canvases")
    open("data/canvases/F1.html", "w").write("<h1>Plan</h1>")
    json.dump({"F1": {"title": "Plan"}}, open("data/canvases/manifest.json", "w"))


def test_recreate_dry_run_does_not_call_api():
    _seed()
    with patch("slack_migrate.methods.canvases.create_canvas") as create:
        result = CliRunner().invoke(cli, ["canvases", "recreate", "--dry-run", "F1"])
    assert result.exit_code == 0 and "Would create 'Plan'" in result.output
    create.assert_not_called()


def test_recreate_reports_failures():
    _seed()
    with patch("slack_migrate.methods.canvases.create_canvas", return_value="N1") as create:
        result = CliRunner().invoke(cli, ["canvases", "recreate", "F1", "MISSING"])
    assert "F1 -> N1" in result.output
    assert "1 failed" in result.output and "MISSING" in result.output
    assert create.call_args.args[1].startswith("# Plan")
