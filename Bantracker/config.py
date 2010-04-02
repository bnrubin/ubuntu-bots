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


# This little hack allows me to store last time bans were checked for review
# and guarantee that nobody will edit it.
# I'm using a registry option instead of the SQL db because this is much simpler.
class ReadOnlyValue(registry.Integer):
    """This is a read only option."""
    def __init__(self, *args, **kwargs):
        registry.Integer.__init__(self, *args, **kwargs)
        self.value = None

    def set(self, s):
        try:
            if not self.value:
                self.setValue(int(s))
            else:
                raise ValueError
        except ValueError:
            #self.error() # commented, this causes a lot of trouble.
            pass


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
        ReadOnlyValue(0,
            "Timestamp used internally for identify bans that need review. Can't and shouldn't be edited."))
conf.registerGlobalValue(Bantracker, 'reviewAfterTime',
        registry.Float(7,
            "Days after which the bot will request for review a ban. Can be an integer or decimal value."))
