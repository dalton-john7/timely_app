"""Ticket categories, modeled on the functional areas of the DAC ERP.

Tagging every ticket with the module it touches is what makes the reports
useful: a lead can see that, say, EDI tickets take twice as long as
purchasing tickets and plan training or staffing around it.
"""

DAC_MODULES = [
    "Order Management",
    "EDI / Order Import",
    "Warehouse",
    "Purchasing",
    "Inventory",
    "Pricing / Pricebook",
    "Tobacco Tax & Compliance",
    "Financials / Month-End",
    "Delivery / Routes",
    "Returns",
    "Equipment",
    "Reporting",
    "Other",
]

# Time is split into two phases. Call centers call the second one
# "wrap-up" or "after-call work" (ACW). Tracking it on its own shows how much
# of the day goes to writing things up, not just fixing things.
PHASES = ("work", "documentation")


def normalize_module(value: str) -> str:
    """Match user input to a known module, case-insensitively.

    Accepts a full name ("warehouse") or a unique prefix ("tob").
    Anything unrecognized becomes "Other" so logging is never blocked.
    """
    if not value:
        return "Other"
    v = value.strip().lower()
    for m in DAC_MODULES:
        if m.lower() == v:
            return m
    matches = [m for m in DAC_MODULES if m.lower().startswith(v)]
    return matches[0] if len(matches) == 1 else "Other"
