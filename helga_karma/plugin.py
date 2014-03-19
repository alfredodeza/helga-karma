import re

import six

from helga import log, settings
from helga.plugins import Plugin

from .data import KarmaRecord


logger = log.getLogger(__name__)


class KarmaPlugin(Plugin):
    KARMA_COMMANDS = {
        'info': (
            r'^!k(?:arma)? ?(?P<detailed>details)?'
            r' ?(?:for)? ?(?P<nick>[\w|-]+)?$'
        ),
        'top': r'^!k(?:arma)? top (?P<count>\d+)$',
        'link': r'^!k(?:arma)? (?P<usera>[\w|-]+) ?== ?(?P<userb>[\w|-]+)$',
        'unlink': r'^!k(?:arma)? (?P<usera>[\w|-]+) ?!= ?(?P<userb>[\w|-]+)$',
        'give': r'^!(t(?:hanks)?|m(?:otivate)?) (?P<nick>[\w|-]+)$',
    }
    MESSAGES = {
        'info_none': (
            'I\'m not aware of {for_nick} having done anything '
            'helpful, {nick}.'
        ),
        'info_detailed': (
            '{for_nick} has {value} {VALUE_NAME}. ('
            'thanked others {given} times, '
            'received thanks {received} times, '
            '{COEFFICIENT_NAME} {coefficient}, '
            'aliases: {aliases})'
        ),
        'info_standard': (
            '{for_nick} has about {value} '
            '{VALUE_NAME}, {nick}.'
        ),

        'linked_already': '{secondary} is already linked to {main}.',
        'linked': '{main} and {secondary} are now linked, {nick}.',

        'unlinked_not_linked': '{usera} and {userb} are not linked.',
        'unlinked': '{usera} and {userb} are now unlinked.',

        'too_arrogant': 'Uhh, do you want a gold star, {nick}?',
        'good_job': 'You\'re doing good work, {nick}!',

        'unknown_user_many': (
            'Neither of the users you specified appear to exist, {nick}.'
        ),
        'unknown_user': 'I don\'t know who {for_nick} is, {nick}.',
        'nope': 'That doesn\'t make much sense now, does it, {nick}.'
    }

    def __init__(self, *args, **kwargs):
        super(KarmaPlugin, self).__init__(*args, **kwargs)

        # Let's both pre-compile the regexen, as well as look up the
        # mapped methods (just to make sure we fail early if they're
        # unspecified).
        commands = {}
        for cmd_name, cmd_re in six.iteritems(self.KARMA_COMMANDS):
            commands[getattr(self, cmd_name)] = re.compile(cmd_re)
        self._compiled_karma_commands = commands

    @property
    def karma_commands(self):
        return self._compiled_karma_commands

    def format_message(self, name, **kwargs):
        kwargs['VALUE_NAME'] = getattr(
            settings,
            'KARMA_VALUE_NAME',
            'karma'
        )
        kwargs['COEFFICIENT_NAME'] = getattr(
            settings,
            'KARMA_COEFFICIENT_NAME',
            'karma coefficient'
        )
        return self.MESSAGES[name].format(**kwargs)

    def run(self, channel, nick, message, command, groups):
        try:
            return command(channel, nick, message, groups)
        except Exception as e:
            logger.exception(e)
            return 'Exception encountered while processing your request.'

    def process(self, client, channel, nick, message):
        for command, regex in six.iteritems(self.karma_commands):
            matched = regex.match(message)
            if matched:
                groups = matched.groupdict()
                return self.run(channel, nick, message, command, groups)

    def info(self, channel, nick, message, matches):
        for_nick = matches['nick'] if matches['nick'] else nick
        detailed = matches['detailed']

        record = KarmaRecord.get_for_nick(for_nick)

        if not record['value'] and not detailed:
            return self.format_message(
                'info_none',
                for_nick=for_nick,
                nick=nick,
            )

        if detailed:
            aliases = record.get_aliases()
            return self.format_message(
                'info_detailed',
                for_nick=record['nick'],
                value=round(record['value'], 2),
                given=record['given'],
                received=record['received'],
                coefficient=round(record.get_coefficient(), 2),
                aliases=(
                    ', '.join(aliases)
                    if len(aliases) else 'none'
                )
            )
        return self.format_message(
            'info_standard',
            for_nick=for_nick,
            value=int(round(record['value'], 0)),
            nick=nick,
        )

    def top(self, channel, nick, message, matches):
        limit = int(matches['count']) if matches['count'] else 10
        top_n = KarmaRecord.get_top(limit)
        lines = []
        for idx, record in enumerate(top_n):
            lines.append(
                '#{idx}: {nick} ({value} karma)'.format(
                    idx=idx+1,
                    nick=record['nick'],
                    value=round(record['value'], 1),
                )
            )
        return ' | '.join(lines)

    def link(self, channel, nick, message, matches):
        # KarmaRecord.get_for_nick will resolve aliases for us,
        # so we don't need to worry about checking whether they're already
        # linked as long as we make sure that the resultant records' nicks
        # do not already match.
        records = {
            'usera': KarmaRecord.get_for_nick(matches['usera']),
            'userb': KarmaRecord.get_for_nick(matches['userb'])
        }
        if records['usera']['nick'] == records['userb']['nick']:
            return self.format_message(
                'nope',
                nick=nick,
            )

        main, secondary = records.values()
        if secondary['value'] > main['value']:
            _main = secondary
            secondary = main
            main = _main

        main.add_alias(secondary)
        return self.format_message(
            'linked',
            main=main['nick'],
            secondary=secondary['nick'],
        )

    def unlink(self, channel, nick, message, matches):
        if matches['usera'] == matches['userb']:
            return self.format_message(
                'nope',
                nick=nick,
            )

        records = {
            matches['usera']: KarmaRecord.get_for_nick(
                matches['usera'],
                use_aliases=False,
                get_empty=False,
            ),
            matches['userb']: KarmaRecord.get_for_nick(
                matches['userb'],
                use_aliases=False,
                get_empty=False,
            )
        }
        actual = [v for v in six.itervalues(records) if v]
        try:
            alias = [k for k, v in six.iteritems(records) if not v][0]
        except IndexError:
            alias = None
        if len(actual) == 0:
            return self.format_message(
                'unknown_user_many',
                nick=nick,
            )

        main = actual.pop()
        if len(actual) == 2 or alias not in main.get_aliases():
            return self.format_message(
                'unlinked_not_linked',
                usera=matches['usera'],
                userb=matches['userb'],
            )

        main.remove_alias(alias)
        return self.format_message(
            'unlinked',
            usera=matches['usera'],
            userb=matches['userb'],
        )

    def give(self, channel, nick, message, matches):
        if matches['nick'] == nick:
            return self.format_message(
                'too_arrogant',
                nick=nick,
            )

        from_record = KarmaRecord.get_for_nick(nick)
        to_record = KarmaRecord.get_for_nick(matches['nick'])

        from_record.give_karma_to(to_record)

        return self.format_message(
            'good_job',
            nick=matches['nick']
        )
