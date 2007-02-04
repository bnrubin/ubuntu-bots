###
# Copyright (c) 2006, Dennis Kaarsemaker
# All rights reserved.
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
    conf.registerPlugin('Restart', True)

Restart = conf.registerPlugin('Restart')
conf.registerGlobalValue(Restart, 'configfile',
    registry.String('', """Config filename to restart with"""))
