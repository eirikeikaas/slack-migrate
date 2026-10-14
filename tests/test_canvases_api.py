import pytest
from unittest.mock import MagicMock


def test_fetch_canvases_paginates_filters_and_caches(isolated):
    api = isolated
    api.app.client.files_list.side_effect = [
        {"files": [{"id": "F1", "filetype": "quip"},
                   {"id": "FX", "filetype": "pdf"}], "paging": {"pages": 2}},
        {"files": [{"id": "F2", "filetype": "quip"}], "paging": {"pages": 2}},
    ]
    api.fetch_channels = MagicMock(return_value=[{"id": "C1"}])
    api.app.client.conversations_info.return_value = {
        "ok": True, "channel": {"properties": {"canvas": {"file_id": "F2"}}}}

    result = api.fetch_canvases()

    assert [c["id"] for c in result] == ["F1", "F2"]
    assert result[0]["channel_id"] is None
    assert result[1]["channel_id"] == "C1"
    assert api.fetch_canvases() == result
    assert api.app.client.files_list.call_count == 2


def test_create_canvas_standalone_and_channel(isolated):
    api = isolated
    api.admin_client.canvases_create.return_value = {"ok": True, "canvas_id": "N1"}
    api.admin_client.conversations_canvases_create.return_value = {
        "ok": True, "canvas_id": "N2"}

    assert api.create_canvas("T", "# hi") == "N1"
    assert api.create_canvas("T", "# hi", channel_id="C1") == "N2"
    api.admin_client.canvases_create.assert_called_once_with(
        title="T", document_content={"type": "markdown", "markdown": "# hi"})


def test_create_canvas_error(isolated):
    api = isolated
    api.admin_client.canvases_create.return_value = {"ok": False, "error": "nope"}
    with pytest.raises(Exception, match="nope"):
        api.create_canvas("T", "x")
