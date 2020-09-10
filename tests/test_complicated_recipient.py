import unittest
import logging

import tahrir_api.dbapi
import fedbadges.consumers

from mock import patch, Mock
from nose.tools import eq_

from StringIO import StringIO

# Utils for tests
import utils


class TestComplicatedRecipient(unittest.TestCase):

    @patch('tahrir_api.dbapi.TahrirDatabase.add_issuer')
    @patch('tahrir_api.dbapi.TahrirDatabase.add_badge')
    def setUp(self, add_issuer, add_badge):
        self.consumer = fedbadges.consumers.FedoraBadgesConsumer()

    @patch('datanommer.models.Message.grep')
    @patch('tahrir_api.dbapi.TahrirDatabase.get_person')
    @patch('tahrir_api.dbapi.TahrirDatabase.assertion_exists')
    def test_complicated_recipient_real(self,
                                        assertion_exists,
                                        get_person,
                                        grep,
                                        ):

        for rule in self.consumer.badge_rules:
            if rule['name'] == 'Speak Up!':
                self.rule = rule
        msg = {
            u'username': u'daemon',
            u'i': 236,
            u'timestamp': 1372103541.190249,
            u'topic': u'org.fedoraproject.prod.meetbot.meeting.complete',
            u'msg': {
                u'meeting_topic': u'testing',
                u'attendees': {u'zodbot': 2,
                               u'threebean': 2},
                u'chairs': {},
                u'topic': u'',
                u'url': u'fedora-meeting.2013-06-24-19.52',
                u'owner': u'threebean',
                u'channel': u'#fedora-meeting'
            }
        }

        # Set up some mock stuff
        class MockQuery(object):
            def count(self):
                return float("inf")  # Master tagger

        class MockPerson(object):
            opt_out = False

        grep.return_value = float("inf"), 1, MockQuery()
        get_person.return_value = MockPerson()
        assertion_exists.return_value = False

        with patch("fedbadges.rules.user_exists_in_fas") as g:
            g.return_value = True
            eq_(self.rule.matches(msg), set(['zodbot', 'threebean']))


    @patch('datanommer.models.Message.grep')
    @patch('tahrir_api.dbapi.TahrirDatabase.get_person')
    @patch('tahrir_api.dbapi.TahrirDatabase.assertion_exists')
    def test_complicated_recipient_pagure(self,
                                        assertion_exists,
                                        get_person,
                                        grep,
                                        ):

        for rule in self.consumer.badge_rules:
            if rule['name'] == 'Long Life to Pagure (Pagure I)':
                self.rule = rule
        msg = {
                "username": "git",
                "source_name": "datanommer",
                "i": 1,
                "timestamp": 1528825180.0,
                "topic": "io.pagure.prod.pagure.git.receive",
                "msg": {
                    "authors": [
                        {
                            "fullname": "Pierre-YvesChibon",
                            "name": "pingou"
                        },
                        {
                            "fullname": "Lubom\u00edr Sedl\u00e1\u0159",
                            "name": "lsedlar"
                        }
                        ],
                        "total_commits": 2,
                        "start_commit": "da090b8449237e3878d4d1fe56f7f8fcfd13a248"
                    }
            }

        # Set up some mock stuff
        class MockQuery(object):
            def count(self):
                return float("inf")  # Master tagger

        class MockPerson(object):
            opt_out = False

        grep.return_value = float("inf"), 1, MockQuery()
        get_person.return_value = MockPerson()
        assertion_exists.return_value = False

        with patch("fedbadges.rules.user_exists_in_fas") as g:
            g.return_value = True
            eq_(self.rule.matches(msg), set(['pingou', 'lsedlar']))

    @patch('datanommer.models.Message.grep')
    @patch('tahrir_api.dbapi.TahrirDatabase.get_person')
    @patch('tahrir_api.dbapi.TahrirDatabase.assertion_exists')
    def test_complicated_recipient_pagure_bad(self,
                                        assertion_exists,
                                        get_person,
                                        grep,
                                        ):

        for rule in self.consumer.badge_rules:
            if rule['name'] == 'Long Life to Pagure (Pagure I)':
                self.rule = rule
        msg = {
                "username": "git",
                "source_name": "datanommer",
                "i": 1,
                "timestamp": 1528825180.0,
                "topic": "io.pagure.prod.pagure.git.receive",
                "msg": {
                    "authors": [
                        {
                            "fullname": "Pierre-YvesChibon",
                        },
                        {
                            "fullname": "Lubom\u00edr Sedl\u00e1\u0159",
                        }
                        ],
                        "total_commits": 2,
                        "start_commit": "da090b8449237e3878d4d1fe56f7f8fcfd13a248"
                    }
            }

        # Set up some mock stuff
        class MockQuery(object):
            def count(self):
                return float("inf")  # Master tagger

        class MockPerson(object):
            opt_out = False

        grep.return_value = float("inf"), 1, MockQuery()
        get_person.return_value = MockPerson()
        assertion_exists.return_value = False

        with patch("fedbadges.rules.user_exists_in_fas") as g:
            g.return_value = True
            self.assertRaises(Exception("Multiple recipients : name not found in the message"))
