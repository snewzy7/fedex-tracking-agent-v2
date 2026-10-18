import json
from datetime import date

import anthropic
import httpx2
import pytest
from fake_claude import FakeClaude, answer_for

from shipment_tracker.models import Flag
from shipment_tracker.pipeline import ShipmentOutcome
from shipment_tracker.summarizer import (
    SUMMARY_SCHEMA,
    IssueSummary,
    ShipmentIssue,
    SummaryError,
    format_summary,
    summarize_problems,
)

TODAY = date(2026, 10, 18)


def outcome(tracking, flag, text, name="Riley Demo"):
    return ShipmentOutcome(
        tab="Form Responses 1", row_number=4, tracking=tracking, name=name,
        city="Austin", state="TX", flag=flag, status_text=text,
    )


PROBLEMS = [
    outcome("100000000006", Flag.DELAYED, "Delayed: ETA was 10/15 (in transit)"),
    outcome("100000000007", Flag.EXCEPTION, "Exception: Incorrect address"),
]
TRACKINGS = [p.tracking for p in PROBLEMS]


def test_no_problems_means_no_api_call():
    client = FakeClaude()
    assert summarize_problems([], TODAY, client) is None
    assert client.requests == []


def test_good_answer_is_returned_as_a_checked_summary():
    client = FakeClaude(answer_for(TRACKINGS))
    summary = summarize_problems(PROBLEMS, TODAY, client)
    assert isinstance(summary, IssueSummary)
    assert [i.tracking for i in summary.issues] == TRACKINGS


def test_request_uses_structured_output_and_the_configured_model():
    client = FakeClaude(answer_for(TRACKINGS))
    summarize_problems(PROBLEMS, TODAY, client, model="claude-test-model")
    request = client.requests[0]
    assert request["model"] == "claude-test-model"
    assert request["output_config"]["format"] == {"type": "json_schema", "schema": SUMMARY_SCHEMA}
    assert request["fallbacks"] == "default"


def test_claude_sees_only_flagged_facts_and_no_names():
    client = FakeClaude(answer_for(TRACKINGS))
    summarize_problems(PROBLEMS, TODAY, client)
    sent = client.requests[0]["messages"][0]["content"]
    assert "2026-10-18" in sent
    assert "Incorrect address" in sent
    assert "Riley Demo" not in sent


def test_summary_mentioning_an_unknown_shipment_is_rejected():
    client = FakeClaude(answer_for([*TRACKINGS, "555555555555"]))
    with pytest.raises(SummaryError, match="weren't in the data"):
        summarize_problems(PROBLEMS, TODAY, client)


def test_summary_skipping_a_shipment_is_rejected():
    client = FakeClaude(answer_for(TRACKINGS[:1]))
    with pytest.raises(SummaryError, match="left out"):
        summarize_problems(PROBLEMS, TODAY, client)


def test_summary_listing_a_shipment_twice_is_rejected():
    client = FakeClaude(answer_for([*TRACKINGS, TRACKINGS[0]]))
    with pytest.raises(SummaryError, match="more than once"):
        summarize_problems(PROBLEMS, TODAY, client)


@pytest.mark.parametrize(
    "bad_answer",
    [
        "not json at all",
        {"overview": "x"},  # missing issues
        {"overview": "x", "issues": [{"tracking": "100000000006"}]},  # missing fields
        {**answer_for(TRACKINGS), "status": "Delivered"},  # extra field
        answer_for(TRACKINGS, priority="urgent"),  # not an allowed priority
    ],
)
def test_malformed_answers_are_rejected(bad_answer):
    with pytest.raises(SummaryError, match="expected format"):
        summarize_problems(PROBLEMS, TODAY, FakeClaude(bad_answer))


def test_refusal_and_cut_off_answers_are_rejected():
    with pytest.raises(SummaryError, match="declined"):
        summarize_problems(PROBLEMS, TODAY, FakeClaude(answer_for(TRACKINGS), stop_reason="refusal"))
    with pytest.raises(SummaryError, match="cut off"):
        summarize_problems(PROBLEMS, TODAY, FakeClaude("{", stop_reason="max_tokens"))


REQUEST = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


@pytest.mark.parametrize(
    "error, message",
    [
        (anthropic.AuthenticationError("bad", response=httpx2.Response(401, request=REQUEST), body=None), "API key"),
        (anthropic.RateLimitError("slow", response=httpx2.Response(429, request=REQUEST), body=None), "rate limit"),
        (anthropic.InternalServerError("oops", response=httpx2.Response(500, request=REQUEST), body=None), "500"),
        (anthropic.APIConnectionError(request=REQUEST), "network"),
    ],
)
def test_api_errors_become_friendly_summary_errors(error, message):
    with pytest.raises(SummaryError, match=message):
        summarize_problems(PROBLEMS, TODAY, FakeClaude(raises=error))


def test_printed_summary_uses_our_status_not_claudes_words():
    answer = answer_for(TRACKINGS)
    answer["issues"][0]["issue"] = "It was delivered yesterday."  # Claude being wrong
    summary = IssueSummary.model_validate(answer)
    text = format_summary(summary, PROBLEMS)
    assert "Status: Delayed: ETA was 10/15 (in transit)" in text
    assert "Status: Exception: Incorrect address" in text


def test_printed_summary_lists_high_priority_first():
    answer = answer_for(TRACKINGS)
    answer["issues"][1]["priority"] = "high"
    text = format_summary(IssueSummary.model_validate(answer), PROBLEMS)
    assert text.index("100000000007") < text.index("100000000006")


def test_hand_written_schema_matches_the_pydantic_models():
    item = SUMMARY_SCHEMA["properties"]["issues"]["items"]
    assert set(SUMMARY_SCHEMA["required"]) == set(IssueSummary.model_fields)
    assert set(item["required"]) == set(ShipmentIssue.model_fields) == set(item["properties"])
    assert json.dumps(SUMMARY_SCHEMA)  # serializable
