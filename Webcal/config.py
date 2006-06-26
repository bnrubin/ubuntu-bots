###
# Copyright (c) 2005,2006 Dennis Kaarsemaker
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
    conf.registerPlugin('Webcal', True)

Webcal = conf.registerPlugin('Webcal')
conf.registerChannelValue(conf.supybot.plugins.Webcal, 'url',
    registry.String('',"""Webcal URL for the channel"""))
conf.registerChannelValue(conf.supybot.plugins.Webcal, 'topic',
    registry.String('',"""Topic template"""))
conf.registerGlobalValue(conf.supybot.plugins.Webcal, 'defaultChannel',
    registry.String('',"""Default channel for /msg replies"""))
