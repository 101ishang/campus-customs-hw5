# Campus Customs Agent Harness

This harness documents the database that agents use to resolve shop tickets. The working database is `data/campus_customs_new.db`; `data/campus_customs.db` is the original baseline.

## Tables and fields

### `cash_accounts`

- `name` — TEXT, primary key
- `balance` — REAL, required
- `date` — TEXT, required

Tracks available cash by account and the date of that balance. Agents must check it before proposing or recording any payment.

### `desk`

- `date_today` — TEXT, required
- `notes` — TEXT

Provides the shop’s operating date for deciding what is overdue and stores desk-level notes.

### `inventory`

- `sku` — TEXT, required, part of primary key
- `name` — TEXT, required
- `size` — TEXT, required, part of primary key
- `qty` — INTEGER, required
- `location` — TEXT, required

Shows on-hand stock by product and size so agents can fulfill orders or identify replenishment needs.

### `invoices`

- `id` — INTEGER, primary key
- `vendor_id` — INTEGER, required, references `vendors.id`
- `amount` — REAL, required
- `due_date` — TEXT, required
- `status` — TEXT, required
- `description` — TEXT

Records vendor bills, their due dates, and open or paid status; open unpaid invoices can block vendor shipments.

### `leases`

- `id` — INTEGER, primary key
- `space_name` — TEXT, required
- `landlord` — TEXT, required
- `monthly_rent` — REAL, required
- `next_due` — TEXT, required
- `notes` — TEXT

Defines rent obligations and due dates for the shop’s leased space.

### `payments`

- `id` — INTEGER, primary key
- `kind` — TEXT, required
- `ref_id` — INTEGER
- `amount` — REAL, required
- `account` — TEXT, required
- `paid_at` — TEXT, required
- `approved_by` — TEXT, required

Audits outgoing payments and their human approval, linking a payment to the invoice or lease it settles.

### `pricing`

- `sku` — TEXT, primary key
- `unit_cost` — REAL, required
- `list_price` — REAL, required

Supplies cost and list-price data for order totals and discount decisions.

### `tickets`

- `id` — INTEGER, primary key
- `type` — TEXT, required
- `requester` — TEXT, required
- `subject` — TEXT, required
- `sku` — TEXT
- `size` — TEXT
- `qty` — INTEGER
- `lease_id` — INTEGER, references `leases.id`
- `invoice_id` — INTEGER, references `invoices.id`
- `status` — TEXT, required
- `notes` — TEXT
- `created_at` — TEXT, required

The work queue: each ticket captures a customer, rent, or pricing request and links it to the relevant records.

### `vendors`

- `id` — INTEGER, primary key
- `name` — TEXT, required
- `specialty` — TEXT, required
- `lead_days` — INTEGER, required

Lists supplier capabilities and lead times used when planning replenishment.

## Open-ticket relationships

- Ticket `101` (`customer_order`) requests one `CC-TEE-WHITE` in size `S` and links to invoice `501` through `invoice_id`. That invoice belongs to vendor `1` (`Bulldog Print Co`); inventory currently has zero of this size.
- Ticket `102` (`rent_notice`) links to lease `1` through `lease_id`. The lease is for the Chapel Street shop and is due on `2026-09-02`.
- Ticket `103` (`price_override`) requests 20 `CC-HOOD-NAVY` hoodies in size `M`. It has no lease or invoice link; use `inventory` and `pricing` to evaluate the request. Current size-M stock is 8.

## MCP tools

The read-only FastMCP server in `mcp_server/server.py` uses `data/campus_customs_new.db`.

- `inspect_customer_order(ticket_id)` reads `tickets`, `inventory`, `invoices`, and `vendors`; it helps unlock ticket `101` by showing the requested tee’s stock and the linked vendor invoice that governs replenishment.
- `inspect_rent_notice(ticket_id)` reads `tickets`, `leases`, and `desk`; it helps unlock ticket `102` by joining the rent notice to its lease and comparing its due date with the shop’s operating date.
- `evaluate_bulk_price_override(ticket_id)` reads `tickets`, `inventory`, and `pricing`; it helps unlock ticket `103` by comparing the requested hoodie quantity with size-M stock and the catalog’s cost and list price.

## Agent team

All five PydanticAI agents use `gpt-6-luna` through Portkey, share the same FastMCP toolset, and can delegate through the bounded team loop. Delegation never reads the database directly; facts come from MCP.

- **Boss** — coordinates all three open tickets through `tickets`, delegates evidence gathering, and reconciles specialist reports into an auditable plan.
- **Inventory** — uses `tickets`, `inventory`, `invoices`, `vendors`, and `pricing` for ticket `101` stock and replenishment dependencies plus ticket `103` quantity and vendor-lead questions.
- **Accounting** — uses `tickets`, `invoices`, `leases`, `cash_accounts`, and `payments` to check obligations, cash availability, payment history, and human-approval requirements for tickets `101` and `102`.
- **Facilities** — uses `tickets`, `leases`, and `desk` for ticket `102` lease and rent timing and prepares a board-only facilities draft.
- **Customer Service** — uses `tickets`, `inventory`, `invoices`, `vendors`, and `pricing` to prepare board-only responses for tickets `101` and `103` using verified stock, pricing, and timing evidence.

## MCP tools used by agents

- `inspect_customer_order(ticket_id)` reads `tickets`, `inventory`, `invoices`, and `vendors`; Inventory and Customer Service use it for ticket `101` so a tee response and replenishment plan use the linked stock and invoice evidence.
- `inspect_rent_notice(ticket_id)` reads `tickets`, `leases`, and `desk`; Facilities and Accounting use it for ticket `102` so rent timing is determined from the linked lease and `desk.date_today`.
- `evaluate_bulk_price_override(ticket_id)` reads `tickets`, `inventory`, and `pricing`; Inventory and Customer Service use it for ticket `103` so any bulk-price draft reflects the requested quantity, actual stock, and catalog prices.
- `list_open_tickets()` reads `tickets`; Boss uses it to establish the current work queue before delegating.
- `inspect_vendor_shipping(vendor_id)` reads `vendors` and `invoices`; Inventory uses it for ticket `101` to verify the vendor lead time and whether an open invoice blocks shipment.
- `inspect_payment_readiness(kind, ref_id)` reads `cash_accounts`, `payments`, and either `invoices` or `leases`; Accounting uses it for ticket `101` invoice `501` and ticket `102` lease `1` to prepare a human-review payment draft without making an unapproved payment.

## Safety and token limits

- Keep real-world communication as drafts on the board; do not email customers, call vendors, or claim that a message was sent.
- Require a named human approval before any payment, verify sufficient cash first, reject negative balances, and update the relevant payment and obligation records only through a guarded workflow.
- Treat `desk.date_today` as the shop’s date, use only MCP/database facts, preserve the original database as the reset source, and never invent vendor commitments or customer promises.
- Keep Boss loops to at most three rounds, specialist delegation to six hops, each model run to eight requests, and each request to 12,000 input / 4,000 output tokens; bounded summaries and append-only audit events limit context growth.
- Keep API keys out of prompts and audit output, and review the audit trail and proposed payment before any irreversible action.

## FastAPI routes

- `GET /api/tickets` returns all three tickets with their raw status plus normalized `state` and `resolved` fields.
- `POST /api/tickets/{ticket_id}/run` runs the bounded Boss team loop for one ticket and returns its result with recent audit events.
- `GET /api/events?limit=50` returns recent agent statements, delegation events, and MCP tool names for board refreshes.
- `POST /api/payments/approve` is the human-only control that records an invoice, lease, or purchase payment, updates checking cash, and refuses duplicates or negative balances.
- `GET /api/cash/checking` returns the current checking account row.
- `POST /api/reset` restores `data/campus_customs_new.db` from the original database.

## Route quick reference

- `GET http://localhost:8000/api/tickets` — returns tickets 101–103 with open/resolved state.
- `POST http://localhost:8000/api/tickets/{ticket_id}/run` — runs the bounded agent team for one ticket.
- `GET http://localhost:8000/api/events?limit=50` — returns recent agent statements, delegation events, and MCP tools used.
- `POST http://localhost:8000/api/payments/approve` — applies a named human-approved invoice, lease, or purchase payment.
- `GET http://localhost:8000/api/cash/checking` — returns the current checking balance.
- `POST http://localhost:8000/api/reset` — restores the working database from the original baseline.

## Dashboard

The React + Vite + TypeScript desk lives in `frontend/` and is served at `http://localhost:5173`. It calls the FastAPI routes at `http://localhost:8000`, lists all three tickets, lets an operator select one and run the team, streams recent audit events into the agent activity feed, and marks a successful run resolved. The queue keeps resolved tickets visible with green status pills, while the selected-ticket panel shows each of the five roles, its latest statement, active state, and the MCP tool chip used by that role. The lower audit panel exposes delegation and tool events, and the Human Gate panel collects a named approval before calling `POST /api/payments/approve`.

The summary cards show open/resolved counts, the live checking balance from `cash_accounts`, and the connected five-agent crew. The Cash control is intentionally separate from agent work: a payment or purchase is only applied after the human approval route succeeds, and the backend refuses duplicate or overdrawn payments. `output/desk_tickets.html` keeps the pre-run Expected plans beside the post-run Actual evidence; `output/resolved_board.html` contains browser captures of the resolved board for tickets 101, 102, and 103.

## Resolved run record

The clean run began with checking at `$3,400.00` on `desk.date_today = 2026-08-31`. Tickets 101, 102, and 103 ended with status `resolved`; no payment, purchase, or human approval occurred, so each ticket changed cash by `$0.00` and checking ended at `$3,400.00`, matching `cash_accounts` in the working database. Per-ticket outcomes, agent contributions, delegations, tools, and approvals are recorded in `output/resolved_tickets.json`; the append-only event detail remains in `output/audit_trail.json`.
