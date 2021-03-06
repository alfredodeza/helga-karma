import mock
import mongomock

# DO NOT import KarmaPlugin directly -- it will import helga.db,
# and attempt to connect to MongoDB.
#from helga_karma.plugin import KarmaPlugin


class TestKarmaPlugin(object):

    def setup(self):
        from _pytest.monkeypatch import monkeypatch
        patch = monkeypatch()
        patch.setattr('pymongo.MongoClient', mongomock.MongoClient)

        from helga_karma import plugin
        self.plugin = plugin

    def test_give_handles_arrogance(self):
        ret = self.plugin.give('foo', ['foo'])
        assert ret == "Uhh, do you want a gold star, foo?"

    def test_give(self):
        with mock.patch.object(self.plugin, 'KarmaRecord') as db:
            from_user = mock.Mock()
            to_user = mock.Mock()
            db.get_for_nick.side_effect = [from_user, to_user]

            self.plugin.give('foo', ['bar'])

            from_user.give_karma_to.assert_called_with(to_user)

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
            user2.add_alias.assert_called_with(user1)

    def test_alias(self):
        with mock.patch.object(self.plugin, 'KarmaRecord') as db:
            user1 = mock.Mock(nick='foo', value=1)
            user2 = mock.Mock(nick='bar', value=1)

            getter = lambda s, k: getattr(s, k)
            user1.__getitem__ = getter
            user2.__getitem__ = getter

            db.get_for_nick.side_effect = [user1, user2]

            self.plugin.alias('me', 'foo', 'bar')
            user1.add_alias.assert_called_with(user2)

    def test_unalias_nope_with_same_nick(self):
        with mock.patch.object(self.plugin, 'KarmaRecord') as db:
            db.get_for_nick.side_effect = [
                {'nick': 'foo'},
                {'nick': 'foo'},
            ]

            retval = self.plugin.unalias('me', 'foo', 'foo')
            assert retval == "That doesn't make much sense now, does it, me."

    def test_unalias_no_records(self):
        with mock.patch.object(self.plugin, 'KarmaRecord') as db:
            db.get_for_nick.side_effect = [None, None]
            retval = self.plugin.unalias('me', 'foo', 'bar')
            assert retval == "Neither of the users you specified appear to exist, me."

    def test_unalias_non_linked_users(self):
        with mock.patch.object(self.plugin, 'KarmaRecord') as db:
            user1 = mock.Mock()
            user2 = mock.Mock()

            user2.get_aliases.return_value = ['bar']

            db.get_for_nick.side_effect = [user1, user2]

            retval = self.plugin.unalias('me', 'foo', 'bar')
            assert retval == "foo and bar are not linked."

    def test_unalias(self):
        with mock.patch.object(self.plugin, 'KarmaRecord') as db:
            user2 = mock.Mock()

            user2.get_aliases.return_value = ['bar']

            db.get_for_nick.side_effect = [None, user2]

            self.plugin.unalias(requested_by='me', nick1='bar', nick2='foo')

            user2.remove_alias.assert_called_with('bar')

    @mock.patch('helga_karma.plugin.settings')
    def test_message_not_overridden(self, settings):
        overridden_message = 'info_standard'
        not_overridden_message = 'linked'

        settings.KARMA_MESSAGE_OVERRIDES = {
            overridden_message: "Arbitrary Message"
        }
        from helga_karma.plugin import format_message, MESSAGES

        kwargs = {'main': 'foo', 'secondary': 'bar'}

        result = format_message(not_overridden_message, **kwargs)
        expected = MESSAGES[not_overridden_message].format(**kwargs)

        assert result == expected

    @mock.patch('helga_karma.plugin.settings')
    def test_message_karma_overridden(self, settings):
        overridden_message = 'info_standard'

        settings.KARMA_MESSAGE_OVERRIDES = {
            overridden_message: "Arbitrary Message"
        }
        from helga_karma.plugin import format_message

        result = format_message(overridden_message)
        expected = settings.KARMA_MESSAGE_OVERRIDES[overridden_message]
        assert result == expected

    def test_autokarma_match(self):
        matcher = self.plugin._autokarma_match

        assert ['helga'] == matcher('thanks, helga')
        assert ['helga'] == matcher('TYVM helga!')
        assert ['helga'] == matcher('ty helga. i needed that reminder')

        assert not matcher('i appreciate it helga')


class TestPlusPlusSupport(TestKarmaPlugin):

    def test_autokarma_match_nick_alone(self):
        matcher = self.plugin._autokarma_match
        assert ['helga++'] == matcher('helga++')

    def test_autokarma_match_nick_leading_whitespace(self):
        matcher = self.plugin._autokarma_match
        assert ['helga++'] == matcher(' helga++')

    def test_autokarma_match_leading_text_matches(self):
        matcher = self.plugin._autokarma_match
        assert ['helga++'] == matcher('you are doing great helga++')

    def test_autokarma_match_trailing_text_matches(self):
        matcher = self.plugin._autokarma_match
        assert ['helga++'] == matcher('you are doing great helga++ fantastic job there')

    def test_autokarma_match_trailing_comma_matches(self):
        matcher = self.plugin._autokarma_match
        assert ['helga++'] == matcher('helga++, way to go')

    def test_autokarma_no_match_trailing_garbage(self):
        matcher = self.plugin._autokarma_match
        assert matcher('helga++burrrr') == []

    def test_autokarma_no_match_cpp(self):
        matcher = self.plugin._autokarma_match
        assert matcher('I love programming in C++') == []

    def test_autokarma_multiple_matches(self):
        matcher = self.plugin._autokarma_match
        result = matcher('go team helga++ andrewschoen++ yuriw++')
        assert 'helga++' == result[0]
        assert 'andrewschoen++' == result[1]
        assert 'yuriw++' == result[2]


class TestInvalidWords(TestKarmaPlugin):
    # if py.test fixtures get used, they should be in place for these
    # tests to get all combinations of `thanks` that the plugin supports
    def test_default_for_does_not_match(self):
        matcher = self.plugin._autokarma_match
        assert matcher('thanks for helping out') is None

    def test_default_i_does_not_match(self):
        matcher = self.plugin._autokarma_match
        assert matcher('thanks I was able to fix it') is None
