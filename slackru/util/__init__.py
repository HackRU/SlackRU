import os

from slackclient import SlackClient

from slackru.util.slackapi import SlackAPI


slack = SlackAPI(SlackClient(os.environ['SLACK_API_KEY']))


def ifTestingThen(func, *args, inverted=False, **kwargs):
    """ Higher-Order Debugging Utility

    Calls function only if debugging is enabled.
    """
    from slackru.config import config
    if config.TESTING ^ inverted:  # Bitwise XOR operator
        func(*args, **kwargs)


def ifNotTestingThen(func, *args, **kwargs):
    ifTestingThen(func, *args, inverted=True, **kwargs)
