from fastapi import FastAPI, Body
from pydantic import BaseModel

from config import (BankAccount, Transaction, account,
                    SetBalance, SetIban, SendMoney, ScheduleTransaction, UpdateScheduledTransaction, GetMostRecentTransactions)

app = FastAPI()

@app.get("/next_id")
def next_id() -> int:
    """Get the next ID for a transaction."""
    return (
            max(
                [t.id for t in account.transactions] + [t.id for t in account.scheduled_transactions],
                default=0,
                )
            + 1
    )

@app.post("/set_balance")
def set_balance(req: SetBalance) -> dict[str, str]:
    """Set the balance of the account."""
    account.balance = req.balance
    return {
        "message": "Successfully set"
    }

@app.post("/set_iban")
def set_iban(req: SetIban) -> dict[str, str]:
    """Set the IBAN of the account."""
    account.iban = req.iban
    return {
        "message": "Successfully set"
    }

@app.get("/get_iban")
def get_iban() -> str:
    """Get the IBAN of the current bank account."""
    return account.iban

@app.post("/send_money")
def send_money(req: SendMoney) -> dict[str, str]:
    """
    Sends a transaction to the recipient.

    :param recipient: IBAN of the recipient
    :param amount: Amount of the transaction
    :param subject: Subject of the transaction
    :param date: Date of the transaction
    """
    transaction = Transaction(
        id=next_id(),
        sender=get_iban(),
        recipient=req.recipient,
        amount=req.amount,
        subject=req.subject,
        date=req.date,
        recurring=False,
    )
    account.transactions.append(transaction)

    return {
        "message": f"Transaction to {req.recipient} for {req.amount} sent.",
    }

@app.post("/schedule_transaction")
def schedule_transaction(req: ScheduleTransaction) -> dict[str, str]:
    """
    Schedule a transaction.

    :param recipient: IBAN of the recipient
    :param amount: Amount of the transaction
    :param subject: Subject of the transaction
    :param date: Next date of the transaction
    :param recurring: Is the transaction recurring
    """
    transaction = Transaction(
        id=next_id(),
        sender=get_iban(),
        recipient=req.recipient,
        amount=req.amount,
        subject=req.subject,
        date=req.date,
        recurring=req.recurring,
    )
    account.scheduled_transactions.append(transaction)

    return {
        "message": f"Transaction to {req.recipient} for {req.amount} scheduled.",
    }

@app.post("/update_scheduled_transaction")
def update_scheduled_transaction(req: UpdateScheduledTransaction) -> dict[str, str]:
    """
    Update a scheduled transaction.

    :param id: ID of the transaction (mandatory)
    :param recipient: IBAN of the recipient (optional)
    :param amount: Amount of the transaction (optional)
    :param subject: Subject of the transaction (optional)
    :param date: Next date of the transaction (optional)
    :param recurring: Is the transaction recurring (optional)
    """
    transaction = next((t for t in account.scheduled_transactions if t.id == id), None)
    if transaction:
        if req.recipient:
            transaction.recipient = req.recipient
        if req.amount:
            transaction.amount = req.amount
        if req.subject:
            transaction.subject = req.subject
        if req.date:
            transaction.date = req.date
        if req.recurring:
            transaction.recurring = req.recurring
    else:
        return {
            "error": f"Transaction with ID {id} not found.",
        }
    return {
        "message": f"Transaction with ID {id} updated.",
    }

@app.get("/get_balance")
def get_balance() -> float:
    """
    Get the balance of the account.
    """
    return account.balance

@app.post("/get_most_recent_transactions")
def get_most_recent_transactions(req: GetMostRecentTransactions) -> list[Transaction]:
    """
    Get the list of the most recent transactions, e.g. to summarize the last n transactions.

    :param n: Number of transactions to return
    """
    return [t for t in account.transactions[-int(req.n) :]]


@app.get("/get_scheduled_transactions")
def get_scheduled_transactions() -> list[Transaction]:
    """
    Get the list of scheduled transactions.
    """
    return [t for t in account.scheduled_transactions]