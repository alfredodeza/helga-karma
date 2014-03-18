from unittest import TestCase

import mock
import mongomock


class TestKarmaPluginIntegration(TestCase):
    def setUp(self):
        super(TestKarmaPluginIntegration, self).setUp()

        self.db_patch = mock.patch(
            'pymongo.MongoClient',
            new_callable=lambda: mongomock.Connection
        )
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)

        from helga_karma.data import KarmaRecord
        from helga_karma.plugin import KarmaPlugin
        from helga.db import db
        self.KarmaRecord = KarmaRecord
        self.plugin = KarmaPlugin()
        self.db = db
        self.client = None
        self.channel = None
        self.nick = 'arbitrary_nick'

    def tearDown(self):
        self.db.karma_user.drop()
        self.db.karma_link.drop()

    def create_nick(self, nick, **kwargs):
        aliases = []
        if 'aliases' in kwargs:
            aliases = kwargs['aliases']
            kwargs.pop('aliases')
        kwargs.update({'nick': nick})
        self.db.karma_user.insert(kwargs)
        for alias in aliases:
            if isinstance(alias, basestring):
                record = {
                    'nick': alias,
                    'real_nick': nick,
                    'record': {
                        'nick': alias,
                        'given': 0,
                        'received': 0,
                        'value': 0,
                    },
                    'aliases': [],
                }
            else:
                record.update({'real_nick': nick})
            self.db.karma_link.insert(record)

    def test_info_no_karma(self):
        nick = 'alpha'
        nick_record = {
            'value': 0
        }
        self.create_nick(nick, **nick_record)
        message = '!k %s' % nick

        with mock.patch.object(self.plugin, 'format_message') as fmt_msg:
            self.plugin.process(self.client, self.channel, self.nick, message)
            fmt_msg.assert_called_with(
                'info_none',
                for_nick=nick,
                nick=self.nick,
            )

    def test_info_standard(self):
        nick = 'alpha'
        nick_record = {
            'value': 10.1
        }
        message = '!k %s' % nick
        self.create_nick(nick, **nick_record)

        with mock.patch.object(self.plugin, 'format_message') as fmt_msg:
            self.plugin.process(self.client, self.channel, self.nick, message)
            fmt_msg.assert_called_with(
                'info_standard',
                for_nick=nick,
                nick=self.nick,
                value=round(10.1),
            )

    def test_info_detailed(self):
        nick = 'alpha'
        nick_record = {
            'value': 10.1,
            'given': 10,
            'received': 5,
        }
        message = '!k details %s' % nick
        self.create_nick(nick, **nick_record)

        with mock.patch.object(self.plugin, 'format_message') as fmt_msg:
            self.plugin.process(
                self.client, self.channel, self.nick, message
            )
            fmt_msg.assert_called_with(
                'info_detailed',
                for_nick=nick,
                value=nick_record['value'],
                given=nick_record['given'],
                received=nick_record['received'],
                coefficient=(
                    float(nick_record['received'])/nick_record['given']
                ),
                aliases='none'
            )

    def test_link_self(self):
        nick = 'alpha'
        self.create_nick(nick)

        message = '!k %s==%s' % (
            nick,
            nick,
        )
        with mock.patch.object(self.plugin, 'format_message') as fmt_msg:
            self.plugin.process(
                self.client, self.channel, self.nick, message
            )
            fmt_msg.assert_called_with(
                'nope',
                nick=self.nick,
            )

    def test_link_does_not_exist(self):
        nick = 'alpha'
        nick_b = 'beta'

        message = '!k %s==%s' % (
            nick,
            nick_b,
        )
        with mock.patch.object(self.plugin, 'format_message') as fmt_msg:
            self.plugin.process(
                self.client, self.channel, self.nick, message
            )
            fmt_msg.assert_called_with(
                'unknown_user',
                for_nick=nick,
                nick=self.nick,
            )

    def test_link_linked_already(self):
        nick = 'alpha'
        nick_b = 'beta'

        self.create_nick(
            nick,
            aliases=[nick_b],
        )

        message = '!k %s==%s' % (
            nick,
            nick_b,
        )
        with mock.patch.object(self.plugin, 'format_message') as fmt_msg:
            self.plugin.process(
                self.client, self.channel, self.nick, message
            )
            fmt_msg.assert_called_with(
                'linked_already',
                main=nick,
                secondary=nick_b,
            )

    def test_link_linked_ok(self):
        nick = 'alpha'
        nick_b = 'beta'

        self.create_nick(nick)
        self.create_nick(nick_b)

        message = '!k %s==%s' % (
            nick,
            nick_b,
        )
        with mock.patch.object(self.plugin, 'format_message') as fmt_msg:
            self.plugin.process(
                self.client, self.channel, self.nick, message
            )
            fmt_msg.assert_called_with(
                'linked',
                main=nick,
                secondary=nick_b,
            )

    def test_unlink_self(self):
        nick = 'alpha'
        self.create_nick(nick)

        message = '!k %s!=%s' % (
            nick,
            nick,
        )
        with mock.patch.object(self.plugin, 'format_message') as fmt_msg:
            self.plugin.process(
                self.client, self.channel, self.nick, message
            )
            fmt_msg.assert_called_with(
                'nope',
                nick=self.nick,
            )

    def test_unlink_does_not_exist(self):
        nick = 'alpha'
        nick_b = 'beta'

        message = '!k %s!=%s' % (
            nick,
            nick_b,
        )
        with mock.patch.object(self.plugin, 'format_message') as fmt_msg:
            self.plugin.process(
                self.client, self.channel, self.nick, message
            )
            fmt_msg.assert_called_with(
                'unknown_user_many',
                nick=self.nick,
            )

    def test_unlink_not_linked(self):
        nick = 'alpha'
        nick_b = 'beta'
        self.create_nick(nick)

        message = '!k %s!=%s' % (
            nick,
            nick_b,
        )
        with mock.patch.object(self.plugin, 'format_message') as fmt_msg:
            self.plugin.process(
                self.client, self.channel, self.nick, message
            )
            fmt_msg.assert_called_with(
                'unlinked_not_linked',
                usera=nick,
                userb=nick_b
            )

    def test_unlink_ok(self):
        nick = 'alpha'
        nick_b = 'beta'
        self.create_nick(nick, aliases=[nick_b])

        message = '!k %s!=%s' % (
            nick,
            nick_b,
        )
        with mock.patch.object(self.plugin, 'format_message') as fmt_msg:
            self.plugin.process(
                self.client, self.channel, self.nick, message
            )
            fmt_msg.assert_called_with(
                'unlinked',
                usera=nick,
                userb=nick_b
            )

    def test_give_self(self):
        nick = self.nick

        message = '!m %s' % nick
        with mock.patch.object(self.plugin, 'format_message') as fmt_msg:
            self.plugin.process(
                self.client, self.channel, self.nick, message
            )
            fmt_msg.assert_called_with(
                'too_arrogant',
                nick=nick,
            )

    def test_give(self):
        nick = 'alpha'

        message = '!m %s' % nick
        with mock.patch.object(self.plugin, 'format_message') as fmt_msg:
            self.plugin.process(
                self.client, self.channel, self.nick, message
            )
            fmt_msg.assert_called_with(
                'good_job',
                nick=nick,
            )
