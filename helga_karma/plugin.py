import re

import six

from helga import log
from helga.plugins import Plugin

from .data import KarmaRecord


logger = log.getLogger(__name__)


class KarmaPlugin(Plugin):
    KARMA_COMMANDS = {
        'info': (
            r'^!k(?:arma)? ?(?P<detailed>details)?'
            r' ?(?:for)? ?(?P<nick>[\w-]+)?$'
        ),
        'top': r'^!k(?:arma)? top (?P<count>\d+)$',
        'link': r'^!k(?:arma)? (?P<usera>[\w-]+) ?== ?(?P<userb>[\w-]+)$',
        'unlink': r'^!k(?:arma)? (?P<usera>[\w-]+) ?!= ?(?P<userb>[\w-]+)$',
        'give': r'^!(t(?:hanks)?|m(?:otivate)?) (?P<nick>[\w]+)$',
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
            return (
                "I'm not aware of {nick} having done anything "
                "helpful, {nick}.".format(
                    for_nick=for_nick,
                    nick=nick,
                )
            )

        if detailed:
            aliases = record.get_aliases()
            return (
                '{for_nick} has {value} karma. ('
                'thanked others {given} times, '
                'received thanks {received} times, '
                'karma coefficient {coefficient}, '
                'aliases: {aliases})'.format(
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
            )
        return (
            "{for_nick} has about {value} karma, {nick}.".format(
                for_nick=for_nick,
                value=int(round(record['value'], 0)),
                nick=nick,
            )
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
        if matches['usera'] == matches['userb']:
            return "That doesn't make much sense now, does it, {nick}.".format(
                nick=nick
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
        if not all(six.itervalues(records)):
            for name, record in six.iteritems(records):
                if not record:
                    return "I don't know who {who} is, {nick}.".format(
                        who=name,
                        nick=nick,
                    )

        main, secondary = records.values()
        if secondary['value'] > main['value']:
            _main = secondary
            secondary = main
            main = _main

        if secondary['nick'] in main.get_aliases():
            return "{secondary} is already linked to {main}.".format(
                secondary=secondary['nick'],
                main=main['nick'],
            )

        main.add_alias(secondary)
        return "{main} and {secondary} are now linked, {nick}.".format(
            main=main['nick'],
            secondary=secondary['nick'],
            nick=nick,
        )

    def unlink(self, channel, nick, message, matches):
        if matches['usera'] == matches['userb']:
            return "That doesn't make much sense now, does it, {nick}.".format(
                nick=nick
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
            return (
                "Neither of the users you specified appear to exist, "
                "{nick}.".format(
                    nick=nick,
                )
            )
        main = actual.pop()
        if len(actual) == 2 or alias not in main.get_aliases():
            return (
                "{usera} and {userb} are not linked.".format(
                    usera=matches['usera'],
                    userb=matches['userb'],
                )
            )

        main.remove_alias(alias)
        return "{usera} and {userb} are now unlinked.".format(
            usera=matches['usera'],
            userb=matches['userb'],
        )

    def give(self, channel, nick, message, matches):
        if matches['nick'] == nick:
            return "Uhh, do you want a gold star, {nick}?".format(nick=nick)

        from_record = KarmaRecord.get_for_nick(nick)
        to_record = KarmaRecord.get_for_nick(matches['nick'])

        from_record.give_karma_to(to_record)

        return "You're doing good work, {nick}!".format(
            nick=matches['nick']
        )
