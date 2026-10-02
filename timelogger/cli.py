"""Command-line interface.

    python -m timelogger start CDR-10432 --module edi --customer "Tidewater"
    python -m timelogger doc                # switch to documentation
    python -m timelogger stop --note "Remapped UPCs, reprocessed file"
    python -m timelogger status
    python -m timelogger report --days 7
    python -m timelogger ask "Where did my time go this week?"
    python -m timelogger handoff            # AI-written end-of-shift note
    python -m timelogger demo               # load a week of sample data
"""

import argparse
import getpass
import os
import sys

from . import db, reports
from .modules import DAC_MODULES
from .timer import TimeLogger, TimerError


def _fmt(minutes):
    minutes = minutes or 0
    return f"{int(minutes // 60)}h {int(minutes % 60):02d}m" if minutes >= 60 else f"{minutes:.0f}m"


def _table(rows, cols):
    if not rows:
        print("  (no data)")
        return
    widths = [max(len(c), *(len(str(r[c])) for r in rows)) for c in cols]
    print("  " + "  ".join(c.ljust(w) for c, w in zip(cols, widths)))
    print("  " + "  ".join("-" * w for w in widths))
    for r in rows:
        print("  " + "  ".join(str(r[c]).ljust(w) for c, w in zip(cols, widths)))


def build_parser():
    p = argparse.ArgumentParser(prog="timelogger", description="DAC help desk time logger")
    p.add_argument("--db", help="database file (default: ~/.dac_timelogger.db)")
    p.add_argument("--agent", default=os.environ.get("TIMELOGGER_AGENT", getpass.getuser()),
                   help="analyst username (default: $TIMELOGGER_AGENT or your login)")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("start", help="start timing a ticket")
    s.add_argument("ticket_id")
    s.add_argument("--module", help="DAC module, e.g. 'edi', 'tobacco', 'warehouse'")
    s.add_argument("--customer")
    s.add_argument("--subject")
    s.add_argument("--note")

    sub.add_parser("doc", help="switch the running ticket to documentation time")
    sub.add_parser("work", help="switch the running ticket back to work time")

    s = sub.add_parser("stop", help="stop the running timer")
    s.add_argument("--note")

    sub.add_parser("status", help="show the running timer")
    sub.add_parser("modules", help="list DAC module categories")

    s = sub.add_parser("report", help="time summary")
    s.add_argument("--days", type=int, default=7)
    s.add_argument("--team", action="store_true", help="include all analysts")

    s = sub.add_parser("ask", help="ask the AI assistant a question")
    s.add_argument("question", nargs="+")
    s.add_argument("-v", "--verbose", action="store_true", help="show tool calls")

    s = sub.add_parser("handoff", help="AI-written end-of-shift handoff note")
    s.add_argument("-v", "--verbose", action="store_true")

    sub.add_parser("demo", help="load a week of fictional sample data")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    conn = db.connect(args.db)
    logger = TimeLogger(conn)
    me = args.agent

    try:
        if args.cmd == "start":
            e = logger.start(me, args.ticket_id, module=args.module, customer=args.customer,
                             subject=args.subject, note=args.note)
            print(f"▶ {e['ticket_id']} [{e['module']}] {e['phase']} started {e['started_at']} UTC")
        elif args.cmd in ("doc", "work"):
            e = logger.switch_phase(me, "documentation" if args.cmd == "doc" else "work")
            print(f"↺ {e['ticket_id']} now in {e['phase']}")
        elif args.cmd == "stop":
            e = logger.stop(me, note=args.note)
            print(f"■ {e['ticket_id']} {e['phase']} stopped: {_fmt(e['minutes'])}")
        elif args.cmd == "status":
            e = logger.running(me)
            print(f"▶ {e['ticket_id']} [{e['module']}] {e['phase']} since {e['started_at']} UTC"
                  if e else "No timer running.")
        elif args.cmd == "modules":
            print("\n".join(DAC_MODULES))
        elif args.cmd == "report":
            who = None if args.team else me
            print(f"\nTime by module, last {args.days} days ({'team' if args.team else me})")
            _table(reports.time_by_module(conn, args.days, who),
                   ["module", "tickets", "total_min", "work_min", "doc_min", "doc_pct",
                    "avg_min_per_ticket"])
            print("\nTop tickets")
            _table(reports.top_tickets(conn, args.days, 5, who),
                   ["ticket_id", "customer", "module", "total_min", "sessions"])
            print()
        elif args.cmd in ("ask", "handoff"):
            if not os.environ.get("ANTHROPIC_API_KEY"):
                sys.exit("Set ANTHROPIC_API_KEY to use the AI assistant (see README).")
            from .agent import run_agent
            q = (" ".join(args.question) if args.cmd == "ask" else
                 "Write my end-of-shift handoff note for today.")
            print(run_agent(q, logger, me, verbose=args.verbose))
        elif args.cmd == "demo":
            from .demo import seed
            seed(conn)
            print("Loaded sample data for analysts 'jdalton' and 'mreyes'. "
                  "Try: python -m timelogger --agent jdalton report")
    except TimerError as exc:
        sys.exit(f"Error: {exc}")


if __name__ == "__main__":
    main()
