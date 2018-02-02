""" Shared Testing Utilities """

import os
import inspect
from datetime import datetime, timedelta
from unittest.mock import Mock

import flask
from flask_testing import TestCase

import slackru.util
from slackru import get_db
from slackru.util.slackapi import SlackAPI


data = dict()
data['mentor'] = ['Bryan Bugyi', 'Timmy Tester']
data['mentorname'] = ['bryan.bugyi', 'tester.timmy']
data['mentorid'] = ['U86U3G52Q', 'U8R4CCDV4']
data['username'] = ['bryanbugyi34']
data['userid'] = ['U8LRL4L5R']
data['channel'] = ['D86QQ6P2P', 'D8RAAMGJ3']
data['question'] = ['I am having some trouble with my Python code.', 'I love JAVA', 'I hate C++!']


def side_effect(action, *args, **kwargs):
    return {'channel': {'id': 'CHANNEL_ID'},
            'ts': 'TIMESTAMP',
            'ok': True}


slack_client = Mock()
slack_client.api_call = Mock(side_effect=side_effect)
slackru.util.slack = SlackAPI(slack_client)


def params(*parameters):
    """ Example Usage:

            @params((1,2,3), (2,4,6), (5,6,11))
            def test_add(self, x, y, z):
                self.assertEqual(add(x,y), z)

        The above example will run 3 tests total, one for each of the following paramenter
        assignments: x=1, y=2, z=3; x=2, y=4, z=6; and x=5, y=6, z=11.
    """
    def decorator(func):
        def wrapper(self):
            funcArgNames = inspect.getfullargspec(func).args[1:]
            for args in parameters:
                with self.subTest(**dict(zip(funcArgNames, args))):
                    func(self, *args)
        return wrapper
    return decorator


class TestBase(TestCase):
    """ Base Unit Testing Class. Inherited by all other test classes. """
    @classmethod
    def setUpClass(cls):
        cls.db = get_db()

        # A hack to enable tests to run certain commands only once per SESSION
        # instead of once per CLASS
        if not os.getenv('SLACKRU_TEST_SESSION'):
            os.environ['SLACKRU_TEST_SESSION'] = 'True'
            from slackru.config import config
            flask.testing = True
            config.setup()

            cls.db.drop_all()
            cls.db.create_all()

            start_time = datetime.now().strftime('%Y-%m-%d %H:%M')
            end_time = (datetime.now() + timedelta(days=365)).strftime('%Y-%m-%d %H:%M')
            cls.db.insertMentor(data['mentor'][0], data['mentorname'][0], data['mentorid'][0], "Python")
            cls.db.insertMentor(data['mentor'][1], data['mentorname'][1], data['mentorid'][1], "Java")
            cls.db.insertShift(data['mentorid'][0], start_time, end_time)
            cls.db.insertShift(data['mentorid'][1], start_time, end_time)

    def create_app(self):
        """ Used by Flask-Testing package to create app context """
        from slackru import create_app
        app = create_app()
        app.config['TESTING'] = True
        return app
