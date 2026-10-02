# Roadmap

## Next: Ticket-surge calendar

**Idea:** Distributors' support needs follow their own business calendar.
Ticket volume spikes before deadlines the *customer* has to meet. A shared
calendar of those dates lets the team see a rush coming. They can schedule
coverage, avoid PTO on crunch days, and refresh how-to articles before
the calls start.

Dates to track (to be confirmed with the team; many vary by state and customer):

- **State / local tobacco tax filings.** Monthly returns, usually due mid-month
  for the prior month. Varies by state, and some counties and cities have
  their own.
- **Manufacturer / MSA reporting windows.** Periodic sales reports to
  tobacco manufacturers and programs.
- **Month-end close** (last and first few business days of each month)
- **Quarter- and year-end close**, plus year-end 1099s and inventory counts
- **Price-change effective dates** (e.g. manufacturer cigarette price
  increases), which drive pricebook and retailer EDI tickets
- **Holiday route schedule changes.** Delivery days shift and order cutoffs move.
- **Software release / upgrade dates** for DAC itself

**Planned design:**
- `surge_events` table: name, category, date or recurrence rule, states
  affected, expected impact (low/med/high), prep checklist
- `upcoming` CLI command and an AI tool: "What's coming in the next two weeks?"
- Link to time data: compare ticket volume and minutes before and after each
  event to *measure* which dates actually cause surges, then adjust
  impact ratings from real history

## Later

- Web dashboard (Flask) with charts
- Live integration: webhook endpoint using `automation.handle_event`
- Knowledge-base suggestions: flag modules or ticket types with high repeat
  time as candidates for new help articles
- Team view for leads: coverage vs. forecast surge
