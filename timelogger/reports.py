"""Reporting queries. Every report here is a single SQL statement.

Timers that are still running count up to "now", so reports stay accurate
during the day. Durations use SQLite's julianday(): subtracting two julian
days gives a fraction of a day, and multiplying by 1440 turns it into minutes.
"""

from datetime import timedelta

from .timer import TIME_FMT, utc_now

_MINUTES = "(julianday(COALESCE(e.ended_at, :now)) - julianday(e.started_at)) * 1440"


def _params(clock, days, agent):
    now = clock()
    return {
        "now": now.strftime(TIME_FMT),
        "since": (now - timedelta(days=days)).strftime(TIME_FMT),
        "agent": agent,
    }


def time_by_module(conn, days=7, agent=None, clock=utc_now):
    """Minutes per DAC module, split into work and documentation.

    Answers questions like "which part of DAC eats most of our time?" and
    "where is documentation taking longest?"
    """
    sql = f"""
    SELECT t.module,
           COUNT(DISTINCT e.ticket_id)                                         AS tickets,
           ROUND(SUM({_MINUTES}), 1)                                           AS total_min,
           ROUND(SUM(CASE WHEN e.phase = 'work' THEN {_MINUTES} ELSE 0 END), 1) AS work_min,
           ROUND(SUM(CASE WHEN e.phase = 'documentation'
                          THEN {_MINUTES} ELSE 0 END), 1)                      AS doc_min,
           ROUND(SUM({_MINUTES}) / COUNT(DISTINCT e.ticket_id), 1)             AS avg_min_per_ticket
      FROM time_entries e
      JOIN tickets t USING (ticket_id)
     WHERE e.started_at >= :since
       AND (:agent IS NULL OR e.agent = :agent)
     GROUP BY t.module
     ORDER BY total_min DESC
    """
    rows = [dict(r) for r in conn.execute(sql, _params(clock, days, agent))]
    for r in rows:
        r["doc_pct"] = round(100 * r["doc_min"] / r["total_min"], 1) if r["total_min"] else 0.0
    return rows


def ticket_history(conn, ticket_id, clock=utc_now):
    """Every time entry for one ticket, oldest first, with minutes."""
    sql = f"""
    SELECT e.id, e.agent, e.phase, e.started_at, e.ended_at, e.source, e.note,
           ROUND({_MINUTES}, 1) AS minutes
      FROM time_entries e
     WHERE e.ticket_id = :ticket_id
     ORDER BY e.started_at
    """
    p = _params(clock, 0, None)
    p["ticket_id"] = ticket_id
    return [dict(r) for r in conn.execute(sql, p)]


def top_tickets(conn, days=7, limit=5, agent=None, clock=utc_now):
    """The tickets that took the most time. These often point to a
    knowledge-base article worth writing or a bug worth escalating."""
    sql = f"""
    SELECT e.ticket_id, t.customer, t.module, t.subject,
           ROUND(SUM({_MINUTES}), 1) AS total_min,
           COUNT(*)                  AS sessions
      FROM time_entries e
      JOIN tickets t USING (ticket_id)
     WHERE e.started_at >= :since
       AND (:agent IS NULL OR e.agent = :agent)
     GROUP BY e.ticket_id
     ORDER BY total_min DESC
     LIMIT :limit
    """
    p = _params(clock, days, agent)
    p["limit"] = limit
    return [dict(r) for r in conn.execute(sql, p)]


def daily_totals(conn, days=7, agent=None, clock=utc_now):
    """Minutes logged per analyst per day."""
    sql = f"""
    SELECT DATE(e.started_at) AS day, e.agent,
           ROUND(SUM({_MINUTES}), 1) AS total_min,
           COUNT(DISTINCT e.ticket_id) AS tickets
      FROM time_entries e
     WHERE e.started_at >= :since
       AND (:agent IS NULL OR e.agent = :agent)
     GROUP BY day, e.agent
     ORDER BY day, e.agent
    """
    return [dict(r) for r in conn.execute(sql, _params(clock, days, agent))]
