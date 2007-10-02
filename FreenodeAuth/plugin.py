###
# Copyright (c) 2007, Dennis Kaarsemaker
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
import supybot.schedule as schedule
import random, os

class FreenodeAuth(callbacks.Plugin):
    """Use @login to login"""
    threaded = True

    def loadnicks(self):
        uf = self.registryValue('UserList')
        if not uf or not os.path.exists(uf):
            self.log.info('Not loading non-existant userlist')
            return
        fd = open(uf)
        users = fd.read()
        fd.close()
        knownusers = [x.lower() for x in users.split() if x]
        self.knownusers = knownusers
        allusers = [u.name.lower() for u in ircdb.users.itervalues()]

        to_add = [x for x in knownusers if x not in allusers]
        for a in to_add:
            self.log.info("Adding %s" % a)
            user = ircdb.users.newUser()
            user.name = a
            rp = ''
            chars = '''1234567890-=~!@#$%^&*()_qwertyuiop[]QWERTYUIOP{}}|asdfghjkl;ASDFGHJKL:zxcvbnm,./ZXCVBNM<>?'''
            for i in range(16):
                rp += chars[random.randint(1,len(chars))-1]
            user.setPassword(rp)
        irc.queueMsg(ircmsgs.IrcMsg('CAPAB IDENTIFY-MSG'))

    def do290(self, irc, msg):
        assert 'IDENTIFY-MSG' in msg.args[1]
        irc.getRealIrc()._Freenode_capabed = True

    def do376(self, irc, msg):
        irc.queueMsg(ircmsgs.IrcMsg('CAPAB IDENTIFY-MSG'))
    def do422(self, irc, msg): # MOTD missing
        irc.queueMsg(ircmsgs.IrcMsg('CAPAB IDENTIFY-MSG'))

    def inFilter(self, irc, msg):
        if getattr(irc,'_Freenode_capabed',None) and msg.command == 'PRIVMSG':
            first = msg.args[1][0]
            rest = msg.args[1][1:]
            msg.tag('identified', first == '+')
            msg = ircmsgs.privmsg(msg.args[0], rest, msg=msg)
            assert msg.receivedAt and msg.receivedOn and msg.receivedBy
        return msg
            
    def login(self, irc, msg, args):
        if not msg.tagged('identified'):
            irc.error(conf.supybot.replies.incorrectAuthentication())
            return
        try:
            user = ircdb.users.getUser(msg.prefix[:msg.prefix.find('!')])
        except:
            self.loadnicks()
            try:
                user = ircdb.users.getUser(msg.prefix[:msg.prefix.find('!')])
            except:
                irc.error(conf.supybot.replies.incorrectAuthentication())
                return
        user.addAuth(msg.prefix)
        ircdb.users.setUser(user, flush=False)
        irc.replySuccess()
    login = wrap(login)
Class = FreenodeAuth
