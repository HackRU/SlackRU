"""
Ideaboard
@letsmake -pn [project-name] -pd [project-description] -sh [skills-possessed] -sw [skills-wanted] -sz [team-size]
    Posts a request for a team

@letsmake list-projects
    Lists all open projects

    -a List all projects including those not open
    -m List all projects posted by current user
    -q List all projects that match query (au:[author-name], tu:[posted x hrs prior] pn:[project name contains these words]
        sh:[poster has these skills] sw:[poster wants these skills] sl:[Find projects seeking x or fewer people]
        sg:[find projects seeking x or more people]
    -s=(a|t|u|o)i Sorts list of projects alphabetically (a), timestamp (t), username (u), open status (o), invert order (i)

@letsmake status ([project-id]|all) [status]
    Change project status
    all - applies status change to all projects
    STATUSES
    open - Project needs more hands (0)
    fulfilled - Project has enough hands (1)
    noneed - Decision to not proceed with project (2)

NOTE: When entering skills, do not use spaces. If you need to, use underscores (e.g. Python3 OR Python_3)
"""

from slackclient import SlackClient
from enum import Enum
from oauth2client.service_account import ServiceAccountCredentials
from sqlalchemy.sql import select
from sqlalchemy import create_engine
from random import randint
import random as rnd
import os
import config
import time
import sqlite3
import httplib2
from apiclient.discovery import build
import datetime
import dateutil.parser
import pygal
from modules.tools import util
import requests
import re
from modules.tools import tools 

slack_client = SlackClient(config.apiT)
slack_web_client = SlackClient(config.oauthT)
BOTID = config.botID
BOTNAME = "letsmake"
AT_BOT = "@" + BOTNAME

SQL_CONN = sqlite3.connect('projects.db')
PROJECT_PRIMARY_KEY_SIZE = 5
PROJECT_TABLE_NAME = "projects"

class Message:
    def __init__(self, botname='', username='', channel='', text='', timestamp='', _type=''):
        self.botname = botname
        self.username = username
        self.channel = channel
        self.text = text
        self.timestamp = timestamp
        self.type = _type

class Project:
    def __init__(self, pid='', pn='', pd='', sh=[], sw=[], sz=3, author='',
                        timestamp=int(round(time.time() * 1000)), status=1):
        self.id = pid
        self.project_name = pn
        self.project_desc = pd
        self.skills_have = sh
        self.skills_wanted = sw
        self.team_size = sz
        self.author = author
        self.timestamp = timestamp
        self.status = 1

#######################################################################################
#######################################################################################
#######################################################################################
                                    # SLACK #
#######################################################################################
#######################################################################################
#######################################################################################

MESSAGE_TYPE = 'desktop_notification'

def parse_slack_output(slack_rtm_output):
    """
        The Slack Real Time Messaging API is an events firehose.
        this parsing function returns None unless a message is
        directed at the Bot, based on its ID.
    """
    messages = []
    output_list = filter(lambda out: 'type' in out and out['type'] == MESSAGE_TYPE and AT_BOT in out['content'],
                         slack_rtm_output)
    for out in output_list:
        channel = out['subtitle']
        username, text = out['content'].split(':')
        timestamp = out['event_ts']
        _type = out['type']
        messages.append(Message(BOTNAME, username, channel, text, timestamp, _type))
    return messages

class SQL(Enum):
    EQL = 0
    IS = 1
    LIKE = 2
    BETWEEN = 3

#######################################################################################
#######################################################################################
#######################################################################################
                                # DATABASE #
#######################################################################################
#######################################################################################
#######################################################################################

KEYS = [key for key in Project().__dict__]
print(KEYS)
def execute(query):
    conn = SQL_CONN.cursor()
    conn.execute(query)
    SQL_CONN.commit()
    return conn

def gather(data):
    tuples = []
    for datum in data:
        tuples.append(dict([(x, y) for x, y in zip(KEYS, datum)]))
    return tuples

def create_tables():
    table_create = "CREATE TABLE IF NOT EXISTS projects("
    fields = {
        'id': 'CHAR(5)',
        'project_name': 'VARCHAR(500)',
        'project_desc': 'VARCHAR(3000)',
        'author': 'VARCHAR(300)',
        'skills_have': 'VARCHAR(1000)',
        'skills_wanted': 'VARCHAR(1000)',
        'team_size': 'INTEGER',
        'timestamp': 'FLOAT',
        'status': 'INTEGER'
    }

    table_create += ','.join(['%s %s' % (k, t) for k, t in fields.items()]) + ',PRIMARY KEY (id));'
    print("EXECUTING", table_create)
    print()
    execute(table_create)

#### DATABASE QUERY ####
def query_projects(queries, keys=['*']):
    conn = SQL_CONN.cursor()
    query_params = []
    for k,v in queries.items():
        key = k
        select_type, select_query = v
        select = '='
        if select_type == SQL.IS:
            select = 'IS'
        elif select_type == SQL.LIKE:
            select = 'LIKE'
        elif select_type == SQL.BETWEEN:
            select = 'BETWEEN'
            select_query = '%d AND %d' % (select_query[0], select_query[1])
        query_params.append('%s %s "%s"' % (key, select, select_query))
    query_str = ' AND '.join(query_params)
    keys = ','.join(KEYS)
    sql_query = 'SELECT %s FROM %s WHERE %s' % (keys, PROJECT_TABLE_NAME, query_str)
    print(sql_query)
    conn.execute(sql_query)
    SQL_CONN.commit()
    return gather(conn.fetchall())
    
def get_all_projects():
    conn = execute('SELECT %s FROM %s' % (','.join(KEYS), PROJECT_TABLE_NAME))
    return gather(conn.fetchall())

def get_project_by_id(proj_id):
    return query_projects({'id': (SQL.EQL, proj_id)})

def get_project_by_name(proj_name):
    return query_projects({'project_name': (SQL.EQL, proj_name)})

def get_project_by_user(username):
    return query_projects({'author': (SQL.EQL, username)})

def get_project_by_needed_skill(skills):
    skill_str = '%%' + '%%'.join(skills) + '%%'
    return query_projects({'skills_wanted': (SQL.LIKE, skill_str)})

def get_project_by_skill(skills):
    skill_str = '%%' + '%%'.join(skills) + '%%'
    return query_projects({'skills_have': (SQL.LIKE, skill_str)})

def get_project_from_timerange(stime, etime):
    return query_projects({'timestamp': (SQL.BETWEEN, (stime, etime))})

def insert_project(proj):
    keys, values = [], []
    for k,v in proj.__dict__.items():
        keys.append(k)
        if isinstance(v, str):
            values.append('"%s"' % v)
        else:
            values.append(str(v))
    keys_str = ', '.join(keys)
    values_str = ', '.join(values)
    sql_insert = 'INSERT INTO %s (%s) VALUES (%s)' % (PROJECT_TABLE_NAME, keys_str, values_str)
    execute(sql_insert)

def generate_project_id():
    while True:
        _id = ''.join([chr(ord('A') + rnd.randint(0, 25)) for x in range(PROJECT_PRIMARY_KEY_SIZE)])
        if not get_project_by_id(_id):
            return _id

#######################################################################################
#######################################################################################
#######################################################################################
                            # COMMAND PROCESSING #
#######################################################################################
#######################################################################################
#######################################################################################

# Processes the post into proper format so it can be inserted into SQLite3
def process_posting(msg):
    posting = [w.strip() for w in re.split('\s+', msg.text)][1:] # eliminates that @ reference
    project = Project()
    info = {}
    curr_key = None
    arg_pattern = re.compile('^-[a-z]{2}$')
    # iterates over text, and if it encounters arg_pattern, updates curr_key and append all text to that kv-pair
    # in info
    for w in posting:
        if arg_pattern.match(w):
            arg = w[1:]
            if not curr_key or arg != curr_key:
                curr_key = arg
            if curr_key not in info:
                info[curr_key] = []
        elif curr_key != None:
            info[curr_key].append(w)
    # refining data
    if 'sh' in info:
        info['sh'] = [w.strip() for w in tools.flatten([re.split(',|;', skill.strip()) for skill in info['sh']]) if w]
    if 'sw' in info:
        info['sw'] = [w.strip() for w in tools.flatten([re.split(',|;', skill.strip()) for skill in info['sw']]) if w]
    # if key is in dictionary, return dictionary[key], else return default value
    if_in_else = lambda k, d, dv: d[k] if k in d else dv # k: key, d: dictionary, dv: default value
    # inflating project
    if 'pn' not in info:
        return (400, 'Please specify a project name. Use @letsmake help to see usage.')
    if 'pd' not in info:
        return (400, 'Please specify a project description. Use @letsmake help to see usage.')
    project.project_name = ' '.join(info['pn']) if 'pn' in info else project.project_name
    project.project_desc = ' '.join(info['pd']) if 'pd' in info else project.project_desc
    project.skills_have = '|'.join(info['sh']) if 'sh' in info else ''
    project.skills_wanted = '|'.join(info['sw']) if 'sw' in info else ''
    project.team_size = int(info['sz'][0]) if 'sz' in info else 3
    project.id = generate_project_id()
    project.author = msg.username
    insert_project(project)

# Lists projects according to user specification
def list_projects(msg):
    posting = [w.strip() for w in re.split('\s+', msg.text)][2:] # elimintes '@letsmake list-projects' string
    arg_pattern = re.compile('^-(a|m|q|s)$')
    info = {}
    criteria = []
    curr_key = None
    for w in posting:
        if arg_pattern.match(w):    
            arg = w[1]
            if not curr_key or arg != curr_key:
                curr_key = arg
            if curr_key not in info:
                info[curr_key] = []
        elif curr_key != None:
            info[curr_key].append(w)
    # RESULT ORDERING
    ordering = None
    invert_order = 'ASC'
    if not 'a' in info:
        criteria.append('status = 1')
    if 'm' in info:
        criteria.append('author = "%s"' % msg.username)
    if 's' in info:
        order_type = info['s'][0][0]
        if order_type == 'o':
            ordering = 'status'
        elif order_type == 'u':
            ordering = 'author'
        elif order_type == 't':
            ordering = 'timestamp'
        elif order_type == 'a':
            ordering = 'project_name'
        if len(info['s'][0]) == 2 and info['s'][0][1] == 'i':
            invert_order = 'DESC'
    if 'q' in info:
        qs = info['q'][1:]
        search_keys = {}
        curr_key = None
        q_pattern = re.compile('^[a-z]{2}:.+')
        for q in qs:
            if q_pattern.match(q):
                arg = q[:2] # xx:yyyy, only gets xx
                rem = q[3:] # xx:yyyy, gets yyyy
                if not curr_key or arg != curr_key:
                    curr_key = arg
                if curr_key not in search_keys:
                    search_keys[curr_key] = []
                search_keys[curr_key].append(rem)
            elif curr_key != None:
                search_keys[curr_key].append(w)
        for k, v in search_keys.items():
            if k == 'au':
                criteria.append('author LIKE %%%s%%' % '%'.join(v))
            elif k == 'tu':
                deltaT = 1000 * 3600 * int(v[0])
                target = int(time.time() * 1000) - deltaT
                criteria.append('timestamp >= %d' % deltaT)
            elif k == 'pn':
                criteria.append('project_name LIKE %%%s%%' % '%'.join(v))
            elif k == 'sh':
                criteria.append('skills_have LIKE %%%s%%' % '%'.join(v))
            elif k == 'sw':
                criteria.append('skills_wnated LIKE %%%s%%' % '%'.join(v))
            elif k == 'sl':
                cnt = int(v[0])
                critiera.append('team_size <= %d' % cnt)
            elif k == 'sg':
                criteria.append('team_size >= %d' % cnt)
    filter_query = ' AND '.join(criteria)
    sql_query = 'SELECT %s FROM %s WHERE %s %s' % (
                ','.join(KEYS), PROJECT_TABLE_NAME,
                filter_query, '%s %s' % (ordering, invert_order) if ordering else '')
    print(sql_query)

def show_project_statuses(msg):
    pass

# Handles commands given by the user
def central_dispatch(msg):
    cmd = re.split('\s+', msg.text)[1]
    if cmd == 'list-projects':
        list_projects(msg)
    elif cmd == 'status':
        show_project_statuses(msg)
    else:
        process_posting(msg)

#sends message to a channel
if __name__ == "__main__":
    create_tables()
    READ_WEBSOCKET_DELAY = 1 # 1 second delay between reading from firehose
    print(get_all_projects())
    if slack_client.rtm_connect():
        print("StarterBot connected and running!")
        while True:
            messages = parse_slack_output(slack_client.rtm_read())
            for msg in messages:
                central_dispatch(msg)
    else:
        print("Connection failed. Invalid Slack token or bot ID?")
