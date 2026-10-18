"""A stand-in for the Anthropic client, so tests need no API key, network, or money.

It mimics only the bit we use, `client.beta.messages.create(...)`, and
remembers what it was asked so tests can check the request too.
"""

import json
from types import SimpleNamespace


class FakeClaude:
    def __init__(self, answer=None, stop_reason="end_turn", raises=None):
        self.answer = answer  # dict (sent as JSON) or str (sent as-is)
        self.stop_reason = stop_reason
        self.raises = raises
        self.requests = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.requests.append(kwargs)
        if self.raises:
            raise self.raises
        text = self.answer if isinstance(self.answer, str) else json.dumps(self.answer)
        return SimpleNamespace(
            stop_reason=self.stop_reason,
            content=[SimpleNamespace(type="text", text=text)],
        )


def answer_for(trackings, priority="medium"):
    """A well-formed answer covering exactly these tracking values."""
    return {
        "overview": "A few shipments need attention.",
        "issues": [
            {"tracking": t, "issue": f"Issue for {t}.", "recommended_action": "Contact FedEx.", "priority": priority}
            for t in trackings
        ],
    }
