import json

from shipment_tracker.sheets.base import CellUpdate
from shipment_tracker.sheets.json_file_sheet import JsonFileSheet


def write_template(tmp_path):
    template = tmp_path / "template.json"
    template.write_text(json.dumps({"tabs": {"T": [["Tracking"], ["111111111111"]]}}))
    return template


def test_working_copy_is_created_from_the_template(tmp_path):
    template = write_template(tmp_path)
    working = tmp_path / "work" / "sheet.json"
    sheet = JsonFileSheet(working, template)
    assert working.exists()
    assert sheet.read_tab("T")[1] == ["111111111111"]


def test_writes_and_colors_survive_reopening_and_template_is_untouched(tmp_path):
    template = write_template(tmp_path)
    working = tmp_path / "sheet.json"
    JsonFileSheet(working, template).write_cells("T", [CellUpdate(2, 2, "Delivered 10/14", "#b7e1cd")])

    reopened = JsonFileSheet(working, template)
    assert reopened.read_tab("T")[1] == ["111111111111", "Delivered 10/14"]
    assert reopened.color_of("T", 2, 2) == "#b7e1cd"
    assert "Delivered" not in template.read_text()
