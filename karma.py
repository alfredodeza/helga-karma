import datetime
import re

import pymongo

from helga import log
from helga.db import db
from helga.plugins import match


logger = log.getLogger(__name__)


def get_karma_command(message):
    for regex, handler in KARMA_COMMANDS.items():
        result = re.match(regex, message)
        if result:
            matches = result.groupdict()
            return handler, matches


def calculate_karma_coefficient(karma_record):
    """ Calaulate the weight of karma given by provided record's user

    In order to effectively reduce the net value of frequent over-givers
    of karma -- and increase the net value of people who thank only
    infrequently -- reduce the effective weight of users in proportion
    to the ratio of received vs given karma.

    """
    return (
        max(float(karma_record['received']), 1)
        / max(karma_record['given'], 1)
    )


def get_karma_record(nick):
    linked = db.karma_link.find_one({'nick': nick})
    if linked:
        nick = linked['real_nick']
    record = {
        'nick': nick,
        'given': 0,
        'received': 0,
        'value': 0,
        'record_created': datetime.datetime.now(),
        'last_received_thanks': None,
        'last_given_thanks': None,
    }
    result = db.karma_user.find_one({'nick': nick})
    if result:
        record.update(result)
    return record


def set_karma_record(record):
    db.karma_user.update(
        {'nick': record['nick']},
        record,
        upsert=True,
    )


def give_karma(from_, to, count=1):
    from_record = get_karma_record(from_)
    to_record = get_karma_record(to)

    value = count * calculate_karma_coefficient(from_record)

    from_record['given'] += 1
    from_record['last_given_thanks'] = datetime.datetime.now()
    set_karma_record(from_record)

    to_record['last_received_thanks'] = datetime.datetime.now()
    to_record['received'] += count
    to_record['value'] += value
    set_karma_record(to_record)

    return value


# Commands

def karma_info(client, channel, nick, message, matches):
    for_nick = matches['nick'] if matches['nick'] else nick
    is_self = nick == for_nick
    detailed = matches['detailed']

    karma_record = get_karma_record(for_nick)
    aliases = db.karma_link.find({'real_nick': karma_record['nick']})

    if not karma_record['value'] and not detailed:
        if is_self:
            return (
                "You haven't done anything helpful that "
                "I'm aware of, {nick}.".format(
                    nick=nick,
                )
            )
        else:
            return (
                "I'm not aware of {for_nick} having done "
                "anything helpful, {nick}.".format(
                    for_nick=for_nick,
                    nick=nick,
                )
            )

    if detailed:
        value = round(karma_record['value'], 2)
        return (
            '{for_nick} has {value} karma. ('
            'thanked others {given} times, '
            'received thanks {received} times, '
            'karma coefficient {coefficient}, '
            'aliases: {aliases})'.format(
                for_nick=karma_record['nick'],
                value=value,
                given=karma_record['given'],
                received=karma_record['received'],
                coefficient=round(
                    calculate_karma_coefficient(karma_record), 2
                ),
                aliases=(
                    ', '.join([u['nick'] for u in aliases])
                    if aliases.count() else 'none'
                )
            )
        )
    else:
        value = int(round(karma_record['value']))
        if is_self:
            return "You have about {value} karma, {nick}.".format(
                value=value,
                nick=nick,
            )
        return "{for_nick} has about {value} karma, {nick}.".format(
            for_nick=for_nick,
            value=value,
            nick=nick,
        )


def karma_leaders(client, channel, nick, message, matches):
    limit = int(matches['count']) if matches['count'] else 10
    results = (
        db.karma_user.find()
        .sort('value', direction=pymongo.DESCENDING)
        .limit(limit)
    )
    lines = []
    for idx, record in enumerate(results):
        lines.append(
            '#{idx}: {nick} ({value} karma)'.format(
                idx=idx+1,
                nick=record['nick'],
                value=round(record['value'], 1),
            )
        )
    return '  |  '.join(lines)


def link_karma(client, channel, nick, message, matches):
    if matches['usera'] == matches['userb']:
        return "That doesn't make much sense now, does it, {nick}.".format(
            nick=nick
        )

    record_a = get_karma_record(matches['usera'])
    record_b = get_karma_record(matches['userb'])

    # Figure out who has the highest karma, and link the other record to that
    from_record = record_b
    to_record = record_a
    if record_b['value'] > record_a['value']:
        from_record = record_a
        to_record = record_b

    if from_record['nick'] == to_record['nick']:
        raise Exception("What?")

    # Prevent linking a single record twice
    for record in [from_record, to_record]:
        result = db.karma_link.find_one({'nick': record['nick']})
        if result:
            return "{one} is already linked to {another}.".format(
                one=record['nick'],
                another=result['real_nick']
            )

    db.karma_link.insert(
        {
            'nick': from_record['nick'],
            'real_nick': to_record['nick'],
            'record': from_record,
        },
    )
    to_record['given'] += from_record['given']
    to_record['received'] += from_record['received']
    to_record['value'] += from_record['value']
    for key in ['last_received_thanks', 'last_given_thanks']:
        if (
            from_record[key] and to_record[key]
            and from_record[key] > to_record[key]
        ):
            to_record[key] = from_record[key]
    if from_record['record_created'] < to_record['record_created']:
        to_record['record_created'] = from_record['record_created']
    set_karma_record(to_record)
    db.karma_user.remove({'nick': from_record['nick']})

    return "Nicks {one} and {two} are now linked.".format(
        one=from_record['nick'],
        two=to_record['nick'],
    )


def unlink_karma(client, channel, nick, message, matches):
    if matches['usera'] == matches['userb']:
        return "That doesn't make much sense now, does it, {nick}.".format(
            nick=nick
        )

    results = list(
        db.karma_link.find(
            {
                '$or': [
                    {'nick': matches['usera']},
                    {'nick': matches['userb']}
                ]
            }
        )
    )
    if len(results) < 1:
        return "Neither of the users you specified appear to be linked."

    linked_data = results[0]

    master_nick = matches['usera']
    if linked_data['nick'] == master_nick:
        master_nick = matches['userb']

    if linked_data['real_nick'] != master_nick:
        return "Nick {nick} is linked to {actual}, not {expected}.".format(
            linked_data['nick'],
            linked_data['real_nick'],
            master_nick,
        )

    master_record = get_karma_record(master_nick)
    master_record['given'] -= linked_data['record']['given']
    master_record['received'] -= linked_data['record']['received']
    master_record['value'] -= linked_data['record']['value']

    set_karma_record(master_record)
    set_karma_record(linked_data['record'])
    db.karma_link.remove({'nick': linked_data['nick']})

    return "Nicks {one} and {two} are now unlinked.".format(
        one=master_record['nick'],
        two=linked_data['nick'],
    )


def thanks(client, channel, nick, message, matches):
    if nick == matches['nick']:
        # Don't let people give karma to themselves
        return "Uhh, do you want a gold star, {nick}?".format(nick=nick)

    give_karma(
        nick,
        matches['nick'],
    )
    return "You're doing good work {nick}!".format(
        nick=matches['nick']
    )


@match(get_karma_command)
def karma(client, channel, nick, message, result):
    handler, matches = result
    return handler(client, channel, nick, message, matches)


KARMA_COMMANDS = {
    # List karma information for a nick.
    # - !karma [details] [for] [nick]
    r'^!k(?:arma)? ?(?P<detailed>details)? ?(?:for)? ?(?P<nick>[\w-]+)?$': (
        karma_info
    ),

    # List (in descending order) nicks having top karma>
    # - !karma top [10]
    r'^!k(?:arma)? top (?P<count>\d+)$': karma_leaders,

    # Link karma between two nicks.
    # - !karma arbitraryNick == arbitraryNick2
    r'^!k(?:arma)? (?P<usera>[\w-]+) ?== ?(?P<userb>[\w-]+)$': link_karma,

    # Unlink karma between two nicks.
    # - !karma arbitraryNick != arbitraryNick2
    r'^!k(?:arma)? (?P<usera>[\w-]+) ?!= ?(?P<userb>[\w-]+)$': unlink_karma,

    # Give thanks (karma) to somebody who deserves it.
    # - !thanks somebody
    # - !motivate somebody
    r'^!(t(?:hanks)?|m(?:otivate)?) (?P<nick>[\w]+)$': thanks
}
