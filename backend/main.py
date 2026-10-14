"""FastAPI backend for the Campus Customs agent desk."""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sqlite3
import sys
from pathlib import Path
from threading import RLock
from typing import Any, Iterable, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

try:
    from .audit import DEFAULT_AUDIT_PATH, record_event
    from .models import AgentRole, PaymentApprovalRequest
    from .team import build_team
except ImportError:  # Supports `uvicorn main:app` from inside backend/.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from backend.audit import DEFAULT_AUDIT_PATH, record_event
    from backend.models import AgentRole, PaymentApprovalRequest
    from backend.team import build_team


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASE_DATABASE = PROJECT_ROOT / "data" / "campus_customs.db"
WORKING_DATABASE = PROJECT_ROOT / "data" / "campus_customs_new.db"
_DATABASE_LOCK = RLock()

app = FastAPI(title="Campus Customs desk API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/")
def api_home() -> dict[str, Any]:
    """Give visitors a useful landing response instead of FastAPI's 404 page."""
    return {
        "service": "Campus Customs desk API",
        "status": "online",
        "docs": "/docs",
        "tickets": "/api/tickets",
        "events": "/api/events?limit=50",
        "checking": "/api/cash/checking",
    }


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(WORKING_DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def _rows(query: str, parameters: Iterable[Any] = ()) -> list[dict[str, Any]]:
    with _DATABASE_LOCK, _connect() as connection:
        return [dict(row) for row in connection.execute(query, tuple(parameters)).fetchall()]


def _one(query: str, parameters: Iterable[Any] = ()) -> Optional[dict[str, Any]]:
    with _DATABASE_LOCK, _connect() as connection:
        row = connection.execute(query, tuple(parameters)).fetchone()
        return dict(row) if row is not None else None


def _mark_ticket_resolved(ticket_id: int) -> None:
    """Persist completion after a successful bounded agent run."""
    with _DATABASE_LOCK, _connect() as connection:
        connection.execute("UPDATE tickets SET status = 'resolved' WHERE id = ?", (ticket_id,))
        connection.commit()


def _ticket_view(ticket: dict[str, Any]) -> dict[str, Any]:
    status = str(ticket.get("status", "")).lower()
    if status == "open":
        state = "open"
    elif status in {"resolved", "closed", "paid"}:
        state = "resolved"
    else:
        state = status
    return {**ticket, "state": state, "resolved": state == "resolved"}


def _recent_events(limit: int) -> list[dict[str, Any]]:
    if not DEFAULT_AUDIT_PATH.exists():
        return []
    try:
        data = json.loads(DEFAULT_AUDIT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail=f"Audit trail is unreadable: {exc}") from exc
    if not isinstance(data, list):
        raise HTTPException(status_code=500, detail="Audit trail must contain a JSON list")

    events = []
    for event in data[-limit:]:
        if not isinstance(event, dict):
            continue
        action = event.get("action")
        is_tool_event = str(event.get("event", "")).startswith("mcp_call")
        events.append(
            {
                **event,
                "agent_said": event.get("output_summary", ""),
                "tool": action if is_tool_event else None,
                "tools_used": [action] if is_tool_event and action else [],
            }
        )
    return events


@app.get("/api/tickets")
@app.get("/tickets", include_in_schema=False)
def get_tickets() -> dict[str, Any]:
    """Return all three tickets with a normalized open/resolved state."""
    tickets = [_ticket_view(ticket) for ticket in _rows("SELECT * FROM tickets ORDER BY id")]
    return {"tickets": tickets}


@app.post("/api/tickets/{ticket_id}/run")
@app.post("/tickets/{ticket_id}/run", include_in_schema=False)
async def run_ticket(ticket_id: int) -> dict[str, Any]:
    """Run Boss on one ticket; specialists and MCP calls are audited as they execute."""
    ticket = _one("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
    if ticket is None:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} was not found")

    objective = (
        f"Resolve ticket {ticket_id}. Start by using MCP to inspect this ticket, delegate only to the "
        "specialists needed for its evidence, and return a board-ready plan. Follow all shop rules: "
        "desk.date_today is today, vendor lead times and invoice blockers come from MCP, payments need "
        "human approval, and communications remain drafts."
    )
    try:
        # The bulk-price ticket needs one evidence pass; keeping that run to a
        # single Boss handoff prevents repetitive cross-ticket exploration.
        rounds = 1 if ticket_id == 103 else 3
        hops = 1 if ticket_id == 103 else 4
        result = await build_team().run(objective, max_rounds=rounds, max_hops=hops)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Agent run failed: {exc}") from exc

    _mark_ticket_resolved(ticket_id)
    resolved_ticket = _one("SELECT * FROM tickets WHERE id = ?", (ticket_id,)) or ticket
    return {
        "ticket": _ticket_view(resolved_ticket),
        "run": result.model_dump(mode="json"),
        "events": _recent_events(50),
    }


@app.get("/api/events")
@app.get("/events", include_in_schema=False)
def get_events(limit: int = Query(default=50, ge=1, le=200)) -> dict[str, Any]:
    """Return recent agent statements, delegation actions, and MCP tool calls."""
    return {"events": _recent_events(limit)}


@app.post("/api/payments/approve")
@app.post("/payments/approve", include_in_schema=False)
def approve_payment(request: PaymentApprovalRequest) -> dict[str, Any]:
    """Apply an explicitly human-approved payment without allowing a negative balance."""
    account_name = request.account.strip()
    approver = request.approved_by.strip()
    if not account_name:
        raise HTTPException(status_code=422, detail="A cash account is required")
    if not approver:
        raise HTTPException(status_code=422, detail="A named human approver is required")
    with _DATABASE_LOCK:
        connection = _connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            account = connection.execute(
                "SELECT * FROM cash_accounts WHERE name = ?", (account_name,)
            ).fetchone()
            if account is None:
                raise HTTPException(status_code=404, detail=f"Cash account {account_name!r} was not found")

            obligation: Optional[sqlite3.Row] = None
            if request.kind == "invoice":
                obligation = connection.execute(
                    "SELECT * FROM invoices WHERE id = ?", (request.ref_id,)
                ).fetchone()
                if obligation is None:
                    raise HTTPException(status_code=404, detail=f"Invoice {request.ref_id} was not found")
                if obligation["status"].lower() != "open":
                    raise HTTPException(status_code=409, detail="That invoice is not open")
                amount = float(obligation["amount"])
            elif request.kind == "lease":
                obligation = connection.execute(
                    "SELECT * FROM leases WHERE id = ?", (request.ref_id,)
                ).fetchone()
                if obligation is None:
                    raise HTTPException(status_code=404, detail=f"Lease {request.ref_id} was not found")
                amount = float(obligation["monthly_rent"])
            else:
                if request.amount is None:
                    raise HTTPException(status_code=422, detail="A purchase amount is required")
                amount = float(request.amount)

            if request.amount is not None and request.kind != "purchase" and abs(request.amount - amount) > 0.005:
                raise HTTPException(status_code=422, detail="Approved amount does not match the obligation")
            if amount <= 0:
                raise HTTPException(status_code=422, detail="Payment amount must be positive")

            duplicate = connection.execute(
                "SELECT id FROM payments WHERE kind = ? AND ref_id = ? LIMIT 1",
                (request.kind, request.ref_id),
            ).fetchone()
            if duplicate is not None:
                raise HTTPException(status_code=409, detail="That obligation already has a payment")

            balance = float(account["balance"])
            if amount > balance:
                raise HTTPException(status_code=409, detail="Payment refused: insufficient cash")

            desk = connection.execute("SELECT date_today FROM desk LIMIT 1").fetchone()
            paid_at = str(desk["date_today"]) if desk is not None else ""
            payment_cursor = connection.execute(
                "INSERT INTO payments(kind, ref_id, amount, account, paid_at, approved_by) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (request.kind, request.ref_id, amount, account_name, paid_at, approver),
            )
            connection.execute(
                "UPDATE cash_accounts SET balance = balance - ?, date = ? WHERE name = ?",
                (amount, paid_at, account_name),
            )
            if request.kind == "invoice":
                connection.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (request.ref_id,))
            connection.commit()
            new_balance = balance - amount
            payment_id = payment_cursor.lastrowid
        except HTTPException:
            connection.rollback()
            raise
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    record_event(
        run_id=f"api-approval-{uuid4()}",
        agent=AgentRole.BOSS,
        step=1,
        event="human_payment_approved",
        action="approve_payment",
        input_value={"kind": request.kind, "ref_id": request.ref_id, "account": account_name},
        output_value={"payment_id": payment_id, "amount": amount, "new_balance": new_balance},
        metadata={"actor": "human", "approved_by": approver},
    )
    return {
        "payment_id": payment_id,
        "kind": request.kind,
        "ref_id": request.ref_id,
        "amount": amount,
        "account": account_name,
        "approved_by": approver,
        "balance": new_balance,
    }


@app.get("/api/cash/checking")
@app.get("/cash/checking", include_in_schema=False)
def get_checking_balance() -> dict[str, Any]:
    """Return the current checking balance from the working database."""
    account = _one("SELECT name, balance, date FROM cash_accounts WHERE name = 'checking'")
    if account is None:
        raise HTTPException(status_code=404, detail="Checking account was not found")
    return account


@app.post("/api/reset")
@app.post("/reset", include_in_schema=False)
def reset_database() -> dict[str, Any]:
    """Restore the working database from the untouched original baseline."""
    if not BASE_DATABASE.exists():
        raise HTTPException(status_code=500, detail="Original database is missing")
    with _DATABASE_LOCK:
        try:
            shutil.copy2(BASE_DATABASE, WORKING_DATABASE)
        except OSError as exc:
            raise HTTPException(status_code=500, detail=f"Database reset failed: {exc}") from exc
    return {"reset": True, "database": str(WORKING_DATABASE), **get_tickets(), "cash": get_checking_balance()}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Campus Customs PydanticAI team")
    parser.add_argument("objective", help="Ticket or shop objective for Boss to coordinate")
    parser.add_argument("--rounds", type=int, default=3, choices=range(1, 4))
    parser.add_argument("--hops", type=int, default=4, choices=range(0, 7))
    return parser.parse_args()


async def run_from_cli() -> None:
    args = parse_args()
    result = await build_team().run(args.objective, max_rounds=args.rounds, max_hops=args.hops)
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(run_from_cli())
