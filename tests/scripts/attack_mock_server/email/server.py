from config import inbox, Email, EmailContact, CloudDriveFileID, CalendarEvent, SendEmail, SearchEmails, DeleteEmail, SearchContactsByName, SearchContactsByEmail
from fastapi import FastAPI

app = FastAPI()

@app.get("/get_unread_emails")
def get_unread_emails() -> list[Email]:
    """Returns all the unread emails in the inbox. Each email has a sender, a subject, and a body.
    The emails are marked as read after this function is called."""
    return inbox.get_unread()

@app.post("/send_email")
def send_email(
        req: SendEmail
) -> Email | dict[str, str]:
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
    try:
        if req.attachments is not None:
            parsed_attachments = []
            for attachment in req.attachments:
                if not isinstance(attachment, dict):
                    raise ValueError("Attachments must be dictionaries.")
                if "type" not in attachment:
                    raise ValueError("Attachment must have a 'type' field.")
                if attachment["type"] == "file" or "file_id" in attachment:
                    if "file_id" not in attachment:
                        raise ValueError("Attachment of type 'file' must have a 'file_id' field.")
                    parsed_attachments.append(CloudDriveFileID(attachment["file_id"]))
                else:
                    if "event_details" not in attachment:
                        raise ValueError("Attachment of type 'event' must have an 'event_details' field.")
                    parsed_attachments.append(CalendarEvent(**attachment["event_details"]))
        else:
            parsed_attachments = None
    except Exception as e:
        return {
            "error" : str(e)
        }

    return inbox.send_email(req.recipients, req.subject, req.body, parsed_attachments, req.cc, req.bcc)

@app.post("/search_emails")
def search_emails(
        req: SearchEmails
) -> list[Email] | dict[str, str]:
    """Searches for emails in the inbox that contain the given query in the subject or body. If `address` is provided,
    only emails from that address are searched.

    :param query: The query to search for in the email subject or body. If empty, all emails are returned.
    :param sender: The email address of the sender. If `null`, all emails are searched. Use `search_contacts_by_name`
    if the email address is unknown.
    """
    try:
        matches = inbox.search_emails(req.query, req.sender)
        if len(matches) == 0:
            raise ValueError("No emails found. Try with a different query.")
    except Exception as e:
        return {
            "error" : str(e)
        }

    return matches

@app.post("/delete_email")
def delete_email(req: DeleteEmail) -> str | dict[str, str]:
    """Deletes the email with the given `email_id` from the inbox.

    :param email_id: The id of the email to delete.
    """
    try:
        inbox.delete_email(req.email_id)
    except Exception as e:
        return {
            "error" : str(e)
        }

    return f"Email with id {req.email_id} deleted successfully."


@app.get("/get_sent_emails")
def get_sent_emails() -> list[Email]:
    """Returns all the sent emails in the inbox. Each email has a recipient, a subject, and a body."""
    return inbox.sent


@app.get("/get_received_emails")
def get_received_emails() -> list[Email]:
    """Returns all the received emails in the inbox. Each email has a sender, a subject, and a body."""
    return inbox.received

@app.get("/get_draft_emails")
def get_draft_emails() -> list[Email]:
    """Returns all the draft emails in the inbox. Each email has a recipient, a subject, and a body."""
    return inbox.drafts

@app.post("/search_contacts_by_name")
def search_contacts_by_name(req: SearchContactsByName) -> list[EmailContact] | dict[str, str]:
    """Finds contacts in the inbox's contact list by name.
    It returns a list of contacts that match the given name.

    :param query: The name of the contacts to search for.
    """
    try:
        return inbox.find_contacts_by_name(req.query)
    except Exception as e:
        return {
            "error" : str(e)
        }

@app.post("/search_contacts_by_email")
def search_contacts_by_email(req: SearchContactsByEmail) -> list[EmailContact] | dict[str, str]:
    """Finds contacts in the inbox's contact list by email.
    It returns a list of contacts that match the given email.

    :param query: The email of the contacts to search for.
    """
    try:
        return inbox.find_contacts_by_email(req.query)
    except Exception as e:
        return {
            "error" : str(e)
        }