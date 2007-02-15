###
# Copyright (c) 2007, Dennis Kaarsemaker
# All rights reserved.
#
#
###

import supybot.conf as conf
import supybot.registry as registry

def configure(advanced):
    from supybot.questions import expect, anything, something, yn
    conf.registerPlugin('LpLogin', True)


LpLogin = conf.registerPlugin('LpLogin')
conf.registerGlobalValue(LpLogin, 'UserList',
    registry.String('', """Filename of file with list of users"""))
conf.registerGlobalValue(LpLogin, 'DeleteUnknowns',
    registry.Boolean(True, """Unregister people not in the list"""))
