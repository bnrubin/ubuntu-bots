"""
Random mess plugin
"""

import supybot
import supybot.world as world

__version__ = "0.5"
__author__ = supybot.Author('Dennis Kaarsemaker','Seveas','dennis@kaarsemaker.net')
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
