"""
Various channel protections
"""

import supybot
import supybot.world as world

__version__ = "0.1"
__author__ = supybot.Author('Dennis Kaarsemaker', 'Seveas', 'dennis@kaarsemaker.net')
__contributors__ = {}
__url__ = 'http://bots.ubuntulinux.nl'

import config
reload(config)
import plugin
reload(plugin)

if world.testing:
    import test
Class = plugin.Class
configure = config.configure
