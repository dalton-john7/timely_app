"""AI assistant built on Claude with tool use.

WHAT MAKES THIS AN "AGENT"
--------------------------
A chatbot only answers from what it already knows. An agent can *take
actions*. We give Claude a set of tools (plain Python functions, described
in TOOLS below). Claude decides which tools to call and with what arguments.
We run them and send the results back, and this repeats until Claude has
what it needs to answer. That loop is `run_agent()`.

Example: asked "Why was my Tuesday so slow?", Claude might call
get_time_by_module(days=7), notice EDI dominated, call get_top_tickets(),
then answer: "Two stalled EDI order-import tickets for Tidewater Wholesale
took 2.5 hours..."

Guardrails:
- Claude can read reports and start or stop *the current analyst's* timer.
  Nothing more. Tools are the only way it can touch data.
- The loop stops after MAX_TURNS, so it can never run away.
- The Anthropic client is passed in (dependency injection), so tests use a
  fake client and never call the real API.
"""

import json
import os

from . import reports
from .modules import DAC_MODULES

DEFAULT_MODEL = os.environ.get("TIMELOGGER_MODEL", "claude-sonnet-4-5")
MAX_TURNS = 8

SYSTEM_PROMPT = f"""You are a help desk operations assistant for an ERP support team.
The team supports convenience-store distributors who use the DAC ERP
(orders, EDI order import, warehouse, purchasing, pricing, tobacco tax and
compliance reporting, month-end financials, delivery routes).

You help one analyst ({{agent}}) understand and manage their time:
- Answer questions about where time went, using the tools. Never guess numbers.
- Point out patterns: modules that take long, tickets that keep coming back,
  documentation time that is unusually high or low.
- When asked, write an end-of-shift handoff note: open or running tickets
  first, then notable issues, then time totals.
- You may start or stop the analyst's timer when they ask you to.

Known modules: {", ".join(DAC_MODULES)}.
Keep answers short and practical: a few sentences or a short list. Minutes
over 90 should be shown as hours and minutes."""

TOOLS = [
    {
        "name": "get_time_by_module",
        "description": "Total, work, and documentation minutes per DAC module "
                       "over the last N days for the current analyst.",
        "input_schema": {
            "type": "object",
            "properties": {"days": {"type": "integer", "default": 7}},
        },
    },
    {
        "name": "get_top_tickets",
        "description": "The tickets that consumed the most time in the last N days.",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "default": 7},
                "limit": {"type": "integer", "default": 5},
            },
        },
    },
    {
        "name": "get_daily_totals",
        "description": "Minutes and ticket counts per day for the current analyst.",
        "input_schema": {
            "type": "object",
            "properties": {"days": {"type": "integer", "default": 7}},
        },
    },
    {
        "name": "get_ticket_history",
        "description": "Every time entry (work and documentation) for one ticket.",
        "input_schema": {
            "type": "object",
            "properties": {"ticket_id": {"type": "string"}},
            "required": ["ticket_id"],
        },
    },
    {
        "name": "get_running_timer",
        "description": "The analyst's currently running timer, if any.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "start_timer",
        "description": "Start timing a ticket for the current analyst. Stops any "
                       "running timer first.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string"},
                "phase": {"type": "string", "enum": ["work", "documentation"]},
                "module": {"type": "string", "enum": DAC_MODULES},
            },
            "required": ["ticket_id"],
        },
    },
    {
        "name": "stop_timer",
        "description": "Stop the analyst's running timer.",
        "input_schema": {
            "type": "object",
            "properties": {"note": {"type": "string"}},
        },
    },
]


def execute_tool(name, args, logger, agent):
    """Run one tool call and return a JSON-serializable result."""
    conn, clock = logger.conn, logger.clock
    if name == "get_time_by_module":
        return reports.time_by_module(conn, args.get("days", 7), agent, clock)
    if name == "get_top_tickets":
        return reports.top_tickets(conn, args.get("days", 7), args.get("limit", 5), agent, clock)
    if name == "get_daily_totals":
        return reports.daily_totals(conn, args.get("days", 7), agent, clock)
    if name == "get_ticket_history":
        return reports.ticket_history(conn, args["ticket_id"], clock)
    if name == "get_running_timer":
        return logger.running(agent) or {"running": False}
    if name == "start_timer":
        return logger.start(agent, args["ticket_id"], phase=args.get("phase", "work"),
                            module=args.get("module"))
    if name == "stop_timer":
        return logger.stop(agent, note=args.get("note"))
    raise ValueError(f"unknown tool {name}")


def run_agent(question, logger, agent, client=None, model=DEFAULT_MODEL, verbose=False):
    """Ask the assistant a question. Returns the final text answer."""
    if client is None:
        import anthropic  # imported here so the rest of the app works without it
        client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment

    messages = [{"role": "user", "content": question}]
    for _ in range(MAX_TURNS):
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            system=SYSTEM_PROMPT.format(agent=agent),
            tools=TOOLS,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            return "".join(b.text for b in response.content if b.type == "text").strip()

        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            try:
                output = execute_tool(block.name, block.input, logger, agent)
                is_error = False
            except Exception as exc:  # tell Claude what failed so it can adjust
                output, is_error = {"error": str(exc)}, True
            if verbose:
                print(f"  [tool] {block.name}({block.input})")
            results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(output, default=str),
                "is_error": is_error,
            })
        messages.append({"role": "user", "content": results})

    return "Stopped after too many steps. Try a more specific question."
