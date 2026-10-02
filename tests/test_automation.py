"""These tests show the automation already works. Going live only requires
an adapter from a real ticketing or phone system to these events."""

from timelogger.automation import from_ticket_webhook, handle_event


def ev(type_, **kw):
    return {"type": type_, "agent": "jd", **kw}


def test_full_call_lifecycle(logger, clock):
    assert handle_event(logger, ev("call.answered", ticket_id="CDR-1"))["action"] == "started_work"
    clock.advance(12)
    assert handle_event(logger, ev("call.ended", ticket_id="CDR-1"))["action"] == "started_documentation"
    clock.advance(4)
    r = handle_event(logger, ev("ticket.status_changed", ticket_id="CDR-1", status="solved"))
    assert r["action"] == "stopped"
    assert r["detail"]["source"] == "automation"
    assert "solved" in r["detail"]["note"]


def test_pending_status_stops_timer(logger):
    handle_event(logger, ev("ticket.status_changed", ticket_id="CDR-1", status="in_progress"))
    r = handle_event(logger, ev("ticket.status_changed", ticket_id="CDR-1", status="pending"))
    assert r["action"] == "stopped"


def test_event_for_other_ticket_does_not_stop_current(logger):
    handle_event(logger, ev("call.answered", ticket_id="CDR-2"))
    r = handle_event(logger, ev("ticket.status_changed", ticket_id="CDR-1", status="solved"))
    assert r["action"] == "ignored"
    assert logger.running("jd")["ticket_id"] == "CDR-2"


def test_idle_is_a_safety_net(logger):
    handle_event(logger, ev("call.answered", ticket_id="CDR-1"))
    assert handle_event(logger, ev("agent.idle"))["action"] == "stopped"
    assert handle_event(logger, ev("agent.idle"))["action"] == "ignored"


def test_event_without_agent_is_ignored(logger):
    assert handle_event(logger, {"type": "call.answered", "ticket_id": "X"})["action"] == "ignored"


def test_webhook_adapter_end_to_end(logger):
    payload = {
        "ticket": {"id": 10432, "status": "In Progress", "category": "edi",
                   "subject": "Order file stuck"},
        "assignee": {"username": "jd"},
        "organization": {"name": "Tidewater Wholesale"},
    }
    r = handle_event(logger, from_ticket_webhook(payload))
    assert r["action"] == "started_work"
    assert r["detail"]["module"] == "EDI / Order Import"
    assert r["detail"]["customer"] == "Tidewater Wholesale"
