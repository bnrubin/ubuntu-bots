###
# Copyright (c) 2006,2007 Dennis Kaarsemaker
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of version 2 of the GNU General Public License as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
###

import supybot.conf as conf
import supybot.registry as registry

class ValidTypes(registry.OnlySomeStrings):
    """Invalid type, valid types are: 'removal', 'ban' or 'quiet'."""
    validStrings = ('removal', 'ban', 'quiet')

class SpaceSeparatedListOfTypes(registry.SpaceSeparatedListOf):
    Value = ValidTypes


# This registry translates days to seconds
# storing seconds instead of days is more convenient for testing
class DaysToSeconds(registry.Integer):
    """Value must be an integer and not higher than 100"""
    def set(self, s):
        try:
            n = int(s)
            if n > 100:
                raise ValueError
            self.setValue(n*84600)
        except ValueError:
            self.error()


def configure(advanced):
    conf.registerPlugin('Bantracker', True)

Bantracker = conf.registerPlugin('Bantracker')
conf.registerChannelValue(Bantracker, 'enabled',
        registry.Boolean(False, """Enable the bantracker"""))
conf.registerGlobalValue(Bantracker, 'database',
        registry.String('', "Filename of the bans database", private=True))
conf.registerGlobalValue(Bantracker, 'bansite',
        registry.String('', "Web site for the bantracker, without the 'bans.cgi' appended", private=True))

conf.registerGroup(Bantracker, 'commentRequest')
conf.registerChannelValue(Bantracker.commentRequest, 'type',
        SpaceSeparatedListOfTypes(['removal', 'ban', 'quiet'],
            "List of events for which the bot should request a comment."))
conf.registerChannelValue(Bantracker.commentRequest, 'ignore',
        registry.SpaceSeparatedListOfStrings([],
            "List of nicks for which the bot won't request to comment a ban/quiet/removal."\
            " Is case insensible and wildcards * ? are accepted."))
conf.registerChannelValue(Bantracker.commentRequest, 'forward',
        registry.SpaceSeparatedListOfStrings([],
            "List of nicks for which the bot will forward the request to"\
            " the channels/nicks defined in forwards.channels option."\
            " Is case insensible and wildcards * ? are accepted."))
conf.registerChannelValue(Bantracker.commentRequest.forward, 'channels',
        registry.SpaceSeparatedListOfStrings([],
            "List of channels/nicks to forward the request if the op that set the ban/quiet"\
            " is in the forward list."))


# temp config
conf.registerGlobalValue(Bantracker, 'reviewTime',
        registry.Integer(0, "", ))
conf.registerGlobalValue(Bantracker, 'reviewAfterTime',
        DaysToSeconds(7*84600,
            "Days after which the bot will request for review a ban. NOTE: the number of days is"
            " stored in seconds, but when configuring it the time unit is in days."))
