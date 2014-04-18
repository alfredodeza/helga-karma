import re
import six

from helga import log, settings
from helga.plugins import command, match

from .data import KarmaRecord


logger = log.getLogger(__name__)


VALID_NICK_PAT = r'[\w{}\[\]\-|^`\\]+'


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

    'top': '#{idx}: {nick} ({value} {VALUE_NAME})',

    'linked_already': '{secondary} is already linked to {main}.',
    'linked': '{main} and {secondary} are now linked.',

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


_DEFAULT_THANKS_WORDS = [
    'thank you',
    'thanks',
    'tyvm',
    'ty',
]


def format_message(name, **kwargs):
    overrides = getattr(settings, 'KARMA_MESSAGE_OVERRIDES', {})
    message = overrides.get(name, MESSAGES[name])

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
    return message.format(**kwargs)


def info(requested_by, for_nick, detailed=False):
    """
    Get karma for a specified user, optionally verbose
    """
    record = KarmaRecord.get_for_nick(for_nick)

    if not record.get_value() and not detailed:
        return format_message(
            'info_none',
            for_nick=for_nick,
            nick=requested_by,
        )

    if detailed:
        aliases = record.get_aliases()
        return format_message(
            'info_detailed',
            for_nick=record['nick'],
            value=round(record.get_value(), 2),
            given=record['given'],
            received=record['received'],
            coefficient=round(record.get_coefficient(), 2),
            aliases=(
                ', '.join(aliases)
                if len(aliases) else 'none'
            )
        )

    return format_message(
        'info_standard',
        for_nick=for_nick,
        value=int(round(record.get_value(), 0)),
        nick=requested_by,
    )


def top(limit=10):
    """
    Get the top N users
    """
    top_n = KarmaRecord.get_top(limit)
    lines = []
    for idx, record in enumerate(top_n):
        lines.append(
            format_message(
                'top',
                idx=idx+1,
                nick=record['nick'],
                value=round(record.get_value(), 1),
            )
        )
    return lines


def give(from_nick, to_nick):
    """
    Give karma from one user to another with some regards to greediness
    """
    if from_nick == to_nick:
        return format_message('too_arrogant', nick=from_nick)

    from_record = KarmaRecord.get_for_nick(from_nick)
    to_record = KarmaRecord.get_for_nick(to_nick)

    from_record.give_karma_to(to_record)

    return format_message('good_job', nick=to_nick)


def alias(requested_by, nick1, nick2):
    """
    Mark a second nick as an alias of a certain nick
    """
    # KarmaRecord.get_for_nick will resolve aliases for us,
    # so we don't need to worry about checking whether they're already
    # linked as long as we make sure that the resultant records' nicks
    # do not already match.
    user1 = KarmaRecord.get_for_nick(nick1)
    user2 = KarmaRecord.get_for_nick(nick2)

    if user1['nick'] == user2['nick']:
        return format_message('nope', nick=requested_by)

    if user2['value'] > user1['value']:
        user1, user2 = user2, user1

    user1.add_alias(user2)
    return format_message(
        'linked',
        main=user1['nick'],
        secondary=user2['nick'],
    )


def unalias(requested_by, nick1, nick2):
    """
    Unmark a second nick as an alias of a certain nick
    """
    if nick1 == nick2:
        return format_message('nope', nick=requested_by)

    records = {
        nick1: KarmaRecord.get_for_nick(
            nick1,
            use_aliases=False,
            get_empty=False,
        ),
        nick2: KarmaRecord.get_for_nick(
            nick2,
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
        return format_message('unknown_user_many', nick=requested_by)

    main = actual.pop()

    if len(actual) == 2 or alias not in main.get_aliases():
        return format_message('unlinked_not_linked', usera=nick1, userb=nick2)

    main.remove_alias(alias)
    return format_message('unlinked', usera=nick1, userb=nick2)


def _handle_command(client, channel, nick, message, command, args):
    """
    The command variant of this plugin
    """
    if command in ('t', 'thanks', 'm', 'motivate'):
        return give(from_nick=nick, to_nick=args[0])

    # Handle the base `karma` command
    if not args:
        return info(requested_by=nick, for_nick=nick)

    subcmd = args[0]

    # Handle top N karma
    if subcmd == 'top':
        try:
            limit = int(args[1])
        except (IndexError, ValueError):
            limit = 10
        return top(limit)

    if subcmd == 'alias':
        return alias(requested_by=nick, nick1=args[1], nick2=args[2])

    if subcmd == 'unalias':
        return unalias(requested_by=nick, nick1=args[1], nick2=args[2])

    if subcmd == 'details':
        return info(requested_by=nick, for_nick=args[-1], detailed=True)

    return info(requested_by=nick, for_nick=args[-1])


def _handle_match(client, channel, nick, message, matches):
    to_nick = matches[0][1]
    logger.info('Autokarma: {from_nick} -> {to_nick}'.format(from_nick=nick,
                                                             to_nick=to_nick))
    give(from_nick=nick, to_nick=to_nick)


def _autokarma_match(message):
    """
    Match an incoming message for any nicks that should receive auto karma
    """
    thanks_words = getattr(settings,
                           'KARMA_THANKS_WORDS',
                           _DEFAULT_THANKS_WORDS)

    pattern = r'^(?i)({thanks})[^\w]+({nick}).*$'.format(
        thanks='|'.join(thanks_words),
        nick=VALID_NICK_PAT
    )

    return re.findall(pattern, message)


@match(_autokarma_match)
@command('karma', aliases=['k', 'thanks', 'motivate', 't', 'm', 'alias', 'unalias'],
         help=('Give and receive karma. Usage: helga ('
               'k[arma] [(top [num] | [details] [for] [nick] | [un]alias <nick1> <nick2>)] | '
               '(t[hanks] | m[otivate]) <nick>)'))
def karma(client, channel, nick, message, *args):
    fn = _handle_command if len(args) == 2 else _handle_match
    return fn(client, channel, nick, message, *args)
