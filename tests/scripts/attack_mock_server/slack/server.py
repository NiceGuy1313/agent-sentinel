from config import (Slack, Message, slack,
        AddUserToChannel, ReadChannelMessage, ReadInbox, SendDirectMessage, SendChannelMessage, InviteUserToSlack, RemoveUserFromSlack, GetUsersInChannel)
from fastapi import FastAPI, Body


app = FastAPI()

@app.get("/get_channels")
def get_channels() -> list[str]:
    """Get the list of channels in the slack."""
    return slack.channels

@app.post("/add_user_to_channel")
def add_user_to_channel(req: AddUserToChannel) -> dict[str, str]:
    """Add a user to a given channel.

    :param user: The user to add to the channel.
    :param channel: The channel to add the user to.
    """
    if req.user not in slack.users:
        return {
            "error": f"User {req.user} not found in the users list"
        }
    if req.channel not in slack.channels:
        return {
            "error": f"Channel {req.channel} not found in the channels list"
        }
    slack.user_channels[req.user].append(req.channel)
    return {
        "message": f"Added {req.user} to {req.channel}"
    }

@app.post("/read_channel_messages")
def read_channel_messages(req: ReadChannelMessage) -> dict[str, str] | list[Message]:
    """Read the messages from the given channel.

    :param channel: The channel to read the messages from.
    """
    if req.channel not in slack.channels:
        return {
            "error": "Channel does not exist!"
        }
    return slack.channel_inbox.get(req.channel, [])

@app.post("/read_inbox")
def read_inbox(req: ReadInbox) ->  dict[str, str] | list[Message]:
    """Read the messages from the given user inbox.

    :param user: The user whose inbox to read.
    """
    if req.user not in slack.users:
        return {
            "error": f"User {req.user} not found in the users list"
        }
    return slack.user_inbox.get(req.user, [])

@app.post("/send_direct_message")
def send_direct_message(req: SendDirectMessage) -> dict[str, str]:
    """Send a direct message from `author` to `recipient` with the given `content`.

    :param recipient: The recipient of the message.
    :param body: The body of the message.
    """
    sender = "bot"
    if req.recipient not in slack.users:
        return {
            "error": f"Recipient {req.recipient} not found in the users list"
        }
    msg = Message(sender=sender, recipient=req.recipient, body=req.body)
    if req.recipient not in slack.user_inbox:
        slack.user_inbox[req.recipient] = []
    slack.user_inbox[req.recipient].append(msg)
    return {
        "message": "Successfully sent"
    }

@app.post("/send_channel_message")
def send_channel_message(req: SendChannelMessage) -> dict[str, str]:
    """Send a channel message from `author` to `channel` with the given `content`.

    :param channel: The channel to send the message to.
    :param body: The body of the message.
    """
    sender = "bot"
    if req.channel not in slack.channels:
        return {
            "error": f"Channel {req.channel} not found in the channels list"
        }
    msg = Message(sender=sender, recipient=req.channel, body=req.body)
    if req.channel not in slack.channel_inbox:
        slack.channel_inbox[req.channel] = []
    slack.channel_inbox[req.channel].append(msg)
    return {
        "message": "Successfully sent"
    }

@app.post("/invite_user_to_slack")
def invite_user_to_slack(req: InviteUserToSlack) -> dict[str, str]:
    """Invites a user to the Slack workspace.

    :param user: The user to invite.
    :param user_email: The user email where invite should be sent.
    """
    if req.user in slack.users:
        return {
            "error": f"User {req.user} already in the users list"
        }
    slack.users.append(req.user)
    slack.user_inbox[req.user] = []
    slack.user_channels[req.user] = []
    return {
        "message": "Successfully invited"
    }


@app.post("/remove_user_from_slack")
def remove_user_from_slack(req: RemoveUserFromSlack) -> dict[str, str]:
    """Remove a user from the Slack workspace.

    :param user: The user to remove.
    """
    if req.user not in slack.users:
        return {
            "error": f"User {req.user} not found in the users list"
        }
    slack.users.remove(req.user)
    del slack.user_inbox[req.user]
    del slack.user_channels[req.user]
    return {
        "message": "Successfully removed"
    }

@app.post("/get_users_in_channel")
def get_users_in_channel(req: GetUsersInChannel) -> list[str] | dict[str, str]:
    """Get the list of users in the given channel.

    :param channel: The channel to get the users from.
    """
    if req.channel not in slack.channels:
        return {
            "error": f"Channel {req.channel} not found in the channels list"
        }
    users = []
    for user, channels in slack.user_channels.items():
        if req.channel in channels:
            users.append(user)
    return users