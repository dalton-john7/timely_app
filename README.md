# DAC Help Desk Time Logger

A time-tracking tool with an AI assistant, built for ERP help desk teams that
support convenience-store distributors on the DAC ERP.

Help desk time rarely goes where you expect. One stalled EDI order import can
eat an afternoon, and writing up the fix takes time of its own. This tool
records that time by **ticket**, by **DAC module**, and by **phase** (hands-on
*work* vs. *documentation*). It turns the data into reports a lead can staff
and train around.

## Features

- **Manual start / switch / stop timers** from the command line
- **Work vs. documentation split.** Wrap-up time is tracked on its own,
  because it is real work that tends to get squeezed when the queue is busy.
- **SQL reports**: time by module, top time-consuming tickets, daily totals
- **One running timer per analyst**, enforced by a partial unique index in the database
- **Automation-ready.** `automation.py` contains a tested event engine that
  maps ticketing and phone-system events (call answered, call ended, ticket
  solved, etc.) to timer actions. Going live only needs a small adapter for
  the real platform's webhooks.
- **AI assistant (Claude with tool use).** Ask questions in plain English
  ("Where did my time go this week?") or generate an end-of-shift handoff
  note. The assistant calls the same report functions, so it never makes up
  numbers.

## Quick start

```bash
pip install -r requirements.txt
python -m timelogger demo                      # load a week of fictional sample data
python -m timelogger --agent jdalton report    # time by module + top tickets

python -m timelogger start CDR-20001 --module edi --customer "Tidewater Wholesale"
python -m timelogger doc                       # switch to documentation time
python -m timelogger stop --note "Remapped UPCs and reprocessed order file"
```

### AI assistant

```bash
export ANTHROPIC_API_KEY=sk-ant-...            # from console.anthropic.com
python -m timelogger --agent jdalton ask "Which module is slowing me down and why?" -v
python -m timelogger --agent jdalton handoff
```

`-v` prints each tool the agent calls, which is useful for seeing the agent
loop in action. Set `TIMELOGGER_MODEL` to choose a different Claude model.

## How it's built

| File | Purpose |
|---|---|
| `timelogger/db.py` | SQLite schema (tickets, time entries, constraints, indexes) |
| `timelogger/timer.py` | Start / switch / stop rules shared by every interface |
| `timelogger/reports.py` | Reporting, one SQL query per report |
| `timelogger/automation.py` | Event-driven start/stop design + example webhook adapter |
| `timelogger/agent.py` | Claude tool-use agent loop with guardrails |
| `timelogger/cli.py` | Command-line interface |
| `tests/` | pytest suite. Uses a fake clock and a fake Claude client, so tests run offline in under a second |

```bash
pytest -q
```

## Roadmap

See [ROADMAP.md](ROADMAP.md). Next up: a **ticket-surge calendar** of
customer deadlines (tax filings, month-end close, compliance reporting)
that drive spikes in ticket volume.

---
Personal portfolio project. All customers and tickets in the sample data
are fictional. Not affiliated with or endorsed by CDR Software.
