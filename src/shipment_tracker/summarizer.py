"""The only AI in the project: Claude explains problem shipments and suggests next steps.

Claude is downstream of everything else. By the time it runs, the statuses
are already decided by plain code and written to the sheet. Claude gets a
read-only list of the flagged rows and returns advice. It can't change a
status, and its answer is checked before we use it:

1. The answer must match a fixed JSON shape (enforced by the API's
   structured outputs, then re-checked with Pydantic).
2. Every tracking number in the answer must be one we sent, and every one
   we sent must be covered. Otherwise the whole summary is discarded.
3. When we display the summary, the status shown next to each package comes
   from OUR data, never from Claude's text.

If anything goes wrong (no key, network trouble, a bad answer), the run
still succeeds: the sheet is already updated, and the summary is skipped
with a warning.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Literal

import anthropic
from pydantic import BaseModel, ConfigDict, ValidationError

from shipment_tracker.pipeline import ShipmentOutcome

DEFAULT_MODEL = "claude-opus-5-5"
MAX_TOKENS = 16000

SYSTEM_PROMPT = """\
You help a marketing coordinator follow up on FedEx shipments of sales kits \
sent to a nationwide sales team. You'll receive a JSON list of shipments that \
an automated check flagged as delayed, exceptions, or failed lookups.

For each shipment, explain the issue in one or two plain sentences and \
recommend one concrete next step the coordinator can take today (for example: \
contact FedEx about the exception, confirm the address with the recipient, \
re-enter a tracking number that the spreadsheet mangled, or wait and re-check \
if the delay is minor). Set priority to high when the package is likely to \
fail without action, medium when it needs a follow-up soon, and low when \
waiting is reasonable.

Base everything only on the facts provided. The status text is the carrier's \
data and is authoritative: don't guess at causes or delivery dates it doesn't \
state. Include exactly one entry per shipment, using its tracking value \
exactly as given. Finish with a short overview of the overall situation."""

# The JSON shape Claude must return. Written out by hand so it's easy to
# read; a test checks it stays in sync with the Pydantic models below.
SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "overview": {"type": "string"},
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "tracking": {"type": "string"},
                    "issue": {"type": "string"},
                    "recommended_action": {"type": "string"},
                    "priority": {"type": "string", "enum": ["high", "medium", "low"]},
                },
                "required": ["tracking", "issue", "recommended_action", "priority"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["overview", "issues"],
    "additionalProperties": False,
}


class ShipmentIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tracking: str
    issue: str
    recommended_action: str
    priority: Literal["high", "medium", "low"]


class IssueSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overview: str
    issues: list[ShipmentIssue]


class SummaryError(RuntimeError):
    """The summary couldn't be produced or failed our checks. The message says why."""


def summarize_problems(
    problems: list[ShipmentOutcome],
    today: date,
    client: anthropic.Anthropic,
    model: str = DEFAULT_MODEL,
) -> IssueSummary | None:
    """Ask Claude to summarize the problem shipments. Returns None if there are none.

    `client` is passed in so tests can hand over a fake one: no API key,
    no network, no cost.
    """
    if not problems:
        return None  # nothing to summarize, so don't spend an API call

    facts = build_facts(problems)
    response = _call_claude(client, model, today, facts)
    summary = _parse(response)
    check_against_facts(summary, facts)
    return summary


def build_facts(problems: list[ShipmentOutcome]) -> list[dict]:
    """The only data Claude sees. No names or street addresses: it doesn't need them."""
    return [
        {
            "tracking": p.tracking,
            "flag": p.flag.value,
            "status_text": p.status_text,
            "tab": p.tab,
            "row": p.row_number,
            "city": p.city,
            "state": p.state,
        }
        for p in problems
    ]


def check_against_facts(summary: IssueSummary, facts: list[dict]) -> None:
    """Reject the summary if it mentions shipments we didn't send, or skips any we did."""
    sent = [f["tracking"] for f in facts]
    returned = [issue.tracking for issue in summary.issues]

    invented = set(returned) - set(sent)
    if invented:
        raise SummaryError(f"Summary mentions tracking values that weren't in the data: {sorted(invented)}")
    missing = set(sent) - set(returned)
    if missing:
        raise SummaryError(f"Summary left out these shipments: {sorted(missing)}")
    if len(returned) != len(set(returned)):
        raise SummaryError("Summary lists the same shipment more than once.")


def _call_claude(client: anthropic.Anthropic, model: str, today: date, facts: list[dict]):
    user_message = f"Today is {today.isoformat()}.\n\nFlagged shipments:\n{json.dumps(facts, indent=2)}"
    try:
        return client.beta.messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
            output_config={
                "effort": "medium",
                "format": {"type": "json_schema", "schema": SUMMARY_SCHEMA},
            },
            # If a safety check declines the request, let the API retry it on
            # a fallback model it chooses instead of failing outright.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    # Most specific first. The SDK has already retried temporary failures twice.
    except anthropic.AuthenticationError as error:
        raise SummaryError("The Anthropic API key was rejected. Check ANTHROPIC_API_KEY in .env.") from error
    except anthropic.RateLimitError as error:
        raise SummaryError("Anthropic rate limit reached. Try again in a few minutes.") from error
    except anthropic.APIStatusError as error:
        raise SummaryError(f"Anthropic API error {error.status_code}: {error.message}") from error
    except anthropic.APIConnectionError as error:
        raise SummaryError("Couldn't reach the Anthropic API (network problem).") from error


def _parse(response) -> IssueSummary:
    if response.stop_reason == "refusal":
        raise SummaryError("Claude declined to summarize this data.")
    if response.stop_reason == "max_tokens":
        raise SummaryError("Claude's answer was cut off before it finished.")

    text = "".join(block.text for block in response.content if block.type == "text")
    try:
        return IssueSummary.model_validate_json(text)
    except ValidationError as error:
        raise SummaryError(f"Claude's answer didn't match the expected format: {error}") from error


def format_summary(summary: IssueSummary, problems: list[ShipmentOutcome]) -> str:
    """Printable summary. Status and location come from our data; Claude adds advice."""
    ours = {p.tracking: p for p in problems}
    order = {"high": 0, "medium": 1, "low": 2}
    lines = ["AI summary (advice only; statuses come from the tracking data):", "", summary.overview, ""]
    for issue in sorted(summary.issues, key=lambda i: order[i.priority]):
        p = ours[issue.tracking]
        lines.append(f"[{issue.priority.upper()}] {p.tab} row {p.row_number} ({p.city}, {p.state}), {p.tracking}")
        lines.append(f"  Status: {p.status_text}")
        lines.append(f"  Issue: {issue.issue}")
        lines.append(f"  Next step: {issue.recommended_action}")
    return "\n".join(lines)
