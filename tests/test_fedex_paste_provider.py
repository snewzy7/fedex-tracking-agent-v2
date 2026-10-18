from datetime import date
from pathlib import Path

import pytest

from shipment_tracker.models import FailureReason, Flag, TrackingStatus
from shipment_tracker.rules import classify
from shipment_tracker.tracking.fedex_paste_provider import FedExPasteProvider, parse_fedex_summary

# Synthetic copy of FedEx's page, laid out exactly like a real Cmd+A / Cmd+C paste.
SAMPLE = (Path(__file__).parent / "fixtures" / "fedex_summary_sample.txt").read_text()
HEADER = "Tracking ID\tShip date\tShipper city, state\tRecipient city, state\tStatus\tDelivered date\tScheduled delivery date\tService"
TODAY = date(2026, 10, 18)


def page(*rows: str) -> str:
    """Wrap row text in a minimal results page (header + footer)."""
    return "\n".join(["Summary Tracking Results", HEADER, *rows, "Our Company", "Site Map"])


def test_reads_every_row_and_ignores_the_page_around_it():
    results = parse_fedex_summary(SAMPLE)
    assert list(results) == ["100000000101", "100000000102", "100000000103", "100000000104", "100000000105"]


def test_label_created_with_no_dates_yet():
    result = parse_fedex_summary(SAMPLE)["100000000101"]
    assert result.status is TrackingStatus.LABEL_CREATED
    assert result.eta is None
    assert result.detail is None


def test_on_the_way_keeps_fedex_detail_and_scheduled_date():
    result = parse_fedex_summary(SAMPLE)["100000000102"]
    assert result.status is TrackingStatus.IN_TRANSIT
    assert result.eta == date(2026, 10, 19)
    assert result.detail == "Arrived at FedEx location"


def test_multi_piece_master_number_is_read_without_the_label():
    result = parse_fedex_summary(SAMPLE)["100000000105"]
    assert result.status is TrackingStatus.IN_TRANSIT
    assert result.eta == date(2026, 10, 19)


def test_past_scheduled_date_is_flagged_delayed_by_our_rules():
    result = parse_fedex_summary(SAMPLE)["100000000104"]  # scheduled 10/16, still on the way
    assert classify(result, TODAY) is Flag.DELAYED


def test_delivered_row_uses_the_delivered_date():
    # Format assumed from the page's column order; not yet seen in a real paste.
    text = page("100000000201\t10/12/26\tNEW YORK, NY\tBOISE, ID\t", "Delivered", "10/15/26\tFedEx Ground")
    result = parse_fedex_summary(text)["100000000201"]
    assert result.status is TrackingStatus.DELIVERED
    assert result.delivered_on == date(2026, 10, 15)


def test_delivered_row_with_both_dates():
    text = page("100000000202\t10/12/26\tNEW YORK, NY\tBOISE, ID\t", "Delivered", "10/15/26\t10/14/26\tFedEx Ground")
    result = parse_fedex_summary(text)["100000000202"]
    assert (result.delivered_on, result.eta) == (date(2026, 10, 15), date(2026, 10, 14))


def test_delivery_exception_keeps_fedex_explanation():
    text = page("100000000203\t10/12/26\tNEW YORK, NY\tBOISE, ID\t", "Delivery exception",
                "Incorrect address", "10/16/26\tFedEx Ground")
    result = parse_fedex_summary(text)["100000000203"]
    assert result.status is TrackingStatus.EXCEPTION
    assert result.detail == "Incorrect address"


def test_status_on_the_same_line_as_the_cities_is_also_read():
    text = page("100000000204\t10/15/26\tNEW YORK, NY\tBOISE, ID\tOn the way", "10/19/26\tFedEx Ground")
    assert parse_fedex_summary(text)["100000000204"].status is TrackingStatus.IN_TRANSIT


def test_unrecognized_fedex_status_is_reported_not_guessed():
    text = page("100000000205\t10/15/26\tNEW YORK, NY\tBOISE, ID\t", "Returning to sender", "10/19/26\tFedEx Ground")
    result = parse_fedex_summary(text)["100000000205"]
    assert result.failure is FailureReason.PROVIDER_ERROR
    assert "Returning to sender" in result.failure_message


def test_strange_date_text_is_reported_not_guessed():
    text = page("100000000206\t10/15/26\tNEW YORK, NY\tBOISE, ID\t", "On the way", "next Tuesday\tFedEx Ground")
    result = parse_fedex_summary(text)["100000000206"]
    assert result.failure is FailureReason.PROVIDER_ERROR
    assert "next Tuesday" in result.failure_message


def test_row_cut_off_before_its_last_line_is_reported():
    text = "\n".join(["Summary Tracking Results", HEADER, "100000000207\t10/15/26\tNEW YORK, NY\tBOISE, ID\t", "On the way"])
    result = parse_fedex_summary(text)["100000000207"]
    assert "ends before" in result.failure_message


def test_windows_line_endings_work():
    assert len(parse_fedex_summary(SAMPLE.replace("\n", "\r\n"))) == 5


def test_text_that_isnt_the_fedex_page_is_rejected_clearly():
    with pytest.raises(ValueError, match="Summary Tracking Results"):
        parse_fedex_summary("Dear team, here are the numbers...")


def test_number_not_in_any_paste_says_so():
    provider = FedExPasteProvider([SAMPLE])
    result = provider.fetch("999999999999")
    assert result.failure is FailureReason.NOT_FOUND
    assert "Include it in a batch" in result.failure_message


def test_several_pastes_combine_and_a_later_paste_wins():
    later = page("100000000101\t10/17/26\tNEW YORK, NY\tOMAHA, NE\t", "On the way", "10/21/26\tFedEx Ground")
    provider = FedExPasteProvider([SAMPLE, later])
    assert provider.fetch("100000000101").status is TrackingStatus.IN_TRANSIT
    assert provider.fetch("100000000102").status is TrackingStatus.IN_TRANSIT
    assert len(provider.tracking_numbers) == 5
