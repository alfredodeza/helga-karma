import datetime
import math
from unittest import TestCase

import mock
import mongomock

# DO NOT import KarmaRecord directly -- it will import helga.db,
# and attempt to connect to MongoDB.
#from helga_karma.data import KarmaRecord


class TestKarmaRecord(TestCase):
    def setUp(self):
        super(TestKarmaRecord, self).setUp()

        self.db_patch = mock.patch(
            'pymongo.MongoClient',
            new_callable=lambda: mongomock.Connection
        )
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)

        from helga_karma.data import KarmaRecord
        from helga.db import db
        self.KarmaRecord = KarmaRecord
        self.db = db

    def _get_karma_record(self, nick, **kwargs):
        record = self.KarmaRecord.get_for_nick(nick)
        for k, v in kwargs.items():
            record[k] = v
        record.save()
        return record

    def tearDown(self):
        self.db.karma_user.drop()
        self.db.karma_link.drop()

    def test_get_actual_nick(self):
        arbitrary_nick = 'one'
        arbitrary_alias = 'two'

        self.db.karma_link.insert(
            {
                'nick': arbitrary_alias,
                'real_nick': arbitrary_nick
            }
        )

        k = self.KarmaRecord({})
        actual_result = k.get_actual_nick(arbitrary_alias)
        expected_result = arbitrary_nick

        self.assertEqual(actual_result, expected_result)

    def test_get_nick_with_pipe(self):
        arbitrary_nick = 'somebody|away'

        k = self.KarmaRecord({})
        actual_result = k.get_actual_nick(arbitrary_nick)
        expected_result = arbitrary_nick.split('|')[0]

        self.assertEqual(actual_result, expected_result)

    def test_get_actual_nick_no_alias(self):
        arbitrary_nick = 'two'

        k = self.KarmaRecord({})
        actual_result = k.get_actual_nick(arbitrary_nick)
        expected_result = arbitrary_nick

        self.assertEqual(actual_result, expected_result)

    def test_get_for_nick_existing(self):
        existing_nick = 'alpha'
        arbitrary_given = 1324
        arbitrary_record = {
            'nick': existing_nick,
            'given': arbitrary_given
        }
        self.db.karma_user.insert(arbitrary_record)

        k = self.KarmaRecord.get_for_nick(existing_nick)
        self.assertEqual(
            k['given'],
            arbitrary_given,
        )

    def test_get_for_nick_new(self):
        non_existing_nick = 'beta'
        k = self.KarmaRecord.get_for_nick(non_existing_nick)
        self.assertEqual(k['given'], 0)

    def test_get_top(self):
        first = {'nick': 'three', 'value': 15.0}
        second = {'nick': 'one', 'value': 10.0}
        third = {'nick': 'two', 'value': 5.0}
        self.db.karma_user.insert(second)
        self.db.karma_user.insert(third)
        self.db.karma_user.insert(first)

        expected_results = list(self.KarmaRecord.get_top(limit=2))
        self.assertEquals(expected_results[0]['nick'], first['nick'])
        self.assertEquals(expected_results[1]['nick'], second['nick'])
        self.assertEquals(len(expected_results), 2)

    def test_add_alias(self):
        main_nick = 'one'
        alias_nick = 'two'

        record = self._get_karma_record(
            main_nick,
            value=10,
            given=10,
            received=10,
        )
        alias_record = self._get_karma_record(
            alias_nick,
            value=10,
            given=10,
            received=10,
        )

        record.add_alias(alias_record)

        actual_result = self.KarmaRecord.get_for_nick(alias_nick)

        self.assertEquals(actual_result['nick'], main_nick)
        self.assertEquals(actual_result['value'], 20)
        self.assertEquals(actual_result['given'], 20)
        self.assertEquals(actual_result['received'], 20)

    def test_remove_alias(self):
        main_nick = 'three'
        alias_nick = 'four'
        alias = {
            'nick': alias_nick,
            'real_nick': main_nick,
            'record': {
                'nick': alias_nick,
                'given': 10,
                'received': 10,
                'value': 10,
                'created': datetime.datetime.now(),
                'last_received': datetime.datetime.utcnow(),
                'last_given': datetime.datetime.utcnow(),
            },
            'aliases': []
        }
        self.db.karma_link.insert(alias)

        record = self._get_karma_record(
            main_nick,
            given=20,
            value=20,
            received=20
        )
        record.save()
        record.remove_alias(alias_nick)

        main_record = self.KarmaRecord.get_for_nick(main_nick)
        alias_record = self.KarmaRecord.get_for_nick(alias_nick)

        self.assertEquals(main_record['nick'], main_nick)
        self.assertEquals(main_record['value'], 10)
        self.assertEquals(alias_record['nick'], alias_nick)
        self.assertEquals(alias_record['value'], 10)

    def test_get_aliases(self):
        main_nick = 'beta'
        alias_nick1 = 'alpha'
        alias_nick2 = 'gamma'

        main_record = self.KarmaRecord.get_for_nick(main_nick)
        alias_record1 = self.KarmaRecord.get_for_nick(alias_nick1)
        alias_record2 = self.KarmaRecord.get_for_nick(alias_nick2)
        main_record.add_alias(alias_record1)
        main_record.add_alias(alias_record2)

        actual_results = set(main_record.get_aliases())
        expected_results = set([alias_nick1, alias_nick2])

        self.assertEquals(actual_results, expected_results)

    @mock.patch('helga_karma.data.KarmaRecord.get_coefficient')
    def test_give_karma_to(self, get_coefficient_mock):
        # Prevent it from calculating coefficients automatically
        get_coefficient_mock.return_value = 1

        from_nick = 'giraffe'
        to_nick = 'elephant'

        from_record = self._get_karma_record(
            from_nick,
            value=5,
            given=10,
            received=10,
        )
        to_record = self._get_karma_record(
            to_nick,
            value=10,
            given=10,
            received=10,
        )

        from_record.give_karma_to(to_record)

        self.assertEquals(from_record['given'], 11)
        self.assertEquals(to_record['received'], 11)
        self.assertEquals(to_record['value'], 11)

    def test_get_global_karma_maximum(self):
        maximum_value = 30
        not_maximum_value = 20
        also_not_maximum_value = 10

        self._get_karma_record('alpha', value=not_maximum_value)
        self._get_karma_record('delta', value=maximum_value)
        self._get_karma_record('beta', value=also_not_maximum_value)

        expected_value = maximum_value
        actual_value = self.KarmaRecord.get_global_karma_maximum()

        self.assertEqual(actual_value, expected_value)

    def test_get_value_unscaled(self):
        karma_value = 223.210
        record = self._get_karma_record('delta', value=karma_value)

        expected_result = karma_value
        actual_result = record.get_value()

        self.assertEqual(actual_result, expected_result)

    @mock.patch('helga_karma.data.settings')
    def test_get_value_scaled_linear(self, settings):
        karma_maximum = 5
        karma_minimum = 1
        maximum_user_value = 104.24
        active_user_value = 60.12

        settings.KARMA_SCALED_RANGE = (karma_minimum, karma_maximum, )
        settings.KARMA_SCALE_LINEAR = True
        self._get_karma_record('alpha', value=maximum_user_value)
        user = self._get_karma_record('beta', value=active_user_value)

        expected_result = (
            (
                (active_user_value / maximum_user_value)
                * (karma_maximum - karma_minimum)
            ) + karma_minimum
        )
        actual_result = user.get_value()

        self.assertEqual(actual_result, expected_result)

    @mock.patch('helga_karma.data.settings')
    def test_get_value_scaled(self, settings):
        karma_maximum = 5
        karma_minimum = 1
        maximum_user_value = 104.24
        active_user_value = 60.12

        settings.KARMA_SCALED_RANGE = (karma_minimum, karma_maximum, )
        settings.KARMA_SCALE_LINEAR = False
        self._get_karma_record('alpha', value=maximum_user_value)
        user = self._get_karma_record('beta', value=active_user_value)

        expected_result = (
            (
                math.log(active_user_value + 1, maximum_user_value + 1)
                * (karma_maximum - karma_minimum)
            ) + karma_minimum
        )
        actual_result = user.get_value()

        self.assertEqual(actual_result, expected_result)
