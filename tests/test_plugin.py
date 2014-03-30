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

    def test_top(self):
        with mock.patch.object(self.plugin, 'KarmaRecord') as db:
            getitem = lambda s, k: getattr(s, k)
            users = [
                mock.Mock(nick='foo', get_value=lambda: 1, __getitem__=getitem),
                mock.Mock(nick='bar', get_value=lambda: 2, __getitem__=getitem),
                mock.Mock(nick='baz', get_value=lambda: 3, __getitem__=getitem),
            ]
            db.get_top.return_value = users
            ret = self.plugin.top()

            assert ret[0] == '#1: foo (1.0 karma)'
            assert ret[1] == '#2: bar (2.0 karma)'
            assert ret[2] == '#3: baz (3.0 karma)'

    def test_info_no_previous_karma(self):
        with mock.patch.object(self.plugin, 'KarmaRecord') as db:
            record = mock.Mock()
            record.get_value.return_value = None
            db.get_for_nick.return_value = record

            retval = self.plugin.info('me', 'foo')
            assert retval == "I'm not aware of foo having done anything helpful, me."

    def test_info_detailed(self):
        with mock.patch.object(self.plugin, 'KarmaRecord') as db:
            record = mock.Mock(nick='foo', given=1, received=2)
            record.__getitem__ = lambda s, k: getattr(s, k)
            record.get_value.return_value = 3
            record.get_coefficient.return_value = 4
            record.get_aliases.return_value = ['bar', 'baz']
            db.get_for_nick.return_value = record

            retval = self.plugin.info('me', 'foo', detailed=True)
            expected = ('foo has 3.0 karma. (thanked others 1 times, '
                        'received thanks 2 times, karma coefficient 4.0, '
                        'aliases: bar, baz)')
            assert retval == expected

    def test_info(self):
        with mock.patch.object(self.plugin, 'KarmaRecord') as db:
            record = mock.Mock()
            record.get_value.return_value = 1
            db.get_for_nick.return_value = record

            retval = self.plugin.info('me', 'foo')
            expected = 'foo has about 1 karma, me.'
            assert retval == expected

    def test_alias_nope_with_same_nick(self):
        with mock.patch.object(self.plugin, 'KarmaRecord') as db:
            db.get_for_nick.side_effect = [
                {'nick': 'foo'},
                {'nick': 'foo'},
            ]

            retval = self.plugin.alias('me', 'foo', 'foo')
            assert retval == "That doesn't make much sense now, does it, me."

    def test_alias_prefers_user_with_highest_value(self):
        with mock.patch.object(self.plugin, 'KarmaRecord') as db:
            user1 = mock.Mock(nick='foo', value=1)
            user2 = mock.Mock(nick='bar', value=5)

            getter = lambda s, k: getattr(s, k)
            user1.__getitem__ = getter
            user2.__getitem__ = getter

            db.get_for_nick.side_effect = [user1, user2]

            self.plugin.alias('me', 'foo', 'bar')
            user2.add_alias.assertCalledWith(user1)

    def test_alias(self):
        with mock.patch.object(self.plugin, 'KarmaRecord') as db:
            user1 = mock.Mock(nick='foo', value=1)
            user2 = mock.Mock(nick='bar', value=1)

            getter = lambda s, k: getattr(s, k)
            user1.__getitem__ = getter
            user2.__getitem__ = getter

            db.get_for_nick.side_effect = [user1, user2]

            self.plugin.alias('me', 'foo', 'bar')
            user1.add_alias.assertCalledWith(user2)


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
