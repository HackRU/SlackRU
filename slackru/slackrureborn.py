"""
    The new main file for the slack bot
"""
from slackclient import SlackClient
import config
import time
import util
import requests


class wHacker:
    def __init__(self, hackerID, request):
        self.h = hackerID
        self.r = request


class eventObj:
    def __init__(self, startime, summary):
        self.s = startime
        self.sum = summary


# List Of Waiting Hacker -> Hackers who are currently waiting for a mentor to respond to them!
# List Of Active Channels -> Active channels created from the mentor chat.
slack_client = SlackClient(config.apiT)
BOTID = config.botID
AT_BOT = "<@" + BOTID + ">"


def parse_slack_output(slack_rtm_output):
    """
        The Slack Real Time Messaging API is an events firehose.
        this parsing function returns None unless a message is
        directed at the Bot, based on its ID.
    """
    output_list = slack_rtm_output
    if output_list and len(output_list) > 0:
        for output in output_list:
            if output and 'text' in output and AT_BOT in output['text']:
                print(output['text'])
                user_name = util.grab_user(output['user'])
                return (output['text'].split(AT_BOT)[1].strip().lower(),
                        output['channel'],
                        output['user'],
                        user_name)

    return None, None, "", ""


def handle_command(command: str, channel: str, userid: str, username: str) -> None:
    """
        Receives commands directed at the bot and determines if they
        are valid commands. If so, then acts on the commands. If not,
        returns back what it needs for clarification.
        :param command:str the command to parse
        :param channel:str the channel id
        :param userid:str the user id
        :param:str the username
        """
    print(command)
    dividedCommand = command.split()
    cmd = dividedCommand[0]
    cmd = cmd.lower()

    if cmd == 'mentors':
        print(len(dividedCommand))
        if len(dividedCommand) == 1:
            util.message(userid, "Please input a question")
        else:
            findMentor(command[8:], username, userid)
    elif cmd == 'help':
        help(userid, username)
        # call the findAvailMentorCommand


def findMentor(command: str, username: str, userid: str) -> str:
    """
        Makes a post request to the server and passes the pairing to he mentee
        :param command:str the parsedcommand
        :param username:str the username
    """
    postData = {}
    postData['data'] = command
    postData['user'] = username
    postData['userid'] = userid
    util.message(userid, "Trying to find a mentor")
    req = requests.post(config.serverurl + 'pairmentor', data=postData)
    return req.text


def help(userid, username):
    util.message(userid, "Hello! You requested the help command, here are a list of commands you can use delimeted by |'s:")
    util.message(userid, "All commands will begin with <AT character>slackru")
    util.message(userid, """Hacker:\n| mentors <keywords> | -> This command takes keywords and attempts to set you up with a mentor
                    \n| help  | -> Wait what?
                    \n | announcements | -> returns next 5 events \n  | hours | -> returns hours left in the hackathon
                    \nMentor:\n| shortenList <password> <hacker id> | -> Used to help a hackers whose keywords could not be found.
                   \n | unbusy | makes your busy status 0, so you can help more people!
                   \n | busy | -> opposite of the guy above, used when you want to afk I guess""")


# sends message to a channel
if __name__ == "__main__":
    READ_WEBSOCKET_DELAY = 1  # 1 second delay between reading from firehose
    if slack_client.rtm_connect():
        print("SlackRU connected and running!")
        while True:
            command, channel, userid, username = parse_slack_output(slack_client.rtm_read())
            if command and channel:
                handle_command(command, channel, userid, username)
                # check busy status of all users, their last time busy and if they have been busy for more than 35 minutes
            time.sleep(READ_WEBSOCKET_DELAY)
            # This function will check on all the active channels and if the latest response was an hour ago from the current time
            # The bot will message the channel and let them know it will be stop being monitored and give them insturctions
            # For certain scenarios.
    else:
        print("Connection failed. Invalid Slack token or bot ID?")