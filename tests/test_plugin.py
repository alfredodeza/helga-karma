from unittest import TestCase

import mock
import mongomock

# DO NOT import KarmaPlugin directly -- it will import helga.db,
# and attempt to connect to MongoDB.
#from helga_karma.plugin import KarmaPlugin


class TestNewStylePlugin(TestCase):
    # Temporary home for tests of the new-style @command plugin

    def setUp(self):
        self.db_patch = mock.patch(
            'pymongo.MongoClient',
            new_callable=lambda: mongomock.Connection
        )
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)

        from helga_karma import plugin
        self.plugin = plugin

    def test_give_handles_arrogance(self):
        ret = self.plugin.give('foo', 'foo')
        assert ret == "Uhh, do you want a gold star, foo?"

    def test_give(self):
        with mock.patch.object(self.plugin, 'KarmaRecord') as db:
            from_user = mock.Mock()
            to_user = mock.Mock()
            db.get_for_nick.side_effect = [from_user, to_user]

            from_user.give_karma_to.assertCalledWith(to_user)


class TestKarmaPlugin(TestCase):
    def setUp(self):
        super(TestKarmaPlugin, self).setUp()

        self.db_patch = mock.patch(
            'pymongo.MongoClient',
            new_callable=lambda: mongomock.Connection
        )
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)

        from helga_karma.plugin import KarmaPlugin
        from helga.db import db
        self.db = db
        self.client = None
        self.channel = None
        self.nick = 'arbitrary_nick'
        self.plugin = KarmaPlugin()

    def test_underscored_nick_matches_info(self):
        message = '!karma somebody_underscored'

        with mock.patch.object(self.plugin, 'run') as run:
            self.plugin.process(self.client, self.channel, self.nick, message)

            run.assert_called_with(
                self.channel,
                self.nick,
                message,
                self.plugin.info,
                {
                    'detailed': None,
                    'nick': 'somebody_underscored'
                }
            )

    def test_dashed_nick_matches_info(self):
        message = '!karma somebody-dashed'

        with mock.patch.object(self.plugin, 'run') as run:
            self.plugin.process(self.client, self.channel, self.nick, message)

            run.assert_called_with(
                self.channel,
                self.nick,
                message,
                self.plugin.info,
                {
                    'detailed': None,
                    'nick': 'somebody-dashed'
                }
            )

    def test_piped_nick_matches_info(self):
        message = '!karma somebody|piped'

        with mock.patch.object(self.plugin, 'run') as run:
            self.plugin.process(self.client, self.channel, self.nick, message)

            run.assert_called_with(
                self.channel,
                self.nick,
                message,
                self.plugin.info,
                {
                    'detailed': None,
                    'nick': 'somebody|piped'
                }
            )

    def test_long_form_request_matches_nick(self):
        message = '!karma details for somebody'

        with mock.patch.object(self.plugin, 'run') as run:
            self.plugin.process(self.client, self.channel, self.nick, message)

            run.assert_called_with(
                self.channel,
                self.nick,
                message,
                self.plugin.info,
                {
                    'detailed': 'details',
                    'nick': 'somebody'
                }
            )

    def test_short_form_request_matches_nick(self):
        message = '!k'

        with mock.patch.object(self.plugin, 'run') as run:
            self.plugin.process(self.client, self.channel, self.nick, message)

            run.assert_called_with(
                self.channel,
                self.nick,
                message,
                self.plugin.info,
                {
                    'detailed': None,
                    'nick': None
                }
            )

    def test_top_match(self):
        message = '!karma top 10'

        with mock.patch.object(self.plugin, 'run') as run:
            self.plugin.process(self.client, self.channel, self.nick, message)

            run.assert_called_with(
                self.channel,
                self.nick,
                message,
                self.plugin.top,
                {
                    'count': '10'
                }
            )

    def test_link_spaces(self):
        message = '!karma usera == userb'

        with mock.patch.object(self.plugin, 'run') as run:
            self.plugin.process(self.client, self.channel, self.nick, message)

            run.assert_called_with(
                self.channel,
                self.nick,
                message,
                self.plugin.link,
                {
                    'usera': 'usera',
                    'userb': 'userb',
                }
            )

    def test_link_spaceless(self):
        message = '!karma usera==userb'

        with mock.patch.object(self.plugin, 'run') as run:
            self.plugin.process(self.client, self.channel, self.nick, message)

            run.assert_called_with(
                self.channel,
                self.nick,
                message,
                self.plugin.link,
                {
                    'usera': 'usera',
                    'userb': 'userb',
                }
            )

    def test_unlink_spaces(self):
        message = '!karma usera != userb'

        with mock.patch.object(self.plugin, 'run') as run:
            self.plugin.process(self.client, self.channel, self.nick, message)

            run.assert_called_with(
                self.channel,
                self.nick,
                message,
                self.plugin.unlink,
                {
                    'usera': 'usera',
                    'userb': 'userb',
                }
            )

    def test_unlink_spaceless(self):
        message = '!karma usera!=userb'

        with mock.patch.object(self.plugin, 'run') as run:
            self.plugin.process(self.client, self.channel, self.nick, message)

            run.assert_called_with(
                self.channel,
                self.nick,
                message,
                self.plugin.unlink,
                {
                    'usera': 'usera',
                    'userb': 'userb',
                }
            )

    def test_motivate(self):
        message = '!motivate somebody'

        with mock.patch.object(self.plugin, 'run') as run:
            self.plugin.process(self.client, self.channel, self.nick, message)

            run.assert_called_with(
                self.channel,
                self.nick,
                message,
                self.plugin.give,
                {
                    'nick': 'somebody',
                }
            )

    def test_motivate_short(self):
        message = '!m somebody'

        with mock.patch.object(self.plugin, 'run') as run:
            self.plugin.process(self.client, self.channel, self.nick, message)

            run.assert_called_with(
                self.channel,
                self.nick,
                message,
                self.plugin.give,
                {
                    'nick': 'somebody',
                }
            )

    def test_thanks(self):
        message = '!thanks somebody'

        with mock.patch.object(self.plugin, 'run') as run:
            self.plugin.process(self.client, self.channel, self.nick, message)

            run.assert_called_with(
                self.channel,
                self.nick,
                message,
                self.plugin.give,
                {
                    'nick': 'somebody',
                }
            )

    def test_thanks_short(self):
        message = '!t somebody'

        with mock.patch.object(self.plugin, 'run') as run:
            self.plugin.process(self.client, self.channel, self.nick, message)

            run.assert_called_with(
                self.channel,
                self.nick,
                message,
                self.plugin.give,
                {
                    'nick': 'somebody',
                }
            )
