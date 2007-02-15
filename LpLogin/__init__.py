###
# Copyright (c) 2007, Dennis Kaarsemaker
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

"""
Add a description of the plugin (to be presented to the user inside the wizard)
here.  This should describe *what* the plugin does.
"""

import supybot
import supybot.world as world

__version__ = "0.1"
__author__ = supybot.Author("Dennis Kaarsemaker","Seveas","dennis@kaarsemaker.net")
__contributors__ = {}
__url__ = 'http://bots.ubuntulinux.nl/'

import config
reload(config)
import plugin
reload(plugin)

if world.testing:
    import test

Class = plugin.Class
configure = config.configure
