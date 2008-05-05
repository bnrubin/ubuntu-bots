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
        registry.String('', "Filename of the bans database",private=True))
conf.registerGlobalValue(conf.supybot.plugins.Bantracker, 'bansite',
        registry.String('', "Web site for the bantracker, without the 'bans.cgi' appended", private=True))
