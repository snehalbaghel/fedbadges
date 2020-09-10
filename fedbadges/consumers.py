# -*- coding; utf-8 -*-
""" Consumers for producing openbadges by listening for messages on fedmsg

Authors:  Ross Delinger
          Ralph Bean
"""

import os.path
import yaml
import traceback
import transaction
import threading
import time

import datanommer.models
from fedora_messaging.config import conf


from badgrclient import BadgrClient, Assertion, BadgeClass
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker, scoped_session
from zope.sqlalchemy import ZopeTransactionExtension

import fedbadges.rules
import fedbadges.utils

import logging
log = logging.getLogger("fedora-messaging.fedbages")

BADGR_SCOPE = 'rw:profile rw:issuer rw:backpack'

class FedoraBadgesConsumer(object):

    def __init__(self):
        self.badge_rules = []
        self.config = conf["consumer_config"]


        # super(FedoraBadgesConsumer, self).__init__(hub)

        # self.consume_delay = int(self.hub.config.get('badges.consume_delay',
        #                                              self.consume_delay))
        # self.delay_limit = int(self.hub.config.get('badges.delay_limit',
        #                                            self.delay_limit))

        # Five things need doing at start up time
        # 0) Set up a request local to hang thread-safe db sessions on.
        # 1) Initialize our connection to the tahrir DB and perform some
        #    administrivia.
        # 2) Initialize our connection to the datanommer DB.
        # 3) Load our badge definitions and rules from YAML.
        # 4) Initialize fedmsg so that those listening to us can handshake.

        # Thread-local stuff
        self.l = threading.local()

        # Badgr stuff
        self._initalize_badgr_connection()

        # Datanommer stuff
        self._initialize_datanommer_connection()

        # Load badge definitions
        directory = self.config.get("badges_yaml_directory")
        self.badge_rules = self._load_badges_from_yaml(directory)

    def _initalize_badgr_connection(self):
        badgr_user = self.config.get('badgr_user')

        required = frozenset(['username', 'password', 'client_id',
            'base_url'])

        argued_fields = frozenset(badgr_user.keys())
        
        if not required.issubset(argued_fields):
            raise ValueError('BadgrClient requires: {}, \
                missing: {}'.format(required, required.difference(argued_fields)))

        username = badgr_user.get('username')
        password = badgr_user.get('password')
        client_id = badgr_user.get('client_id')
        base_url = badgr_user.get('base_url')

        self.l.badgr_client = BadgrClient(
            username=username,
            password=password,
            client_id=client_id,
            scope=BADGR_SCOPE,
            base_url=base_url,
            unique_badge_names=True
        )

        issuer = self.config.get('badge_issuer')

        issuer_eid = issuer.get('entity_id')

        if (issuer_eid):
            self.issuer_id = issuer_eid
        else:
            # TODO: create issuer
            pass

        if self.issuer_id:
            self.l.badgr_client.load_badge_names(self.issuer_id)
        else:
            # TODO: throw an exception?
            pass

    def _initialize_datanommer_connection(self):
        datanommer.models.init(self.config.get("datanommer_sqlalchemy_url"))

    def _load_badges_from_yaml(self, directory):
        # badges indexed by trigger
        badges = []
        directory = os.path.abspath(directory)
        log.info("Looking in %r to load badge definitions" % directory)
        for root, dirs, files in os.walk(directory):
            for partial_fname in files:
                fname = root + "/" + partial_fname
                badge = self._load_badge_from_yaml(fname)

                if not badge:
                    continue

                try:
                    badge_rule = fedbadges.rules.BadgeRule(
                        badge, self.l.badgr_client, self.issuer_id)
                    badges.append(badge_rule)
                except ValueError as e:
                    log.error("Initializing rule for %r failed with %r" % (
                        fname, e))

        log.info("Loaded %i total badge definitions" % len(badges))
        return badges

    def _load_badge_from_yaml(self, fname):
        log.debug("Loading %r" % fname)
        try:
            with open(fname, 'r') as f:
                return yaml.load(f.read())
        except Exception as e:
            log.error("Loading %r failed with %r" % (fname, e))
            return None

    def award_badge(self, username, badge_rule, link=None):
        """ A high level way to issue a badge to a Person.

        It adds the person if they don't exist, and creates an assertion for
        them.

        :type username: str
        :param username: This person's username.

        :type badge_rule: object
        :param badge_rule: the badge_rule that triggered this.
        """

        log.info("Awarding badge %r to %r" % (badge_rule.badge_id, username))
        email = "%s@fedoraproject.org" % username
        client = badge_rule.client

        # Check if the recipient already has been awarded
        badge_to_award = BadgeClass(client, eid=badge_rule.badge_id)
        badge_to_award.issue(recipient_email=email)

        # try:
            # transaction.begin()
            # self.l.tahrir.add_assertion(badge_rule.badge_id, email, None, link)
            # transaction.commit()
        # except IntegrityError:
        # TODO: How?
            # Here we handle two different kinds of errors due to the existence
            # of a somewhat harmless race condition.
            # Say that someone adds 2 tags to a package in fedora-tagger all at
            # once.  That produces 2 different fedmsg messages that each hit
            # this daemon.  Each message gets handed off to each of 2 worker
            # threads that start working in parallel.  They both ask, does
            # person X have the 'Awesome Tagger' badge?  The database responds
            # "no", so they both start checking to see if the person meets all
            # the criteria.  They do, so the first worker gets here and awards
            # them the badge with add_assertion.  The second thread gets here
            # and tries to award the badge, but it is already awarded by the
            # other thread -- so it raises a 'duplicate primary key'
            # IntegrityError.  We catch that here, and note it in the logs as a
            # warning not an error.  It happens often enough and is harmless
            # enough that we don't want to receive emails about it.
            # transaction.abort()
            # self.l.tahrir.session.rollback()
            # log.warn(traceback.format_exc())
        # except:
            # For all other errors, we rollback the transaction but we also
            # re-raise the error so that it hits the fedmsg handling in the
            # stack above and emails us about it.
            # transaction.abort()
            # self.l.tahrir.session.rollback()
            # raise

    def __call__(self, msg):

        # First thing, we receive the message, but we put ourselves to sleep to
        # wait for a moment.  The reason for this is that, when things are
        # 'calm' on the bus, we receive messages "too fast".  A message that
        # arrives to the badge awarder triggers (usually) a check against
        # datanommer to count messages.  But if we try to count them before
        # this message arrives at datanommer, we'll get skewed results!  Race
        # condition.  We go to sleep to allow ample time for datanommer to
        # consume this one before we go and start doing checks on it.  When
        # fedbadges was first released, this was absolutely necessary.
        # Since that time, the fedmsg bus has become much more congested.  So,
        # to improve our average speed at handling messages, we only do that
        # sleep statement if we're not already backlogged.  If we know we have
        # a huge workload ahead of us, then go ahead and start handling
        # messages as fast as we can.
        if self.incoming.qsize() < self.delay_limit:
            time.sleep(self.consume_delay)

        # Strip the moksha envelope
        msg = msg['body']

        default = "https://apps.fedoraproject.org/datagrepper"
        link = self.config.get('fedbadges_datagrepper_url', default) + \
            "/id?id=%s&is_raw=true&size=extra-large" % msg['msg_id']

        # Define this so we can refer to it in error handling below
        badge_rule = None

        # Initialize our connection if this is the first time we are called.
        self._initialize_tahrir_connection()

        # Award every badge as appropriate.
        log.debug("Received %s, %s" % (msg['topic'], msg['msg_id']))
        for badge_rule in self.badge_rules:
            try:
                for recipient in badge_rule.matches(msg):
                    self.award_badge(recipient, badge_rule, link)
            except Exception as e:
                log.exception("Rule: %r, message: %r" % (badge_rule, msg))

        log.debug("Done with %s, %s" % (msg['topic'], msg['msg_id']))
