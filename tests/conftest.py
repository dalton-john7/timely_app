from datetime import datetime, timedelta

import pytest

from timelogger import db
from timelogger.timer import TimeLogger


class FakeClock:
    """A clock the test controls: time only moves when we call advance()."""

    def __init__(self, start=datetime(2026, 10, 5, 13, 0, 0)):
        self.now = start

    def __call__(self):
        return self.now

    def advance(self, minutes):
        self.now += timedelta(minutes=minutes)


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def logger(clock):
    conn = db.connect(":memory:")  # a fresh in-memory database for every test
    return TimeLogger(conn, clock=clock)
