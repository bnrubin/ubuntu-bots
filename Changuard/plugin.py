import supybot.utils as utils
from supybot.commands import *
import supybot.plugins as plugins
import supybot.ircutils as ircutils
import supybot.callbacks as callbacks
import supybot.ircmsgs as ircmsgs

class Changuard(callbacks.PluginRegexp):
    """Channel guard"""
    regexps = ['theban','badwords']

    def theban(self, irc, msg, match):
        r"""((\S\S\S\S\S.*?)\2\2\2\2\2|nextpicturez)"""
        if self.registryValue('enabled', msg.args[0]):
            if msg.args[0][0] == "#":
                irc.queueMsg(ircmsgs.IrcMsg(command='REMOVE', args=(msg.args[0], msg.nick, "No flooding please"), msg=msg))
                irc.queueMsg(ircmsgs.ban(msg.args[0], '*!*@%s' % msg.host))

    def badwords(self, irc, msg, match):
        r"""http.*(sex|porn)"""
        if self.registryValue('enabled', msg.args[0]):
            if msg.args[0][0] == "#":
                irc.queueMsg(ircmsgs.IrcMsg(command='REMOVE', args=(msg.args[0], msg.nick, "Watch your language!"), msg=msg))
            
Class = Changuard
