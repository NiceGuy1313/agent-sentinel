import requests as req
import argparse
import json
import sys

tools = [
    "get_unread_emails",
    "send_email",
    "search_emails",
    "delete_email",
    "get_sent_emails",
    "get_received_emails",
    "get_draft_emails",
    "search_contacts_by_name",
    "search_contacts_by_email",
]

targetURL = "http://172.17.0.2:9006"

def get_unread_emails(*args):
    """Returns all the unread emails in the inbox. Each email has a sender, a subject, and a body.
    The emails are marked as read after this function is called."""
    return req.get(targetURL + "/get_unread_emails").text

def send_email(data, *args):
    """Sends an email with the given `body` to the given `address`. Returns a dictionary with the email details.

    :param recipients: The list with the email addresses of the recipients.
    :param subject: The subject of the email.
    :param body: The body of the email.
    :param attachments: The list of attachments to include in the email. If `null`, no attachments are included.
    If the attachment has as "type" "file", then it is expected to have a field "file_id", with the ID of the file in the
    cloud drive. If the attachment has as "type" "event", then it is expected to be a calendar event in the field "event_details".
    A calendar event has the following fields: `title`, `description`, `start_time` (in ISO format), `end_time`
    (in ISO format), `location`, and participants (a list of emails).
    :param cc: The list of email addresses to include in the CC field. If `null`, no email addresses are included.
    :param bcc: The list of email addresses to include in the BCC field. If `null`, no email addresses are included.
    """
    return req.post(targetURL + "/send_email", data = data).text

def search_emails(data, *args):
    """Searches for emails in the inbox that contain the given query in the subject or body. If `address` is provided,
    only emails from that address are searched.

    :param query: The query to search for in the email subject or body. If empty, all emails are returned.
    :param sender: The email address of the sender. If `null`, all emails are searched. Use `search_contacts_by_name`
    if the email address is unknown.
    """
    return req.post(targetURL + "/search_emails", data = data).text

def delete_email(data, *args):
    """Deletes the email with the given `email_id` from the inbox.

    :param email_id: The id of the email to delete.
    """
    return req.post(targetURL + "/delete_email", data = data).text

def get_sent_emails(data, *args):
    """Returns all the sent emails in the inbox. Each email has a recipient, a subject, and a body."""
    return req.get(targetURL + "/get_sent_emails").text

def get_received_emails(data, *args):
    """Returns all the received emails in the inbox. Each email has a sender, a subject, and a body."""

    return req.get(targetURL + "/get_received_emails").text

def get_draft_emails(data, *args):
    """Returns all the draft emails in the inbox. Each email has a recipient, a subject, and a body."""

    return req.get(targetURL + "/get_draft_emails").text

def search_contacts_by_name(data, *args):
    """Finds contacts in the inbox's contact list by name.
    It returns a list of contacts that match the given name.

    :param query: The name of the contacts to search for.
    """

    return req.post(targetURL + "/search_contacts_by_name", data = data).text

def search_contacts_by_email(data, *args):
    """Finds contacts in the inbox's contact list by email.
    It returns a list of contacts that match the given email.

    :param query: The email of the contacts to search for.
    """

    return req.post(targetURL + "/search_contacts_by_email", data = data).text

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
            raise ValueError("invalid action")


        print(f"The description and required parameters of action {{{values}}} as follows:\n" + globals()[values].__doc__)
        parser.exit()

def main():
    parser = argparse.ArgumentParser(
        prog="emailcli",
        description="A client program to connect the email server",
        formatter_class = CustomHelpFormatter
    )

    parser.add_argument("-a", "--action",
                        choices=tools,
                        help="The request action to the email server")

    parser.add_argument("-d", "--data", default=None, help="The request data to the email server")
    parser.add_argument("-e", "--explain", metavar="<action>", action=HelperAction, help="Explain the specific action")

    if len(sys.argv) == 1:
        parser.print_help()
        parser.exit()

    args = parser.parse_args()

    rep = globals()[args.action](args.data)
    print(rep)

if __name__ == "__main__":
    main()