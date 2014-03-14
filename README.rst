.. image:: https://travis-ci.org/coddingtonbear/helga-karma.png?branch=master   :target: https://travis-ci.org/coddingtonbear/helga-karma

Helga Karma
===========

Modeled after `PMXBot <https://bitbucket.org/yougov/pmxbot>`_'s karma plugin,
but just a little bit better.

Commands
--------

!k[arma] [details] [for] [<nick>]
+++++++++++++++++++++++++++++++++

Get a user's Karma information.

Example::

    person> !karma
    helga>  person has about 24 karma, person.

You can also ask about another person's karma::

    person> !karma somebody
    helga>  somebody has about 10 karma, person.

And, if you're curious about the details, you can ask for those, too, and
even abbreviate the command itself::

    person> !k details somebody
    helga>  somebody has 10.1 karma.  (thanked others 20 times, received
            thanks 12 times, karma coefficient: 0.6, aliases: adam,
            coddingtonbear)

!k[arma] top [10]
+++++++++++++++++

Get a list of people ordered by how much karma they have.

Example::

    person> !karma top 3
    helga> #1: somebody (2213 karma) | #2: somebody_else (2013 karma) |
           #3: whoisthis (1408 karma)

!k[arma] <nick1>==<nick2>
+++++++++++++++++++++++++

Link two nicknames together to share the same karma values.  This is commonly
used for away nicknames.

Example::

    person> !karma coddingtonbear==coddingtonbear_away
    helga>  coddingtonbear and coddingtonbear_away are now linked, person.

!k[arma] <nick1>!=<nick2>
+++++++++++++++++++++++++

Unlink two nicknames from one another.

Example::

    person> !karma coddingtonbear!=coddingtonbear_away
    helga>  coddingtonbear and coddingtonbear_away are now unlinked, person.

!t[hanks] <nickname>
++++++++++++++++++++

Thank somebody for doing a good job!

Example::

    youthere> I've just fitzbangled the horsemonster for you, person.
    person>   !thanks youthere
    helga>    You're doing good work, youthere!

Also has an alias -- ``!m[otivate]`` -- for situations in which somebody
hasn't yet done the thing you're appreciative of::

    somebody> youthere -- could I convince you into orangerunning the
              twinkleverse?
    somebody> !m youthere
    helga>    You're doing good work, youthere!
    youthere> No problem, somebody!

