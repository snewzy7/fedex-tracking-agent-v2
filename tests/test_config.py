import pytest

from shipment_tracker.cli import build_provider, build_sheet
from shipment_tracker.config import ConfigError, load_settings


def test_defaults_match_the_real_sheet_tabs():
    settings = load_settings({})
    assert settings.tabs == ("Form Responses 1", "Manual Entry")
    assert settings.tracking_provider == "mock"
    assert settings.sheet_backend == "mock"


def test_tabs_can_be_overridden_and_spaces_are_trimmed():
    settings = load_settings({"SHEET_TABS": " Tab A , Tab B ,"})
    assert settings.tabs == ("Tab A", "Tab B")


def test_empty_tab_list_is_rejected():
    with pytest.raises(ConfigError, match="SHEET_TABS"):
        load_settings({"SHEET_TABS": " , "})


def test_providers_that_dont_exist_yet_give_a_clear_error():
    with pytest.raises(ConfigError, match="isn't available yet"):
        build_provider(load_settings({"TRACKING_PROVIDER": "fedex"}))
    with pytest.raises(ConfigError, match="isn't available yet"):
        build_sheet(load_settings({"SHEET_BACKEND": "google"}))
