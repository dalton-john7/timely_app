"""Tests the agent loop with a fake Claude client, so no API key or network
is needed. The fake returns scripted responses: first a tool call, then a
final answer. That lets us check that the loop runs tools and passes their
results back correctly."""

import json
from types import SimpleNamespace as NS

from timelogger.agent import run_agent


class FakeClient:
    def __init__(self, scripted):
        self.scripted = list(scripted)
        self.calls = []
        self.messages = self

    def create(self, **kwargs):
        self.calls.append(json.loads(json.dumps(kwargs["messages"], default=str)))
        return self.scripted.pop(0)


def tool_use(name, inp, id_="t1"):
    return NS(stop_reason="tool_use",
              content=[NS(type="tool_use", name=name, input=inp, id=id_)])


def final(text):
    return NS(stop_reason="end_turn", content=[NS(type="text", text=text)])


def test_agent_calls_tool_and_returns_answer(logger, clock):
    logger.start("jd", "CDR-1", module="edi")
    clock.advance(45)
    logger.stop("jd")

    client = FakeClient([tool_use("get_time_by_module", {"days": 7}), final("EDI took 45m.")])
    answer = run_agent("Where did my time go?", logger, "jd", client=client)

    assert answer == "EDI took 45m."
    tool_result = client.calls[1][-1]["content"][0]
    data = json.loads(tool_result["content"])
    assert data[0]["module"] == "EDI / Order Import"
    assert data[0]["total_min"] == 45.0


def test_agent_can_start_timer(logger):
    client = FakeClient([tool_use("start_timer", {"ticket_id": "CDR-9", "module": "Warehouse"}),
                         final("Started.")])
    run_agent("start CDR-9", logger, "jd", client=client)
    assert logger.running("jd")["ticket_id"] == "CDR-9"


def test_tool_errors_are_reported_not_raised(logger):
    client = FakeClient([tool_use("stop_timer", {}), final("Nothing was running.")])
    assert run_agent("stop", logger, "jd", client=client) == "Nothing was running."
    tool_result = client.calls[1][-1]["content"][0]
    assert tool_result["is_error"] is True
