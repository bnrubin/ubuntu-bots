###
# Copyright (c) 2006 Dennis Kaarsemaker
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
#
# Based on the standard supybot logging plugin, which has the following
# copyright:
#
# Copyright (c) 2002-2004, Jeremiah Fincher
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice,
#     this list of conditions, and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions, and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#   * Neither the name of the author of this software nor the name of
#     contributors to this software may be used to endorse or promote products
#     derived from this software without specific prior written consent.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
###

import supybot.utils as utils
from supybot.commands import *
import supybot.plugins as plugins
import supybot.ircutils as ircutils
import supybot.callbacks as callbacks
import supybot.ircmsgs as ircmsgs
import supybot.conf as conf
import supybot.world as world

import sqlite, pytz, cPickle, datetime, time

db = '/home/dennis/ubugtu/data/bans.db'
tz = 'Europe/Amsterdam'

def now():
    return cPickle.dumps(datetime.datetime.now(pytz.timezone(tz)))

def db_run(query, parms, expect_result = False, expect_id = False):
    con = sqlite.connect(db)
    cur = con.cursor()
    try:
        cur.execute(query, parms)
    except:
        con.close()
        raise
    data = None
    if expect_result: data = cur.fetchall()
    if expect_id: data = con.insert_id()
    con.commit()
    con.close()
    return data

class Bantracker(callbacks.Plugin):
    """This plugin has no commands"""
    noIgnore = True
    
    def __init__(self, irc):
        self.__parent = super(Bantracker, self)
        self.__parent.__init__(irc)
        self.lastMsgs = {}
        self.lastStates = {}
        self.logs = {}
        for channel in irc.state.channels:
            self.doStatsLog(irc, channel, "START")

    def __call__(self, irc, msg):
        try:
            # I don't know why I put this in, but it doesn't work, because it
            # doesn't call doNick or doQuit.
            # if msg.args and irc.isChannel(msg.args[0]):
            super(self.__class__, self).__call__(irc, msg)
            if irc in self.lastMsgs:
                if irc not in self.lastStates:
                    self.lastStates[irc] = irc.state.copy()
                self.lastStates[irc].addMsg(irc, self.lastMsgs[irc])
        finally:
            # We must make sure this always gets updated.
            self.lastMsgs[irc] = msg

    def reset(self):
        self.logs.clear()
        self.lastMsgs.clear()
        self.lastStates.clear()

    def doLog(self, irc, channel, s):
        if not self.registryValue('enabled', channel):
            return
        channel = ircutils.toLower(channel) 
        if channel not in self.logs.keys():
            self.logs[channel] = []
        format = conf.supybot.log.timestampFormat()
        if format:
            s = time.strftime(format) + " " + ircutils.stripFormatting(s)
        self.logs[channel] = self.logs[channel][-199:] + [s.strip()]

    def doStatsLog(self, irc, chan, type):
        if not self.registryValue('stats', chan):
            return
        num = len(irc.state.channels[chan].users)
        format = conf.supybot.log.timestampFormat()
        statslog = open('/home/dennis/ubugtu/data/statslog','a')
        statslog.write("%-20s %f %s %-6s %d\n" % (chan, time.time(), time.strftime(format), type, num))
        statslog.close()
        
    def doKickban(self, irc, channel, nick, target, kickmsg = None):
        if not self.registryValue('enabled', channel):
            return
        n = now()
        id = db_run("INSERT INTO bans (channel, mask, operator, time, log) values(%s, %s, %s, %s, %s)", 
                          (channel, target, nick, n, '\n'.join(self.logs[channel])), expect_id=True)
        if kickmsg and id and not (kickmsg == nick):
            db_run("INSERT INTO comments (ban_id, who, comment, time) values(%s,%s,%s,%s)", (id, nick, kickmsg, n))

    def doUnban(self, irc, channel, nick, mask):
        if not self.registryValue('enabled', channel):
            return
        data = db_run("SELECT MAX(id) FROM bans where channel=%s and mask=%s", (channel, mask), expect_result=True)
        if len(data) and not (data[0][0] == None):
            db_run("UPDATE bans SET removal=%s , removal_op=%s WHERE id=%s", (now(), nick, int(data[0][0])))

    def doPrivmsg(self, irc, msg):
        (recipients, text) = msg.args
        for channel in recipients.split(','):
            if irc.isChannel(channel):
                nick = msg.nick or irc.nick
                if ircmsgs.isAction(msg):
                    self.doLog(irc, channel,
                               '* %s %s\n' % (nick, ircmsgs.unAction(msg)))
                else:
                    self.doLog(irc, channel, '<%s> %s\n' % (nick, text))

    def doNotice(self, irc, msg):
        (recipients, text) = msg.args
        for channel in recipients.split(','):
            if irc.isChannel(channel):
                self.doLog(irc, channel, '-%s- %s\n' % (msg.nick, text))

    def doNick(self, irc, msg):
        oldNick = msg.nick
        newNick = msg.args[0]
        for (channel, c) in irc.state.channels.iteritems():
            if newNick in c.users:
                self.doLog(irc, channel,
                           '*** %s is now known as %s\n' % (oldNick, newNick))
    def doJoin(self, irc, msg):
        for channel in msg.args[0].split(','):
            self.doLog(irc, channel,
                       '*** %s has joined %s\n' % (msg.nick or msg.prefix, channel))
        if irc.prefix != msg.prefix:
            self.doStatsLog(irc, msg.args[0], "JOIN")

    def doKick(self, irc, msg):
        if len(msg.args) == 3:
            (channel, target, kickmsg) = msg.args
        else:
            (channel, target) = msg.args
            kickmsg = ''
        if kickmsg:
            self.doLog(irc, channel,
                       '*** %s was kicked by %s (%s)\n' % (target, msg.nick, kickmsg))
        else:
            self.doLog(irc, channel,
                       '*** %s was kicked by %s\n' % (target, msg.nick))
        self.doKickban(irc, channel, msg.nick, target, kickmsg)
        self.doStatsLog(irc, msg.args[0], "KICK")

    def doPart(self, irc, msg):
        for channel in msg.args[0].split(','):
            self.doLog(irc, channel, '*** %s (%s) has left %s (%s)\n' % (msg.nick, msg.prefix, channel, msg.args[1]))
            if msg.args[1].startswith('requested by'):
                args = msg.args[1].split()
                self.doKickban(irc, channel, args[2].replace(':',''), msg.nick, ' '.join(args[3:])[1:-1].strip())
        if irc.prefix != msg.prefix:
            self.doStatsLog(irc, msg.args[0], "PART")

    def doMode(self, irc, msg):
        channel = msg.args[0]
        if irc.isChannel(channel) and msg.args[1:]:
            self.doLog(irc, channel,
                       '*** %s sets mode: %s %s\n' %
                       (msg.nick or msg.prefix, msg.args[1],
                        ' '.join(msg.args[2:])))
            if 'b' in msg.args[1] or 'd' in msg.args[1]:
                i = 2
                plusmin = False
                for c in msg.args[1]:
                    if   c == '-': plusmin = False
                    elif c == '+': plusmin = True
                    else:
                        if c == 'b':
                            if plusmin: self.doKickban(irc, channel, msg.nick, msg.args[i])
                            else: self.doUnban(irc,channel, msg.nick, msg.args[i])
                            i += 1
                        if c == 'd':
                            if plusmin: self.doKickban(irc, channel, msg.nick, msg.args[i] + ' (realname)')
                            else: self.doUnban(irc,channel, msg.nick, msg.args[i] + ' (realname)')
                            i += 1

    def doTopic(self, irc, msg):
        if len(msg.args) == 1:
            return # It's an empty TOPIC just to get the current topic.
        channel = msg.args[0]
        self.doLog(irc, channel,
                   '*** %s changes topic to "%s"\n' % (msg.nick, msg.args[1]))

    def doQuit(self, irc, msg):
        for (channel, chan) in self.lastStates[irc].channels.iteritems():
            if msg.nick in chan.users:
                self.doLog(irc, channel, '*** %s has quit IRC (%s)\n' % (msg.nick, msg.args[0]))
                self.doStatsLog(irc, channel, "QUIT")

    def outFilter(self, irc, msg):
        # Gotta catch my own messages *somehow* :)
        # Let's try this little trick...
        if msg.command in ('PRIVMSG', 'NOTICE'):
            # Other messages should be sent back to us.
            m = ircmsgs.IrcMsg(msg=msg, prefix=irc.prefix)
            self(irc, m)
        return msg
        
    def do366(self, irc, msg):
        self.doStatsLog(irc, msg.args[1], "START")

Class = Bantracker
