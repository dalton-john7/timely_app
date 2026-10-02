import sqlite3

import pytest

from timelogger import reports
from timelogger.timer import TimerError


def test_start_and_stop_records_minutes(logger, clock):
    logger.start("jd", "CDR-1", module="edi")
    clock.advance(30)
    entry = logger.stop("jd", note="fixed")
    assert entry["minutes"] == 30.0
    assert entry["note"] == "fixed"
    assert logger.running("jd") is None


def test_module_is_normalized(logger):
    e = logger.start("jd", "CDR-1", module="tob")
    assert e["module"] == "Tobacco Tax & Compliance"


def test_starting_new_ticket_stops_previous(logger, clock):
    logger.start("jd", "CDR-1")
    clock.advance(10)
    logger.start("jd", "CDR-2")
    hist = reports.ticket_history(logger.conn, "CDR-1", clock)
    assert hist[0]["ended_at"] is not None
    assert hist[0]["minutes"] == 10.0
    assert logger.running("jd")["ticket_id"] == "CDR-2"


def test_switch_to_documentation_splits_time(logger, clock):
    logger.start("jd", "CDR-1", module="warehouse")
    clock.advance(20)
    logger.switch_phase("jd", "documentation")
    clock.advance(5)
    logger.stop("jd")
    row = reports.time_by_module(logger.conn, clock=clock)[0]
    assert (row["work_min"], row["doc_min"], row["doc_pct"]) == (20.0, 5.0, 20.0)


def test_start_twice_is_harmless(logger):
    a = logger.start("jd", "CDR-1")
    b = logger.start("jd", "CDR-1")
    assert a["id"] == b["id"]


def test_stop_without_running_timer_errors(logger):
    with pytest.raises(TimerError):
        logger.stop("jd")


def test_database_blocks_two_running_timers(logger):
    """Even code that bypasses TimeLogger can't create two running timers."""
    logger.start("jd", "CDR-1")
    with pytest.raises(sqlite3.IntegrityError):
        logger.conn.execute(
            "INSERT INTO time_entries (ticket_id, agent, phase, started_at) "
            "VALUES ('CDR-1', 'jd', 'work', '2026-01-01 00:00:00')"
        )


def test_analysts_have_independent_timers(logger):
    logger.start("jd", "CDR-1")
    logger.start("mr", "CDR-2")
    assert logger.running("jd")["ticket_id"] == "CDR-1"
    assert logger.running("mr")["ticket_id"] == "CDR-2"


def test_reports_include_running_timer(logger, clock):
    logger.start("jd", "CDR-1")
    clock.advance(15)
    assert reports.top_tickets(logger.conn, clock=clock)[0]["total_min"] == 15.0
