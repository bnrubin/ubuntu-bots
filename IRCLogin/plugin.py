###
# Copyright (c) 2008, Terence Simpson
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

import supybot.utils as utils
from supybot.commands import *
import supybot.plugins as plugins
import supybot.ircutils as ircutils
import supybot.ircmsgs as ircmsgs
import supybot.callbacks as callbacks
import supybot.ircdb as ircdb
import supybot.conf as conf
import random, os, sys

def checkCapab(msg, irc):
    try:
        user = ircdb.users.getUser(msg.prefix[:msg.prefix.find('!')])
    except:
        irc.error(conf.supybot.replies.incorrectAuthentication())
        return False
    try:
        if not user.capabilities.check('Admin'):
            irc.error(conf.supybot.replies.noCapability() % 'Admin')
            return False
    except KeyError:
        irc.error(conf.supybot.replies.noCapability() % 'Admin')
        return False
    return True


class IRCLogin(callbacks.Plugin):
    """Use @login to login, @reloadusers to reload the user list and @updateusers to update the user database from 
launchpad"""
    threaded = True

    def __init__(self, irc):
        super(IRCLogin, self).__init__(irc)
        self._irc = irc
        if hasattr(irc, 'getRealIrc'):
            self._irc = irc.getRealIrc()

    def die(self):
        """Disable identify-msg, if possible"""
        if getattr(self._irc, '_Freenode_capabed', False):
            # Only the CAP command can disable identify-msg not CAPAB
            self._irc.queueMsg(ircmsgs.IrcMsg('CAP REQ -IDENTIFY-MSG')) # Disable identify-msg
            self._irc._Freenode_capabed = self._irc._Freenode_capabed_notices = False

    def login(self, irc, msg, args):
        """takes no arguments

        Allows users who are identified to NickServ to login without a password.
        """
        if not msg.tagged('identified'):
            irc.error('You are not identified')
            return
        nick = msg.nick.lower()
        user = None
        try:
            user = ircdb.users.getUser(msg.prefix)
        except:
            try:
                user = ircdb.users.getUser(msg.prefix)
            except:
                for (id, obj) in ircdb.users.users.iteritems():
                    if obj.name.lower() == nick:
                        user =  obj
                if not user:
                    irc.error(conf.supybot.replies.incorrectAuthentication())
                    return
        try:
            user.addAuth(msg.prefix)
        except:
            pass
        try:
            ircdb.users.setUser(user, flush=False)
        except:
            pass
        irc.replySuccess()
    login = wrap(login)

    @wrap
    def identifymsg(self, irc, msg, args):
        """
        takes no arguments.
        Sends a requet for the identify-msg capability.
        """
        self.do376(irc, msg, force=True)
        irc.replySuccess()

    @wrap
    def haveidentifymsg(self, irc, msg, args):
        haveCap = getattr(self._irc, "_Freenode_capabed", False)
        irc.reply("identify-msg is %sabled" % (haveCap and "En" or "Dis"))

    def doPrivmsg(self, irc, msg):
        if not conf.supybot.defaultIgnore(): # Only do this when defaultIgnore is set
            return
        if chr(1) in msg.args[1]:
            return
        try:
            user = ircdb.users.getUser(msg.prefix)
            if user.checkHostmask(msg.prefix):
                return
        except:
            pass

        text = callbacks.addressed(irc.nick, msg)
        cmd = ''
        if not text or text != "login":
            if msg.args[1]:
                if ircutils.isChannel(msg.args[0]):
                    if msg.args[1][0] == '@':
                        cmd = msg.args[1][1:]
                else:
                    if msg.args[1][0] == '@':
                        cmd = msg.args[1][1:]
                    else:
                        cmd = msg.args[1]
                if cmd != "login":
                    return
            else:
                return
        self.log.info("Calling login for %s" % msg.prefix)
        self._callCommand(["login"], irc, msg, [])

    def do290(self, irc, msg):
        """hyperiron CAPAB reply"""
        self._irc._Freenode_capabed_notices = False
        if msg.args[1].lower() == "identify-msg":
            self._irc._Freenode_capabed = True
        else:
            self._irc._Freenode_capabed = False

    def doCap(self, irc, msg):
        """ircd-seven CAP reply"""
        cmd = msg.args[1].lower()
        args = msg.args[2].lower()
        if cmd == "ls": # Got capability listing
            if "identify-msg" in args: # identify-msg is a capability on this server
                irc.queueMsg(ircmsgs.IrcMsg('CAP REQ IDENTIFY-MSG')) # Request identify-msg

        if cmd == "ack": # Acknowledge reply
            if "identify-msg" in args: # identify-msg is set
                self._irc._Freenode_capabed = True
                self._irc._Freenode_capabed_notices = True

        if cmd == 'nak': # Failure reply
            if "identify-msg" in args: # identify-msg is not set
                self._irc._Freenode_capabed = False
                self._irc._Freenode_capabed_notices = False

    def do421(self, irc, msg):
        """Invalid command"""
        if msg.args[1].lower() == "cap":
            irc.queueMsg(ircmsgs.IrcMsg("CAPAB IDENTIFY MSG"))

    def do376(self, irc, msg, force=False): # End of /MOTD command.
        """
        The new freenode ircd-seven requires using the 'CAP' command
        to set capabilities, rather than hyperirons 'CAPAB' command.
        You request "CAP REQ IDENTIFY-MSG" and the server will respond
        with either "CAP <nick> ACK :identify-msg" to acknowledge, or
        "CAP <nick> NAK :identify-msg" to indicate failure.
        Other than that, it's the same.
        """
        if not hasattr(self._irc, "_Freenode_capabed") or force: # Do this only once
            self._irc._Freenode_capabed = False
            self._irc._Freenode_capabed_notices = False
            # Try the CAP command first
            irc.queueMsg(ircmsgs.IrcMsg("CAP LS"))

    do422 = do376

    def inFilter(self, irc, msg):
        """
        Strip the leading '+' or '-' from each message
        """

        if msg.command not in ("PRIVMSG", "NOTICE"):
            return msg

        if not getattr(irc, '_Freenode_capabed', False):
            return msg

        if msg.command == "NOTICE" and not getattr(irc, '_Freenode_capabed_notices', False):
            return msg

        if msg.tagged('identified') == None:
            first = msg.args[1][0]
            rest = msg.args[1][1:]
            msg.tag('identified', first == '+')
            if first in ('+', '-'):
                if msg.command == "NOTICE":
                    msg = ircmsgs.notice(msg.args[0], rest, msg=msg)
                else:
                    msg = ircmsgs.privmsg(msg.args[0], rest, msg=msg)
                    if not ircutils.isChannel(msg.args[0]): # /msg
                        ##TODO: check here that the user isn't already logged in
                        cmd = msg.args[1]
                        if cmd and cmd[0] in str(conf.supybot.reply.whenAddressedBy.chars()):
                            cmd = cmd[1:]
                        if cmd.lower() == 'login':
                            self.doPrivmsg(callbacks.ReplyIrcProxy(irc, msg), msg) # If the login command is given in /msg, force it through
                            return # Don't return the msg otherwise it'll be processed twice
            else:
                self.do376(irc, msg, True)
            assert msg.receivedAt and msg.receivedOn and msg.receivedBy

        if len(msg.args) >= 2 and msg.args[1] and msg.args[1][0] in ('+', '-'):
            self.do376(irc, msg, True)
        return msg

Class = IRCLogin
