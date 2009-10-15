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
import supybot.schedule as schedule
import random, os, sys
from cPickle import Unpickler, Pickler
import lp

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

    def updateusers(self, irc, msg, args):
        """Takes no arguments

        Update the user database from Launchpad"""
        def writePickle(uf, user2nick, nick2user):
            global self
            try:
                fd = open(uf, 'wb')
            except IOError, e:
                self.log.error("Could not write to %s (%s)" % (uf, e))
                return
            except Exception, e:
                self.log.error("Unknown error while opening %s for writing:\n%s" % (uf, e))
                return
            pi = Pickler(fd, 2)
            pi.dump((user2nick, nick2user))

        if not checkCapab(msg, irc):
            return
        uf = self.registryValue('UserList')
        if not uf:
            self.log.info('no UserList config set')
            irc.error('No UserList config set')
            return
        if not os.path.exists(uf):
            self.log.info('Creating initial userlist')
        else:
            self.log.info('Updating userlist')
        irc.reply('Running...')
        user2nick = {}
        nick2user = {}
        users = lp.getUsers()
        for user in users:
            lpuser = lp.getIRCNick(user, False)
            if not lpuser:
                lpuser = [user]
            user2nick[user] = lpuser
            for nick in lpuser:
                nick2user[nick] = user
        writePickle(uf, user2nick, nick2user)
        self.loadUsers()
        irc.reply('updateusers run complete')
    updateusers = wrap(updateusers)

    def loadUsers(self):
        uf = self.registryValue('UserList')
        if not uf or not os.path.exists(uf) or not os.access(uf, os.R_OK):
            self.log.info('Not loading non-existant userlist')
            return
        fd = open(uf, 'rb')
        up = Unpickler(fd)
        (self.user2nick, self.nick2user) = up.load()
        nick2user = self.nick2user
        user2nick = self.user2nick
        self.knownusers = [i.lower() for i in nick2user.keys()]
        allusers = [u.name.lower() for u in ircdb.users.itervalues()]
        to_add = [x for x in self.knownusers if x not in allusers]
        for a in to_add:
            self.log.info("Adding %s" % a)
            user = ircdb.users.newUser()
            user.name = a
            rp = ''
            chars = '''1234567890-=~!@#$%^&*()_qwertyuiop[]QWERTYUIOP{}}|asdfghjkl;ASDFGHJKL:zxcvbnm,./ZXCVBNM<>?'''
            for i in range(16):
                rp += chars[random.randint(1,len(chars))-1]
            user.setPassword(rp)
        bu = []
        for u in nick2user.keys():
            try:
                user = ircdb.users.getUser(u.lower())
                if not 'bantracker' in user.capabilities:
                    user.addCapability('bantracker')
            except Exception, e:
                bu.append("%s (%s)" % (u, e))
                pass
        if bu:
            self.log.info("Could not add users %s" % bu)

    def reloadusers(self, irc, msg, args):
        """Takes no arguments

        Read the user database and add the users in it"""
        if not checkCapab(msg, irc):
            return
        self.loadUsers()
        irc.replySuccess()
    reloadusers = wrap(reloadusers)

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
            user = self.nick2user.get(nick, None)
            if user:
                user = ircdb.users.getUser(user)
        except:
            user = None
            pass
        if not user:
            try:
                user = ircdb.users.getUser(msg.prefix)
            except:
                self.loadUsers()
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

    def doPrivmsg(self, irc, msg):
        if not conf.supybot.defaultIgnore: # Only do this when defaultIgnore is set
            return
        if chr(1) in msg.args[1]:
            return
        try:
            user = ircdb.users.getUser(msg.prefix)
            if user.checkHostmask(msg.prefix):
                #self.log.info("%s is a known user: %r" % (msg.prefix, user))
                return
        except:
            pass

        text = callbacks.addressed(irc.nick, msg)
        if not text or text != "login":
            if msg.args[1]:
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
        assert 'IDENTIFY-MSG' in msg.args[1]
        irc.getRealIrc()._Freenode_capabed = True

    def do376(self, irc, msg):
        irc.queueMsg(ircmsgs.IrcMsg('CAPAB IDENTIFY-MSG'))
    def do422(self, irc, msg): # MOTD missing
        irc.queueMsg(ircmsgs.IrcMsg('CAPAB IDENTIFY-MSG'))

    def inFilter(self, irc, msg):
        if not msg.command == "PRIVMSG":
            return msg
        if getattr(irc,'_Freenode_capabed',None) and msg.command == 'PRIVMSG':
            if msg.tagged('identified') == None:
                first = msg.args[1][0]
                rest = msg.args[1][1:]
                msg.tag('identified', first == '+')
                if first in ('+', '-'):
                    msg = ircmsgs.privmsg(msg.args[0], rest, msg=msg)
                assert msg.receivedAt and msg.receivedOn and msg.receivedBy
        if len(msg.args) >= 2 and msg.args[1] and msg.args[1][0] in ('+', '-'):
            self.do376(irc, msg)
        return msg

Class = IRCLogin
