"""Core timer logic: start, switch phase, stop.

Every way of controlling a timer goes through this class: the CLI (manual
today), the automation event handler (automation.py), and the AI agent
(agent.py). Keeping the rules in one place means they behave the same no
matter who presses "start".

HOW THIS COULD BE AUTOMATED
---------------------------
v0.1 uses manual start and stop on purpose: it's simple, and it lets us
collect honest data first. The full automation design is in the docstring
of automation.py. In short:

  START "work" when
    - the analyst answers a support call (phone system / CTI "call answered"), or
    - a ticket assigned to the analyst is set to "In Progress"
  SWITCH to "documentation" when
    - the call ends (the call center's "wrap-up" / after-call-work period), or
    - the analyst starts writing an internal note or resolution
  STOP when
    - the ticket is Solved, set to Pending / On Hold, or reassigned
    - the analyst opens a different ticket (handled below: starting a new
      timer stops the old one), or
    - the analyst is idle / logs off (a safety net for forgotten timers)

And yes, documentation time should be captured. It is real work, it often
takes 20-40% of a ticket's total time, and it is the part most likely to be
cut short when the queue is busy. Tracking it lets a lead see when
documentation quality is slipping because of workload.
"""

from datetime import datetime, timezone
from typing import Callable, Optional

from .modules import PHASES, normalize_module

TIME_FMT = "%Y-%m-%d %H:%M:%S"


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


class TimerError(Exception):
    """Raised for invalid timer actions (e.g. stopping when nothing runs)."""


class TimeLogger:
    def __init__(self, conn, clock: Callable[[], datetime] = utc_now):
        # `clock` is injectable so tests can control time exactly.
        self.conn = conn
        self.clock = clock

    # ------------------------------------------------------------------ helpers
    def _now(self) -> str:
        return self.clock().strftime(TIME_FMT)

    def ensure_ticket(self, ticket_id, module=None, customer=None, subject=None):
        """Create the ticket if new. Fill in any details we didn't have before."""
        row = self.conn.execute(
            "SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id,)
        ).fetchone()
        if row is None:
            self.conn.execute(
                "INSERT INTO tickets (ticket_id, customer, module, subject, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (ticket_id, customer, normalize_module(module or ""), subject, self._now()),
            )
        else:
            self.conn.execute(
                """UPDATE tickets SET
                       customer = COALESCE(?, customer),
                       module   = CASE WHEN ? IS NOT NULL THEN ? ELSE module END,
                       subject  = COALESCE(?, subject)
                   WHERE ticket_id = ?""",
                (customer, module, normalize_module(module or ""), subject, ticket_id),
            )

    def running(self, agent: str) -> Optional[dict]:
        """Return the analyst's running timer, or None."""
        row = self.conn.execute(
            """SELECT e.*, t.module, t.customer, t.subject
                 FROM time_entries e JOIN tickets t USING (ticket_id)
                WHERE e.agent = ? AND e.ended_at IS NULL""",
            (agent,),
        ).fetchone()
        return dict(row) if row else None

    # ------------------------------------------------------------------ actions
    def start(self, agent, ticket_id, phase="work", module=None, customer=None,
              subject=None, note=None, source="manual") -> dict:
        """Start timing a ticket.

        If the analyst already has a timer running, it is stopped first. That
        matches reality: switching to another ticket means you stopped working
        on the last one.
        """
        if phase not in PHASES:
            raise TimerError(f"phase must be one of {PHASES}")
        with self.conn:  # one transaction: stop the old timer + start the new one
            current = self.running(agent)
            if current:
                if current["ticket_id"] == ticket_id and current["phase"] == phase:
                    return current  # already timing this; calling start twice is harmless
                self._close(current["id"])
            self.ensure_ticket(ticket_id, module, customer, subject)
            self.conn.execute(
                "INSERT INTO time_entries (ticket_id, agent, phase, started_at, source, note) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (ticket_id, agent, phase, self._now(), source, note),
            )
        return self.running(agent)

    def switch_phase(self, agent, phase="documentation", source="manual") -> dict:
        """Switch the running ticket from work to documentation, or back."""
        current = self.running(agent)
        if not current:
            raise TimerError(f"{agent} has no running timer")
        return self.start(agent, current["ticket_id"], phase=phase, source=source)

    def stop(self, agent, note=None) -> dict:
        """Stop the analyst's running timer and return the finished entry."""
        current = self.running(agent)
        if not current:
            raise TimerError(f"{agent} has no running timer")
        with self.conn:
            self._close(current["id"], note)
        row = self.conn.execute(
            """SELECT e.*, ROUND((julianday(ended_at) - julianday(started_at)) * 1440, 1)
                          AS minutes
                 FROM time_entries e WHERE id = ?""",
            (current["id"],),
        ).fetchone()
        return dict(row)

    def _close(self, entry_id, note=None):
        self.conn.execute(
            "UPDATE time_entries SET ended_at = ?, note = COALESCE(?, note) WHERE id = ?",
            (self._now(), note, entry_id),
        )
