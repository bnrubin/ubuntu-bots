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

def configure(advanced):
    conf.registerPlugin('Bantracker', True)

Bantracker = conf.registerPlugin('Bantracker')
conf.registerChannelValue(conf.supybot.plugins.Bantracker, 'enabled',
        registry.Boolean(False, """Enable the bantracker"""))
conf.registerGlobalValue(conf.supybot.plugins.Bantracker, 'database',
        registry.String('', "Filename of the bans database", private=True))
conf.registerGlobalValue(conf.supybot.plugins.Bantracker, 'bansite',
        registry.String('', "Web site for the bantracker, without the 'bans.cgi' appended", private=True))

conf.registerGroup(Bantracker, 'commentRequest')
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

