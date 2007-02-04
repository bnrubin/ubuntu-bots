###
# Copyright (c) 2006, Dennis Kaarsemaker
# All rights reserved.
#
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

from supybot.commands import *
import supybot.callbacks as callbacks
import os


class Restart(callbacks.Plugin):
    """Restart the bot with restart"""

    @wrap
    def restart(self,irc,msg,args):
        try:
             _ = ircdb.users.getUser(msg.prefix)
             if not ircdb.checkCapability(msg.prefix, 'restart'):
                raise KeyError, "Bogus error to trigger the exception"
        except:
            irc.error("You don't have permission to restart")
            return
        conf = self.registryValue('configfile')
        if not conf:
            irc.error("No configfile specified")
        else:
            os.execlp('supybot','supybot',conf)
Class = Restart
