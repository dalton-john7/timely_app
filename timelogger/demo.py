"""Generate a realistic week of fictional sample data for demos.

All customers and tickets are invented. The ticket subjects reflect common
kinds of distribution-ERP support issues.
"""

import random
from datetime import timedelta

from .timer import TIME_FMT, utc_now

SAMPLE_TICKETS = [
    ("EDI / Order Import", "Tidewater Wholesale", "Retailer order file not importing before route cutoff"),
    ("EDI / Order Import", "Blue Ridge Distributing", "Item UPCs rejected on inbound store order"),
    ("Tobacco Tax & Compliance", "Coastal C-Store Supply", "State cigarette tax report totals don't match sales"),
    ("Tobacco Tax & Compliance", "Piedmont Candy & Tobacco", "MSA report missing a manufacturer category"),
    ("Financials / Month-End", "Tidewater Wholesale", "Month-end close: AR aging out of balance"),
    ("Warehouse", "Harbor Point Distribution", "Pick tickets printing in wrong slot order"),
    ("Pricing / Pricebook", "Blue Ridge Distributing", "Price change not reaching retailer pricebook"),
    ("Delivery / Routes", "Coastal C-Store Supply", "Driver handheld not syncing invoices"),
    ("Purchasing", "Harbor Point Distribution", "Suggested order quantities too high for candy"),
    ("Returns", "Piedmont Candy & Tobacco", "Credit memo not posting for damaged returns"),
    ("Order Management", "Tidewater Wholesale", "Customer can't see web order history"),
    ("Inventory", "Harbor Point Distribution", "On-hand qty negative after cycle count"),
]


def seed(conn, agents=("jdalton", "mreyes"), days=5, rng_seed=42, clock=utc_now):
    """Insert sample tickets and completed time entries covering the past few days."""
    rng = random.Random(rng_seed)
    now = clock()
    n = 10400
    with conn:
        for agent in agents:
            for d in range(days, 0, -1):
                t = (now - timedelta(days=d)).replace(hour=13, minute=0, second=0)  # 9am ET
                for _ in range(rng.randint(5, 8)):
                    module, customer, subject = rng.choice(SAMPLE_TICKETS)
                    n += 1
                    ticket_id = f"CDR-{n}"
                    conn.execute(
                        "INSERT OR IGNORE INTO tickets VALUES (?, ?, ?, ?, ?)",
                        (ticket_id, customer, module, subject, t.strftime(TIME_FMT)),
                    )
                    # EDI and tax issues run longer. That pattern is what the reports should reveal.
                    slow = module in ("EDI / Order Import", "Tobacco Tax & Compliance")
                    work = rng.randint(25, 70) if slow else rng.randint(8, 35)
                    doc = max(3, int(work * rng.uniform(0.15, 0.4)))
                    for phase, mins in (("work", work), ("documentation", doc)):
                        end = t + timedelta(minutes=mins)
                        conn.execute(
                            "INSERT INTO time_entries (ticket_id, agent, phase, started_at, "
                            "ended_at, source) VALUES (?, ?, ?, ?, ?, 'manual')",
                            (ticket_id, agent, phase,
                             t.strftime(TIME_FMT), end.strftime(TIME_FMT)),
                        )
                        t = end
                    t += timedelta(minutes=rng.randint(2, 15))
