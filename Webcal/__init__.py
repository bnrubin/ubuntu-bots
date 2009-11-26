###
# Copyright (c) 2005-2007 Dennis Kaarsemaker
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

"""
Update the topic according to an iCal schedule
"""

import supybot
import supybot.world as world
__version__ = "0.3"
__author__ = supybot.Author("Dennis Kaarsemaker","Seveas","dennis@kaarsemaker.net")
__contributors__ = {}
__url__ = 'http://ubottu.com'

import config
reload(config)
import plugin
reload(plugin)
import ical
reload(ical)

if world.testing:
    import test
Class = plugin.Class
configure = config.configure
