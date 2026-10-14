# Campus Customs MCP server

This FastMCP server gives shop agents read-only tools for investigating the tickets in the Campus Customs database. It uses `../data/campus_customs_new.db`, the working copy that later tasks may update; the original database is not used by the server.

It requires the MCP Python SDK 1.x (`mcp<2`), which provides the `mcp.server.fastmcp` FastMCP API; PydanticAI agent connections use the compatible FastMCP client (`fastmcp<3`).

The server currently provides six tools:

- `inspect_customer_order(ticket_id)` — reads a customer-order ticket together with its inventory, invoice, and vendor records (ticket 101).
- `inspect_rent_notice(ticket_id)` — reads a rent notice together with its linked lease and `desk.date_today` (ticket 102).
- `evaluate_bulk_price_override(ticket_id)` — reads a bulk request together with matching inventory and pricing data, including the requested-versus-available quantity gap (ticket 103).
- `list_open_tickets()` — lists the open work queue from `tickets` for the Boss agent.
- `inspect_vendor_shipping(vendor_id)` — reads a vendor and its invoices to expose lead time and the open-invoice shipping blocker for replenishment work.
- `inspect_payment_readiness(kind, ref_id)` — reads cash accounts, payment history, and the selected invoice or lease so Accounting can prepare a human-review draft without making a payment.

The server remains read-only; a later guarded workflow may add updates only when a human has explicitly approved them.
