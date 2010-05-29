# -*- Encoding: utf-8 -*-
###
# Copyright (c) 2008-2010 Terence Simpson
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
    from supybot.questions import expect, something, yn

    def anything(prompt, default=None):
        """Because supybot is pure fail"""
        from supybot.questions import expect
        return expect(prompt, [], default=default)

    IRCLogin = conf.registerPlugin('IRCLogin', True)

    if advanced:
        ## NOTE: This is currently disabled until rewritten to use launchpadlib
        #UserList = anything("What file should be used to contains the list of users?", default=conf.supybot.directories.data.dirize("users.db"))
        #teamname = something("What is the Launchpad team name to get the list of users from?", default=IRCLogin.teamname._default)
        UserList = IRCLogin.UserList._default
        teamname = IRCLogin.teamname._default
    else:
        UserList = IRCLogin.UserList._default
        teamname = IRCLogin.teamname._default

    IRCLogin.UserList.setValue(UserList)
    IRCLogin.teamname.setValue(teamname)

IRCLogin = conf.registerPlugin('IRCLogin')
conf.registerGlobalValue(IRCLogin, 'UserList',
    registry.String('', """Filename of file with list of users""",private=True))
conf.registerGlobalValue(IRCLogin, "teamname",
    registry.String('ubuntu-irc', "Name of the Launchpad team to get users from", private=True))
