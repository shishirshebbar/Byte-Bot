from datetime import datetime
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Request, Response
from pydantic import BaseModel
from .sessions import COOKIE, get_owner
from .errors import error
from .settings import COOKIE_SECURE

router = APIRouter()


class Transaction(BaseModel):
    id: UUID
    direction: Literal["incoming"]
    amount_paise: int
    currency: Literal["INR"]
    sender_name: str
    sender_vpa: str
    receiver_vpa: str
    occurred_at: datetime
    status: Literal["successful", "pending", "failed"]
    reference: str
    source: Literal["mock"]


class TransactionList(BaseModel):
    transactions: list[Transaction]


def fetch(request, response, transaction_id=None):
    with request.app.state.pool.connection() as conn:
        owner, token = get_owner(conn, request.cookies.get(COOKIE))
        if transaction_id is None:
            rows = conn.execute("SELECT * FROM transactions WHERE owner_id = %s ORDER BY occurred_at DESC, id", (owner,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM transactions WHERE owner_id = %s AND id = %s", (owner, transaction_id)).fetchall()
    # Cookie only follows a committed session and fixture set.
    if token:
        response.set_cookie(COOKIE, token, httponly=True, samesite="lax", secure=COOKIE_SECURE, path="/")
    response.headers["Cache-Control"] = "no-store"
    return rows


@router.get("/transactions", response_model=TransactionList)
def list_transactions(request: Request, response: Response):
    return {"transactions": fetch(request, response)}


@router.get("/transactions/{transaction_id}", response_model=Transaction)
def transaction_detail(transaction_id: UUID, request: Request, response: Response):
    rows = fetch(request, response, transaction_id)
    if not rows:
        result = error(404, "not_found", "Transaction not found.")
        if "set-cookie" in response.headers:
            result.headers["set-cookie"] = response.headers["set-cookie"]
        return result
    return rows[0]
