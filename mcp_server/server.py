"""Read-only FastMCP tools for the Campus Customs shop database."""

from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Literal, Optional
from urllib.parse import quote

from mcp.server.fastmcp import FastMCP


DATABASE_PATH = Path(__file__).resolve().parents[1] / "data" / "campus_customs_new.db"
DATABASE_URI = "file:{}?mode=ro".format(quote(str(DATABASE_PATH), safe="/"))

mcp = FastMCP("Campus Customs")


def _connect() -> sqlite3.Connection:
    """Open the working database without permitting writes."""
    connection = sqlite3.connect(DATABASE_URI, uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _row(connection: sqlite3.Connection, query: str, parameters: tuple[Any, ...]) -> Optional[Dict[str, Any]]:
    result = connection.execute(query, parameters).fetchone()
    return dict(result) if result is not None else None


@mcp.tool()
def inspect_customer_order(ticket_id: int) -> Dict[str, Any]:
    """Read a customer-order ticket and its inventory, invoice, and vendor records.

    Ticket 101 uses this view to determine whether the requested item is on hand
    and which vendor and invoice are associated with replenishment.
    """
    with _connect() as connection:
        ticket = _row(connection, "SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        if ticket is None:
            return {"error": "Ticket {} was not found.".format(ticket_id)}

        inventory = None
        if ticket["sku"] is not None and ticket["size"] is not None:
            inventory = _row(
                connection,
                "SELECT * FROM inventory WHERE sku = ? AND size = ?",
                (ticket["sku"], ticket["size"]),
            )

        invoice = None
        vendor = None
        if ticket["invoice_id"] is not None:
            invoice = _row(connection, "SELECT * FROM invoices WHERE id = ?", (ticket["invoice_id"],))
            if invoice is not None:
                vendor = _row(connection, "SELECT * FROM vendors WHERE id = ?", (invoice["vendor_id"],))

        return {
            "ticket": ticket,
            "inventory": inventory,
            "invoice": invoice,
            "vendor": vendor,
        }


@mcp.tool()
def inspect_rent_notice(ticket_id: int) -> Dict[str, Any]:
    """Read a rent-notice ticket, its lease, and the shop's operating date.

    Ticket 102 uses this view to compare the linked lease due date with
    ``desk.date_today`` before preparing a rent response.
    """
    with _connect() as connection:
        ticket = _row(connection, "SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        if ticket is None:
            return {"error": "Ticket {} was not found.".format(ticket_id)}

        lease = None
        if ticket["lease_id"] is not None:
            lease = _row(connection, "SELECT * FROM leases WHERE id = ?", (ticket["lease_id"],))
        desk = _row(connection, "SELECT * FROM desk LIMIT 1", ())

        return {"ticket": ticket, "lease": lease, "desk": desk}


@mcp.tool()
def evaluate_bulk_price_override(ticket_id: int) -> Dict[str, Any]:
    """Read a bulk-price request with its stock and catalog pricing records.

    Ticket 103 uses this view to compare the requested quantity with available
    stock and to review the database's unit cost and list price.
    """
    with _connect() as connection:
        ticket = _row(connection, "SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        if ticket is None:
            return {"error": "Ticket {} was not found.".format(ticket_id)}

        inventory = None
        pricing = None
        if ticket["sku"] is not None:
            pricing = _row(connection, "SELECT * FROM pricing WHERE sku = ?", (ticket["sku"],))
            if ticket["size"] is not None:
                inventory = _row(
                    connection,
                    "SELECT * FROM inventory WHERE sku = ? AND size = ?",
                    (ticket["sku"], ticket["size"]),
                )

        requested_quantity = ticket["qty"]
        available_quantity = inventory["qty"] if inventory is not None else None
        quantity_gap = None
        if requested_quantity is not None and available_quantity is not None:
            quantity_gap = requested_quantity - available_quantity

        return {
            "ticket": ticket,
            "inventory": inventory,
            "pricing": pricing,
            "quantity_gap": quantity_gap,
        }


@mcp.tool()
def list_open_tickets() -> List[Dict[str, Any]]:
    """List the currently open tickets that the team is responsible for."""
    with _connect() as connection:
        rows = connection.execute("SELECT * FROM tickets WHERE status = 'open' ORDER BY id").fetchall()
        return [dict(row) for row in rows]


@mcp.tool()
def inspect_vendor_shipping(vendor_id: int) -> Dict[str, Any]:
    """Read a vendor and its invoices to determine whether an open bill blocks shipping."""
    with _connect() as connection:
        vendor = _row(connection, "SELECT * FROM vendors WHERE id = ?", (vendor_id,))
        invoices = [
            dict(row)
            for row in connection.execute(
                "SELECT * FROM invoices WHERE vendor_id = ? ORDER BY id", (vendor_id,)
            ).fetchall()
        ]
        shipping_blocked = any(invoice["status"].lower() == "open" for invoice in invoices)
        return {
            "vendor": vendor,
            "invoices": invoices,
            "shipping_blocked": shipping_blocked,
        }


@mcp.tool()
def inspect_payment_readiness(kind: Literal["invoice", "lease"], ref_id: int) -> Dict[str, Any]:
    """Read cash, payment history, and the invoice or lease targeted by a payment draft."""
    with _connect() as connection:
        cash_accounts = [dict(row) for row in connection.execute("SELECT * FROM cash_accounts ORDER BY name")]
        payments = [
            dict(row)
            for row in connection.execute(
                "SELECT * FROM payments WHERE kind = ? AND ref_id = ? ORDER BY id",
                (kind, ref_id),
            ).fetchall()
        ]

        if kind == "invoice":
            obligation = _row(connection, "SELECT * FROM invoices WHERE id = ?", (ref_id,))
        else:
            obligation = _row(connection, "SELECT * FROM leases WHERE id = ?", (ref_id,))

        return {
            "kind": kind,
            "ref_id": ref_id,
            "obligation": obligation,
            "cash_accounts": cash_accounts,
            "payments": payments,
        }


if __name__ == "__main__":
    mcp.run()
