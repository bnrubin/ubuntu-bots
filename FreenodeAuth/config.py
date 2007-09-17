###
# Copyright (c) 2007, Dennis Kaarsemaker
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
    conf.registerPlugin('FreenodeAuth', True)

FreenodeAuth = conf.registerPlugin('FreenodeAuth')
conf.registerGlobalValue(FreenodeAuth, 'UserList',
    registry.String('', """Filename of file with list of users""",private=True))
