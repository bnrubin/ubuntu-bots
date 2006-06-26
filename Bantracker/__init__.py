"""
This plugin can store all kick/ban/remove/mute actions
"""

import supybot
import supybot.world as world

__version__ = "0.2"
__author__ = supybot.Author("Dennis Kaarsemaker","Seveas","dennis@kaarsemaker.net")
__contributors__ = {}
__url__ = 'https://bots.ubuntulinux.nl'

import config
reload(config)
import plugin
reload(plugin)

if world.testing:
    import test

Class = plugin.Class
configure = config.configure
