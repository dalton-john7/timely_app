"""Event-driven automation: the "plug in an API and it works" layer.

WHY THIS FILE EXISTS
--------------------
Right now analysts start and stop timers by hand. Help desks already produce
events that show when work starts and stops, from two kinds of systems:

1. The ticketing platform (Zendesk, Freshdesk, ServiceNow, Jira Service
   Management, and others). These can send a *webhook*: an HTTP POST with a
   JSON body, sent automatically whenever a ticket changes (assigned, status
   changed, comment added, solved).

2. The phone system / contact center (RingCentral, Five9, Genesys, 8x8,
   Teams Phone, and others). Their CTI (computer-telephony integration)
   features send events like "call answered" and "call ended", and can often
   attach a ticket number through a "screen pop".

`handle_event()` below is the whole decision engine. It takes a *normalized*
event (a plain dict in our own format) and decides whether to start, switch,
or stop a timer. It already works and has tests. To go live, you only write a
small *adapter* that turns the vendor's payload into this format. An example
adapter, `from_ticket_webhook()`, is at the bottom of this file.

TRIGGER DESIGN
--------------
  event type                         action
  ---------------------------------  -----------------------------------------
  call.answered                      START work on the linked ticket
  ticket.status_changed -> open /    START work (the analyst picked it up)
     in_progress (and assigned to
     this analyst)
  call.ended                         SWITCH to documentation (wrap-up time)
  ticket.note_started                SWITCH to documentation
  ticket.status_changed -> pending / STOP (waiting on customer or vendor; don't
     on_hold                         bill waiting time to the ticket)
  ticket.status_changed -> solved /  STOP
     closed
  ticket.reassigned (away from us)   STOP
  agent.idle / agent.logged_off      STOP (safety net for forgotten timers)

Two design choices:
- Events for a ticket the analyst is *not* currently timing never stop
  anything. A late "solved" event for yesterday's ticket must not kill
  today's timer.
- Every automated entry is saved with source='automation'. Reports can then
  compare automated and manual accuracy while the automation is being trialed.
"""

from .timer import TimeLogger

START_STATUSES = {"open", "in_progress"}
STOP_STATUSES = {"pending", "on_hold", "solved", "closed"}


def handle_event(logger: TimeLogger, event: dict) -> dict:
    """Apply one normalized event. Returns {"action": ..., "detail": ...}.

    Normalized event shape:
        {
          "type":      "call.answered" | "call.ended" | "ticket.status_changed"
                       | "ticket.note_started" | "ticket.reassigned"
                       | "agent.idle" | "agent.logged_off",
          "agent":     "jdalton",            # required
          "ticket_id": "CDR-10432",          # required for call/ticket events
          "status":    "in_progress",        # for ticket.status_changed
          "module":    "EDI / Order Import", # optional extra details
          "customer":  "Tidewater Wholesale",
          "subject":   "PDI order file not importing",
        }
    """
    etype = event.get("type")
    agent = event.get("agent")
    ticket = event.get("ticket_id")
    if not agent:
        return {"action": "ignored", "detail": "event has no agent"}

    current = logger.running(agent)
    on_this_ticket = bool(current and ticket and current["ticket_id"] == ticket)
    extra = {k: event.get(k) for k in ("module", "customer", "subject")}

    def start(phase):
        entry = logger.start(agent, ticket, phase=phase, source="automation", **extra)
        return {"action": f"started_{phase}", "detail": entry}

    def stop(reason):
        entry = logger.stop(agent, note=f"auto-stop: {reason}")
        return {"action": "stopped", "detail": entry}

    if etype == "call.answered" and ticket:
        return start("work")

    if etype == "ticket.status_changed" and ticket:
        status = (event.get("status") or "").lower()
        if status in START_STATUSES:
            return start("work")
        if status in STOP_STATUSES and on_this_ticket:
            return stop(f"status -> {status}")

    if etype in ("call.ended", "ticket.note_started") and on_this_ticket:
        return start("documentation")

    if etype == "ticket.reassigned" and on_this_ticket:
        return stop("ticket reassigned")

    if etype in ("agent.idle", "agent.logged_off") and current:
        return stop(etype)

    return {"action": "ignored", "detail": f"no rule for {etype!r} in current state"}


# ---------------------------------------------------------------------------
# Example adapter. Most ticketing platforms let you design the JSON body their
# webhook sends. The shape below is one you might configure. A Flask route
# like this would receive it:
#
#     @app.post("/webhooks/ticketing")
#     def ticketing_webhook():
#         return handle_event(logger, from_ticket_webhook(request.json))
#
# In production you would also verify the webhook's signature header, so
# no one can forge events.
# ---------------------------------------------------------------------------
_STATUS_MAP = {
    "new": "open", "open": "open", "in progress": "in_progress",
    "pending": "pending", "on-hold": "on_hold", "hold": "on_hold",
    "solved": "solved", "closed": "closed",
}


def from_ticket_webhook(payload: dict) -> dict:
    """Convert an example ticketing-platform webhook into a normalized event."""
    t = payload.get("ticket", {})
    return {
        "type": "ticket.status_changed",
        "agent": (payload.get("assignee") or {}).get("username"),
        "ticket_id": str(t.get("id")),
        "status": _STATUS_MAP.get(str(t.get("status", "")).lower(), t.get("status")),
        "module": t.get("category"),
        "customer": (payload.get("organization") or {}).get("name"),
        "subject": t.get("subject"),
    }
