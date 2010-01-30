###
# Copyright (c) 2008, Terence Simpson
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
    from supybot.questions import expect, anything, something, yn
    conf.registerPlugin('IRCLogin', True)

IRCLogin = conf.registerPlugin('IRCLogin')
conf.registerGlobalValue(IRCLogin, 'UserList',
    registry.String('', """Filename of file with list of users""",private=True))
conf.registerGlobalValue(IRCLogin, "teamname",
    registry.String('ubuntu-irc', "Name of the Launchpad team to get users from", private=True))
