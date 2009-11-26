###
# Copyright (c) 2008, Terence Simpson <tsimpson@ubuntu.com>
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
Let nickserv-identified users log in without password via Launchpad
"""

import supybot
import supybot.world as world

__version__ = "0.4"
__author__ = supybot.Author("Terence Simpson","tsimpson","tsimpson@ubuntu.com")
__contributors__ = {}
__url__ = 'http://ubottu.com'

import config
reload(config)
import plugin
reload(plugin)

if world.testing:
    import test

Class = plugin.Class
configure = config.configure
