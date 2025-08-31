import requests as req
import argparse
import json
import sys

tools = [
    "get_channels",
    "add_user_to_channel",
    "read_channel_messages",
    "read_inbox",
    "send_direct_message",
    "send_channel_message",
    "invite_user_to_slack",
    "remove_user_from_slack",
    "get_users_in_channel",
]

targetURL = "http://172.17.0.2:9002"

def get_channels(*args):
    """Get the list of channels in the slack."""
    return req.get(targetURL + "/get_channels").text

def add_user_to_channel(data, *args):
    """Add a user to a given channel.

    :param user: The user to add to the channel.
    :param channel: The channel to add the user to.
    """
    return req.post(targetURL + "/add_user_to_channel", data = data).text

def read_channel_messages(data, *args):
    """Read the messages from the given channel.

    :param channel: The channel to read the messages from.
    """
    return req.post(targetURL + "/read_channel_messages", data = data).text

def read_inbox(data, *args):
    """Read the messages from the given user inbox.

    :param user: The user whose inbox to read.
    """
    return req.post(targetURL + "/read_inbox", data = data).text

def send_direct_message(data, *args):
    """Send a direct message from `author` to `recipient` with the given `content`.

    :param recipient: The recipient of the message.
    :param body: The body of the message.
    """
    return req.post(targetURL + "/send_direct_message", data = data).text

def send_channel_message(data, *args):
    """Send a channel message from `author` to `channel` with the given `content`.

    :param channel: The channel to send the message to.
    :param body: The body of the message.
    """

    return req.post(targetURL + "/send_channel_message", data = data).text

def invite_user_to_slack(data, *args):
    """Invites a user to the Slack workspace.

    :param user: The user to invite.
    :param user_email: The user email where invite should be sent.
    """

    return req.post(targetURL + "/invite_user_to_slack", data = data).text

def remove_user_from_slack(data, *args):
    """Remove a user from the Slack workspace.

    :param user: The user to remove.
    """

    return req.post(targetURL + "/remove_user_from_slack", data = data).text

def get_users_in_channel(data, *args):
    """Get the list of users in the given channel.

    :param channel: The channel to get the users from.
    """

    return req.post(targetURL + "/get_users_in_channel", data = data).text

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
        prog="slackcli",
        description="A client program to connect the slack server",
        formatter_class = CustomHelpFormatter
    )

    parser.add_argument("-a", "--action",
                        choices=tools,
                        help="The request action to the slack server")

    parser.add_argument("-d", "--data", default=None, help="The request data to the slack server")
    parser.add_argument("-e", "--explain", metavar="<action>", action=HelperAction, help="Explain the specific action")

    if len(sys.argv) == 1:
        parser.print_help()
        parser.exit()

    args = parser.parse_args()

    rep = globals()[args.action](args.data)
    print(rep)

if __name__ == "__main__":
    main()