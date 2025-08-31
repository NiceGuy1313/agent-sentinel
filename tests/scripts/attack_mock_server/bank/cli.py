import requests as req
import argparse
import json
import sys

targetURL = "http://172.17.0.2:9001"

tools = [
    "next_id",
    "set_balance",
    "get_balance",
    "set_iban",
    "get_iban",
    "send_money",
    "schedule_transaction",
    "update_scheduled_transaction",
    "get_most_recent_transactions",
    "get_scheduled_transactions"
]

def next_id(*args):
    """Get the next ID for a transaction."""
    return req.get(targetURL + "/next_id").text

def set_balance(data, *args):
    """Set the balance of the account.

    :param balance: The balance
    """

    return req.post(targetURL + "/set_balance", data = data).text

def get_balance(*args):
    """Get the balance of the account."""

    return req.get(targetURL + "/get_balance").text

def set_iban(data, *args):
    """Set the IBAN of the account.

    :param iban: The IBAN
    """

    return req.post(targetURL + "/set_iban", data = data).text

def get_iban(*args):
    """Get the IBAN of the current bank account."""

    return req.get(targetURL + "/get_iban").text

def send_money(data, *args):
    """
    Sends a transaction to the recipient.

    :param recipient: IBAN of the recipient
    :param amount: Amount of the transaction
    :param subject: Subject of the transaction
    :param date: Date of the transaction
    """

    return req.post(targetURL + "/send_money", data = data).text

def schedule_transaction(data, *args):
    """
    Schedule a transaction.

    :param recipient: IBAN of the recipient
    :param amount: Amount of the transaction
    :param subject: Subject of the transaction
    :param date: Next date of the transaction
    :param recurring: Is the transaction recurring
    """
    return req.post(targetURL + "/schedule_transaction", data = data).text

def update_scheduled_transaction(data, *args):
    """
    Update a scheduled transaction.

    :param id: ID of the transaction (mandatory)
    :param recipient: IBAN of the recipient (optional)
    :param amount: Amount of the transaction (optional)
    :param subject: Subject of the transaction (optional)
    :param date: Next date of the transaction (optional)
    :param recurring: Is the transaction recurring (optional)
    """
    return req.post(targetURL + "/update_scheduled_transaction", data = data).text

def get_most_recent_transactions(data, *args):
    """
    Get the list of the most recent transactions, e.g. to summarize the last n transactions.

    :param n: Number of transactions to return
    """
    return req.post(targetURL + "/get_most_recent_transactions", data = data).text

def get_scheduled_transactions(*args):
    """
    Get the list of scheduled transactions.
    """
    return req.get(targetURL + "/get_scheduled_transactions").text


class CustomHelpFormatter(argparse.HelpFormatter):
    def _format_action_invocation(self, action):
        if not action.option_strings or action.nargs == 0:
            return super()._format_action_invocation(action)
        default = self._get_default_metavar_for_optional(action)
        args_string = self._format_args(action, default)
        return ', '.join(action.option_strings) + ' ' + args_string

class HelperAction(argparse.Action):
    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        if nargs is not None:
            raise ValueError("nargs not allowed")
        super().__init__(option_strings, dest, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):

        if values not in tools:
            raise ValueError(f"invalid action {{{values}}}")

        print(f"The description and required parameters of action {{{values}}} as follows:\n" + globals()[values].__doc__)
        parser.exit()

def main():
    parser = argparse.ArgumentParser(
        prog="bankcli",
        description="A client program to connect the bank server",
        formatter_class=CustomHelpFormatter
    )
    parser.add_argument("-a", "--action",
                        choices=tools,
                        help="The request action to the bank server")

    parser.add_argument("-d", "--data", default=None, help="The request data to the bank server. Note that the data should be in JSON format.")
    parser.add_argument("-e", "--explain", metavar="<action>", action=HelperAction, help="Explain the specific action")

    if len(sys.argv) == 1:
        parser.print_help()
        parser.exit()

    args = parser.parse_args()

    if args.action is not None:
        rep = globals()[args.action](args.data)
        print(rep)


if __name__ == "__main__":
    main()