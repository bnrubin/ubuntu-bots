# -*- Encoding: utf-8 -*-
###
# Copyright (c) 2006-2007 Dennis Kaarsemaker
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
Random mess plugin
"""

import supybot
import supybot.world as world

__version__ = "0.5"
__author__ = supybot.Author('Terence Simpson', 'tsimpson', 'tsimpson@ubuntu.com')
__contributors__ = {
    supybot.Author('Dennis Kaarsemaker','Seveas','dennis@kaarsemaker.net'): ['Original Author']
}
__url__ = 'https://launchpad.net/ubuntu-bots/'

import config
reload(config)
import plugin
reload(plugin)

if world.testing:
    import test
Class = plugin.Class
configure = config.configure
